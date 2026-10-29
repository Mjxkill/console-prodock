#!/usr/bin/env python3
"""Read the initial GAO capture of the exact, user-loaded N56r10.

The installed CLI branches to initial read when capture_init_data_enabled=true.
No reprogram, ordinary rearm, auto-run, or force is requested. Bounded timeout;
only owned child processes are stopped. Raw CSV timing unit needs correction.
"""
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(HERE.parent))
from gowin_toolchain import IDE, environment
from probe_route9_led_compare import usb_identity
from inspect_gao_gui import stop_owned_children

GAO = ROOT / 'tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao'
GAO_SHA = '0116f9daba8ac6d88af534f426d9f168eae56a669c48df9372114a2795fbb7e6'
BIT_SHA = '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_neo():
    identity = usb_identity()
    assert identity['programmer_busdev'] == '3:28'
    library = ctypes.CDLL('/home/michael/gowin/Programmer/bin/libftd2xx.so')
    count = ctypes.c_ulong(0)
    assert library.FT_CreateDeviceInfoList(ctypes.byref(count)) == 0 and count.value < 20
    entries = []
    for index in range(count.value):
        flags, kind, ident, location = [ctypes.c_ulong(0) for _ in range(4)]
        serial, desc = ctypes.create_string_buffer(128), ctypes.create_string_buffer(128)
        handle = ctypes.c_void_p()
        status = library.FT_GetDeviceInfoDetail(index, ctypes.byref(flags), ctypes.byref(kind),
                    ctypes.byref(ident), ctypes.byref(location), serial, desc, ctypes.byref(handle))
        if serial.value == b'2025041420A':
            assert status == 0 and location.value == 12737 and ident.value == 0x04036010
            entries.append(dict(index=index, location=location.value,
                                serial=serial.value.decode(), description=desc.value.decode()))
    assert len(entries) == 1 and entries[0]['description'] == 'USB Debugger A'
    return dict(usb=identity, selected=entries[0])


def main():
    out = HERE / 'r10_initial_read_01'
    assert not out.exists()
    assert sha(GAO) == GAO_SHA and 'capture_init_data_enabled="true"' in GAO.read_text()
    cli = IDE / 'bin/gao_sh'
    assert sha(cli) == '4717a2afa56893861de161207bc2c4f094f53227099763ebfa2f0025ab72515b'
    loaded = json.loads((HERE.parent / 'r10_gao_load_trial/result.json').read_text())
    assert loaded['configured'] and loaded['bitstream_sha256'] == BIT_SHA and not loaded['fallback_restored']
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
        report['identity'] = select_neo()
        out.mkdir()
        private_tmp = tempfile.mkdtemp(prefix='console-gao-read-')
        report['runtime_dir'] = private_tmp
        try:
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
            for log in logs: log.close()
            report['outputs'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
                for p in out.glob('initial*') if p.is_file()}
            report['capture_validated'] = False
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report), flush=True)


if __name__ == '__main__': main()
