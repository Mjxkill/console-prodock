#!/usr/bin/env python3
"""Bind the unchanged, validated Linux RAM loader to Pro Dock 2025071717.

Only board selection is adapted. The original loader retains all manifest,
payload, launcher, pause acknowledgement, J-Link verification and boot-CRC checks.
The console topology is established by the preceding G22r0 enumeration record;
the firmware iSerial alone is ambiguous with two identical consoles attached.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile

ROOT = Path('/home/michael/console-validation-20261001')
WORK = ROOT / 'TESTS/prodock_2025071717_20261028'
PACK = WORK / 'inputs'
ARCHIVE = Path('/tmp/prodock_2025071717_inputs_20261028.tar.gz')
ARCHIVE_SHA = '69c2d5bd247fcf836433dc941a370e0bd403168c292dd6a35e65fdb07d8ef73c'
PORT = '/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0'
USB = Path('/sys/bus/usb/devices/3-7.1')
SERIAL = '2025071717'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound_console():
    keys = ('idVendor', 'idProduct', 'serial', 'busnum', 'devnum', 'speed')
    d = {k: (USB / k).read_text().strip() for k in keys}
    assert (d['idVendor'], d['idProduct'], d['serial'], d['speed']) == ('359f', '2011', '11252024', '480')
    return PORT, dict(d, speed_mbps=480, path=str(USB), port=PORT)


def bound_programmer():
    found = []
    for p in Path('/sys/bus/usb/devices').iterdir():
        if not (p / 'serial').exists() or (p / 'serial').read_text().strip() != SERIAL:
            continue
        assert (p / 'idVendor').read_text().strip() == '0403'
        assert (p / 'idProduct').read_text().strip() == '6010'
        found.append(':'.join((p / k).read_text().strip() for k in ('busnum', 'devnum')))
    assert len(found) == 1
    return found[0]


def main():
    global SERIAL, PORT, USB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--target', choices=('2023112818', '2025071717'), required=True)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    SERIAL = args.target
    branch = '3' if SERIAL == '2023112818' else '1'
    PORT = f'/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.{branch}:1.0'
    USB = Path(f'/sys/bus/usb/devices/3-7.{branch}')
    assert __debug__ and socket.gethostname().split('.')[0] == 'michael-AX15'
    assert sha(ARCHIVE) == ARCHIVE_SHA
    if not PACK.exists():
        PACK.mkdir()
        with tarfile.open(ARCHIVE) as archive:
            archive.extractall(PACK, filter='data')
    manifest = json.loads((PACK / 'inputs.json').read_text())
    # This archive contains identical Pro Dock software for both instances;
    # physical selection is explicit and independently bound below.
    assert manifest['target_programmer_serial'] == '2025071717'
    for name, item in manifest['files'].items():
        p = PACK / name
        assert p.is_file() and not p.is_symlink() and p.stat().st_size == item['bytes'] and sha(p) == item['sha256']
    expected = {'load_linux.py': '2cd0414c1f0dc92cebf81ce95396d5dcb7db1230c33e01597a3daab417beabc0',
                'load_ilm.py': '313948071b2aa592330c877e858a5b1806519867852b6d3220995dc4934b282c'}
    for name, digest in expected.items():
        assert sha(ROOT / 'tools' / name) == digest, name + ' changed'
    proof = json.loads(args.proof.read_text())
    assert proof['configuration_completed'] and proof['target_serial'] == SERIAL
    assert proof['bitstream_sha256'] == manifest['fpga_sha256']
    before = {(d['path'], d['devnum']) for d in proof['before'] if d['idVendor'] == '359f'}
    after = {(d['path'], d['devnum']) for d in proof['usb_observations'][-1] if d['idVendor'] == '359f'}
    assert {path for path, dev in after - before} == {str(USB)}, 'Console is not uniquely tied to this FPGA programming'
    binding = json.loads(args.binding.read_text())
    assert binding['passed'] and binding['target'] == SERIAL and binding['port'] == PORT
    # The nonce proved JTAG-to-UART association with no payload RAM writes.
    assert binding['started_unix'] > proof['finished_unix']
    print('Inputs and board association PASS', flush=True)
    if not args.run:
        return
    fd = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        bound_programmer()
        bound_console()
        owner = subprocess.run(['fuser', PORT], capture_output=True)
        assert owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip()
        jlinks = [p for p in Path('/sys/bus/usb/devices').iterdir()
                  if (p / 'serial').exists() and (p / 'serial').read_text().strip() == '000506005083'
                  and (p / 'idVendor').read_text().strip() == '1366']
        assert len(jlinks) == 1, 'CPU J-Link unavailable'
        sys.path.insert(0, str(ROOT / 'tools'))
        import load_linux
        load_linux.target_busdev = bound_programmer
        load_linux.wait_console = bound_console
        class GuardedProcesses:
            """Keep the original loader; add a fresh CPU gate to its J-Link call."""
            def __getattr__(self, name):
                return getattr(subprocess, name)

            def run(self, command, **kwargs):
                if command[0] == 'JLinkExe':
                    assert command[1:3] == ['-SelectEmuBySN', '506005083']
                    command = [*command, '-JLinkScriptFile', '/tmp/cpu_cold_guard.JLinkScript']
                return subprocess.run(command, **kwargs)
        load_linux.subprocess = GuardedProcesses()
        sys.argv = ['load_linux.py', '--pack', str(PACK / 'linux'), '--packed',
                    '--jtag-speed', '4000', '--out', str(args.out)]
        load_linux.main()


if __name__ == '__main__':
    main()
