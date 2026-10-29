#!/usr/bin/env python3
"""Bounded Neo diagnostic EP0 IN reads; no CDC, JTAG, reset or reconfiguration.

The expected build is an operator annotation, never USB bitstream readback.
--check-only checks local proof/input identities and never opens sysfs or USB.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import struct
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOCK = ROOT / 'TESTS/neo_board.lock'
PROOF = HERE / 'routed_diagnostic_proof.json'
PROOF_SHA = '544dc367ee0c26a078d92dc92d716a3deda8150789fe52c815ed10a8ba0fa28a'
IDENTITY = dict(idVendor='359f', idProduct='2011', serial='NEO00001', product='MegaNeo Console')
BUILD_SHA = {
    'n56r8': '51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35',
    'r9': '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_preflight():
    require(sha(PROOF) == PROOF_SHA, 'Routed diagnostic proof changed')
    proof = json.loads(PROOF.read_text())
    require(proof['passed'] and proof['hardware_access'] is False, 'Invalid structural proof')
    require(proof['bitstream_sha256'] == BUILD_SHA, 'Different frozen builds')
    for name, digest in proof['input_sha256'].items():
        require(sha(Path(name)) == digest, 'Frozen diagnostic input changed: ' + name)
    return dict(proof_sha256=PROOF_SHA, bitstream_sha256=BUILD_SHA,
                signature=0xd1, bytes=32, request=[0xa0, 0x21, 0xd1a6, 0, 32])


def decode(raw):
    require(len(raw) == 32, 'Diagnostic reply must be exactly 32 bytes')
    words = struct.unpack('<8I', raw)
    require(words[5] >> 24 == 0xd1, 'Diagnostic signature is not D1')
    nibble = words[4] >> 28
    return dict(raw_hex=raw.hex(), words_le32=list(words), signature=0xd1,
        board_status_nibble=nibble, pll_ae350_filtered_lock=(nibble >> 3) & 1,
        ddr3_stop_enclk2=(nibble >> 2) & 1, pll_ddr_filtered_lock=(nibble >> 1) & 1,
        ae350_por_hw_rstn=nibble & 1)


def read_identity(path):
    return {name: (path / name).read_text().strip() for name in
            ('idVendor', 'idProduct', 'serial', 'product', 'busnum', 'devnum')}


def select_device(port, address, sysroot=Path('/sys/bus/usb/devices')):
    require(re.fullmatch(r'[1-9]\d*-[1-9]\d*(?:\.[1-9]\d*)*', port), 'Invalid physical USB port')
    require(re.fullmatch(r'[1-9]\d*:[1-9]\d*', address), 'Specify decimal bus:device address')
    path = sysroot / port
    target = read_identity(path)
    require(all(target[k] == v for k, v in IDENTITY.items()), 'Not the Neo SOFT-USB identity')
    require(target['busnum'] + ':' + target['devnum'] == address, 'USB address changed')
    matches, debuggers = [], []
    for item in sysroot.iterdir():
        try:
            identity = read_identity(item)
        except OSError:
            continue
        if identity['serial'] == 'NEO00001':
            matches.append(item.name)
        if identity['serial'] == '2025041420':
            require(identity['idVendor'] == '0403' and identity['idProduct'] == '6010',
                    'Unexpected Neo debugger VID/PID')
            debuggers.append(dict(path=str(item), **identity))
    require(matches == [port], 'Neo SOFT-USB serial missing or ambiguous')
    require(len(debuggers) == 1, 'Neo debugger identity missing or ambiguous')
    return dict(path=str(path), port=port, debugger=debuggers[0], **target)


class Control(ctypes.Structure):
    _fields_ = [('request_type', ctypes.c_uint8), ('request', ctypes.c_uint8),
        ('value', ctypes.c_uint16), ('index', ctypes.c_uint16), ('length', ctypes.c_uint16),
        ('timeout', ctypes.c_uint32), ('data', ctypes.c_void_p)]


def read_once(fd, timeout_ms=1000, ioctl=fcntl.ioctl):
    require(1 <= timeout_ms <= 1000, 'Transfer timeout out of range')
    buf = ctypes.create_string_buffer(32)
    req = Control(0xa0, 0x21, 0xd1a6, 0, 32, timeout_ms, ctypes.addressof(buf))
    number = 0xc0005500 | (ctypes.sizeof(Control) << 16)  # USBDEVFS_CONTROL
    received = ioctl(fd, number, bytearray(bytes(req)))
    require(received == 32, f'Short diagnostic reply: {received}/32')
    return decode(buf.raw)


def collect(port, address, count, report, checkpoint):
    identity = select_device(port, address)
    report['usb_identity'] = identity
    node = Path('/dev/bus/usb') / f"{int(identity['busnum']):03d}" / f"{int(identity['devnum']):03d}"
    # O_RDWR is required by USBDEVFS_CONTROL even for an IN-only request.
    # No interface claim/detach/configuration/reset ioctls are used.
    with node.open('r+b', buffering=0) as stream:
        info = os.fstat(stream.fileno())
        expected_minor = (int(identity['busnum']) - 1) * 128 + int(identity['devnum']) - 1
        require(stat.S_ISCHR(info.st_mode) and os.major(info.st_rdev) == 189 and
                os.minor(info.st_rdev) == expected_minor, 'USB device node identity differs')
        for index in range(count):
            require(select_device(port, address) == identity, 'USB identity changed during sampling')
            sample = read_once(stream.fileno())
            require(select_device(port, address) == identity, 'USB identity changed after request')
            sample.update(index=index, monotonic_ns=time.monotonic_ns())
            report['samples'].append(sample)
            checkpoint()
            if index + 1 < count:
                time.sleep(.1)
    report['measurement_available'] = True
    report['stable_board_status'] = len({s['board_status_nibble'] for s in report['samples']}) == 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--usb-port', help='Operator-confirmed Neo SOFT-USB physical sysfs port, e.g. 3-4.4.3')
    parser.add_argument('--usb-address', help='Current decimal bus:device address, e.g. 3:42')
    parser.add_argument('--expected-build', choices=BUILD_SHA)
    parser.add_argument('--samples', type=int, default=3, choices=range(1, 11))
    parser.add_argument('--out', type=Path, help='New output JSON; never overwrites an earlier measurement')
    args = parser.parse_args(argv)
    checked = local_preflight()
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, **checked)))
        return 0
    if not all((args.usb_port, args.usb_address, args.expected_build, args.out)):
        parser.error('--usb-port, --usb-address, --expected-build and --out are required')
    report = dict(passed=False, measurement_available=False, samples=[], functional_qualification=False,
        scope='Neo diagnostic EP0 IN only', expected_build=args.expected_build,
        expected_bitstream_sha256=BUILD_SHA[args.expected_build], bitstream_readback_verified=False,
        script_sha256=sha(Path(__file__)), structural_proof=checked,
        usb_reset_requested=False, cdc_opened=False, cpu_accessed=False, gpu_accessed=False,
        memory_written=False, qualification_status='FAIL',
        limits=['USB absence/failure does not diagnose the AE350 PLL or CPU reset.',
            'Bits are independently synchronized slow levels, not an atomic clock/reset trace.',
            'Filtered lock is not a frequency, edge-quality or core-clock measurement.',
            'EP0 SETUP selects an endpoint and snapshots counters; it can affect concurrent USB traffic.',
            'Configured FPGA identity is supplied by the operator, not read over USB.'])
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Signal ' + str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    # Reserve output before acquiring hardware resources; no truncation allowed.
    with args.out.open('x') as output:
        def checkpoint():
            output.seek(0)
            json.dump(report, output, indent=2)
            output.write('\n')
            output.truncate()
            output.flush()
        try:
            with LOCK.open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                collect(args.usb_port, args.usb_address, args.samples, report, checkpoint)
                report['passed'] = True
        except BaseException as error:
            report['error'] = repr(error)
        finally:
            checkpoint()
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
