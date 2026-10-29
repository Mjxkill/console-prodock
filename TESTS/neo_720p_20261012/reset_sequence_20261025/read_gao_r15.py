#!/usr/bin/env python3
"""Read the initial GAO capture of the exact diagnostic N56r15 with 50 ms reset.

The installed CLI branches to initial read when capture_init_data_enabled=true.
No reprogram, ordinary rearm, auto-run, or force is requested. Bounded timeout;
only owned child processes are stopped. Raw CSV timing unit needs correction.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLD = HERE.parent / "reload_r1_cold_20261022"
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(COLD))
sys.path.insert(0, str(COLD / 'gao_cli_research'))
from gowin_toolchain import IDE, environment
from probe_route9_led_compare import usb_identity
from inspect_gao_gui import stop_owned_children

GAO = ROOT / 'tang/impl/console_neo_n56r15_reset50ms/source/tang/boards/neo/reset_trial.gao'
GAO_SHA = '6fc99d0f73e07d5a00226db14192508982d20cf9dbbb3125d6afdefcf5e91a5f'
BIT_SHA = '8b005988433a70fdef654f5e2e7f93b3ba484764c1be44bb356bd1418931227b'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_neo():
    identity = usb_identity()
    assert identity['programmer_busdev'] == '3:28'
    library = ctypes.CDLL('/home/michael/gowin/Programmer/bin/libftd2xx.so')
    count = ctypes.c_ulong(0)
    assert library.FT_CreateDeviceInfoList(ctypes.byref(count)) == 0 and count.value < 20
    entries, enumerated = [], []
    for index in range(count.value):
        flags, kind, ident, location = [ctypes.c_ulong(0) for _ in range(4)]
        serial, desc = ctypes.create_string_buffer(128), ctypes.create_string_buffer(128)
        handle = ctypes.c_void_p()
        status = library.FT_GetDeviceInfoDetail(index, ctypes.byref(flags), ctypes.byref(kind),
                    ctypes.byref(ident), ctypes.byref(location), serial, desc, ctypes.byref(handle))
        enumerated.append(dict(status=status, index=index, flags=flags.value,
            location=location.value, id=ident.value,
            serial=serial.value.decode(errors='replace'), description=desc.value.decode(errors='replace')))
        if serial.value == b'2025041420A':
            assert status == 0 and location.value == 12737 and ident.value == 0x04036010
            entries.append(dict(index=index, location=location.value,
                                serial=serial.value.decode(), description=desc.value.decode()))
    assert len(entries) == 1 and entries[0]['description'] == 'USB Debugger A', enumerated
    return dict(usb=identity, selected=entries[0])


def borrow_jtag_interface(report):
    """Temporarily detach only channel A of the sysfs-identified Neo cable."""
    identity = usb_identity()
    assert identity['neo']['path'].endswith('/3-4.4.1')
    assert identity['neo']['serial'] == '2025041420'
    bus, address = map(int, identity['programmer_busdev'].split(':'))
    lib = ctypes.CDLL('libusb-1.0.so.0')
    ptr = ctypes.c_void_p
    lib.libusb_init.argtypes = [ctypes.POINTER(ptr)]
    lib.libusb_exit.argtypes = [ptr]
    lib.libusb_get_device_list.argtypes = [ptr, ctypes.POINTER(ctypes.POINTER(ptr))]
    lib.libusb_get_device_list.restype = ctypes.c_ssize_t
    lib.libusb_free_device_list.argtypes = [ctypes.POINTER(ptr), ctypes.c_int]
    lib.libusb_get_bus_number.argtypes = lib.libusb_get_device_address.argtypes = [ptr]
    lib.libusb_get_bus_number.restype = lib.libusb_get_device_address.restype = ctypes.c_uint8
    lib.libusb_open.argtypes = [ptr, ctypes.POINTER(ptr)]
    lib.libusb_close.argtypes = [ptr]
    for name in ['libusb_kernel_driver_active', 'libusb_detach_kernel_driver', 'libusb_attach_kernel_driver']:
        getattr(lib, name).argtypes = [ptr, ctypes.c_int]
    ctx, handle = ptr(), ptr()
    devices = ctypes.POINTER(ptr)()
    detached = False
    assert lib.libusb_init(ctypes.byref(ctx)) == 0
    try:
        count = lib.libusb_get_device_list(ctx, ctypes.byref(devices))
        assert count >= 0
        matches = [devices[i] for i in range(count)
            if lib.libusb_get_bus_number(devices[i]) == bus and lib.libusb_get_device_address(devices[i]) == address]
        assert len(matches) == 1
        assert lib.libusb_open(matches[0], ctypes.byref(handle)) == 0
        active = lib.libusb_kernel_driver_active(handle, 0)
        assert active in (0, 1)
        report['kernel_driver'] = dict(interface=0, initially_bound=bool(active),
            channel_B_untouched=True, identity=identity)
        if active:
            assert lib.libusb_detach_kernel_driver(handle, 0) == 0
            detached = True
        return lib, ctx, handle, detached
    except BaseException:
        if handle:
            if detached: lib.libusb_attach_kernel_driver(handle, 0)
            lib.libusb_close(handle)
        lib.libusb_exit(ctx)
        raise
    finally:
        if devices: lib.libusb_free_device_list(devices, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-name', default='r15_initial_read_01')
    args = parser.parse_args()
    assert re.fullmatch(r'r15_initial_read_[0-9]{2}', args.out_name)
    out = HERE / args.out_name
    assert not out.exists()
    assert sha(GAO) == GAO_SHA and 'capture_init_data_enabled="true"' in GAO.read_text()
    cli = IDE / 'bin/gao_sh'
    assert sha(cli) == '4717a2afa56893861de161207bc2c4f094f53227099763ebfa2f0025ab72515b'
    loaded = json.loads((HERE / 'cold_trial_01/result.json').read_text())
    assert loaded['configured'] and loaded['bitstream_sha256'] == BIT_SHA and not loaded['previous_restored']
    token = uuid.uuid4().hex
    children, logs = [], []
    report = dict(bitstream_sha256=BIT_SHA, qualification_status='FAIL',
        gao_sha256=GAO_SHA, cli_sha256=sha(cli), script_sha256=sha(Path(__file__)),
        programming=False, rearm_requested=False, force_requested=False,
        initial_read_requested=True, real_sample_period_ns=20,
        cli_csv_period_is_wrong=True, timeout_seconds=45)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Signal ' + str(signum))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, interrupted)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
            '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip()
        out.mkdir()
        private_tmp = tempfile.mkdtemp(prefix='console-gao-read-')
        report['runtime_dir'] = private_tmp
        borrowed = None
        try:
            borrowed = borrow_jtag_interface(report)
            report['identity'] = select_neo()
            env = environment()
            env['LD_PRELOAD'] = str(Path('/lib/x86_64-linux-gnu/libz.so.1').resolve()) + ':' + env.get('LD_PRELOAD', '')
            env.update(TMPDIR=private_tmp, CONSOLE_GAO_INSPECTION_TOKEN=token)
            server_env = dict(os.environ, TMPDIR=private_tmp, CONSOLE_GAO_INSPECTION_TOKEN=token)
            log = (out / 'server.log').open('x'); logs.append(log)
            server = subprocess.Popen(['/home/michael/gowin/Programmer/bin/jtagserver', '-local'],
                cwd=out, env=server_env, stdout=log, stderr=log, start_new_session=True)
            children.append(server)
            time.sleep(.7)
            assert server.poll() is None
            command = [str(cli), '-gao', str(GAO), '-device', 'GW5AST-138C',
                       '-cable', 'FT2CH', '-location', '12737', '-out', str(out / 'initial')]
            report['command'] = command
            log = (out / 'cli.log').open('x'); logs.append(log)
            child = subprocess.Popen(command, cwd=out, env=env, stdout=log,
                                     stderr=log, start_new_session=True)
            children.append(child)
            print('GAO_INITIAL_READ_STARTED location=12737 serial=2025041420A', flush=True)
            report['returncode'] = child.wait(timeout=45)
        except BaseException as error:
            report['error'] = repr(error)
            report['timed_out'] = isinstance(error, subprocess.TimeoutExpired)
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, signal.SIG_IGN)
            report['owned_detached_servers'] = stop_owned_children(children, token)
            if borrowed:
                lib, ctx, handle, detached = borrowed
                if detached:
                    report['kernel_driver']['reattach_status'] = lib.libusb_attach_kernel_driver(handle, 0)
                lib.libusb_close(handle)
                lib.libusb_exit(ctx)
            for log in logs: log.close()
            report['outputs'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
                for p in out.glob('initial*') if p.is_file()}
            report['capture_validated'] = False
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report), flush=True)


if __name__ == '__main__': main()
