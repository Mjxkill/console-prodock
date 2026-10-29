#!/usr/bin/env python3
"""Inspect the vendor GAO cable selector in a private display, under Neo lock.

No bitstream argument and no automatic Start/Force. The operator must select
the identified FPGA cable before any capture. All children started here are
terminated on exit; unrelated processes are neither reused nor stopped.
"""
import argparse
import ctypes
import ctypes.util
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from gowin_toolchain import IDE, environment

GAO = ROOT / 'tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao'
GAO_SHA = '0116f9daba8ac6d88af534f426d9f168eae56a669c48df9372114a2795fbb7e6'


def stop_owned_children(children, token):
    # A QProcess may detach jtagserver from the GUI's process group. Its
    # inherited per-invocation token identifies only a server launched here.
    detached = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal(): continue
        try:
            command = (proc / 'cmdline').read_bytes().split(b'\0')[0]
            if Path(os.fsdecode(command)).name != 'jtagserver': continue
            if ('CONSOLE_GAO_INSPECTION_TOKEN=' + token).encode() not in (proc / 'environ').read_bytes().split(b'\0'): continue
            detached.append(int(proc.name))
        except (OSError, ValueError): pass
    for pid in detached:
        try: os.kill(pid, signal.SIGTERM)
        except ProcessLookupError: pass
    for child in reversed(children):
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: child.wait(timeout=3)
        except subprocess.TimeoutExpired: pass
        # The leader may exit before another member of its own group.
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        child.wait()
    for pid in detached:
        # Recheck ownership immediately before a possible final signal.
        try:
            if ('CONSOLE_GAO_INSPECTION_TOKEN=' + token).encode() in Path('/proc', str(pid), 'environ').read_bytes().split(b'\0'):
                os.kill(pid, signal.SIGKILL)
        except (OSError, ValueError): pass
    deadline = time.monotonic() + 3
    while True:
        alive = []
        for pid in detached:
            try:
                state = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[0]
                if state not in ('Z', 'X'): alive.append(pid)
            except FileNotFoundError: pass
        if not alive: break
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned detached servers still alive after cleanup: ' + str(alive))
        time.sleep(.05)
    return detached


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--start-server', action='store_true',
                   help='Start this installation\'s server explicitly with its own runtime libraries')
    args = p.parse_args()
    assert hashlib.sha256(GAO.read_bytes()).hexdigest() == GAO_SHA
    assert (IDE / 'bin/gao_analyzer').is_file()
    assert Path('/usr/bin/Xvfb').is_file()
    assert ctypes.util.find_library('X11') and ctypes.util.find_library('Xtst')
    out = args.out.resolve()
    assert out.is_relative_to(HERE) and not out.exists()
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, bitstream_argument=False,
                              gao_sha256=GAO_SHA, out=str(out))))
        return
    out.mkdir()
    token = uuid.uuid4().hex
    children = []
    logs = []
    connection = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Operator interrupted: ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, interrupted)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
            '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='],
            capture_output=True, text=True, check=False)
        assert active.returncode == 1 and not active.stdout.strip(), 'Existing hardware operator/server'
        devices = []
        for d in Path('/sys/bus/usb/devices').iterdir():
            if (d / 'serial').is_file() and (d / 'serial').read_text().strip() == '2025041420':
                devices.append({key: (d / key).read_text().strip()
                    for key in ('serial', 'product', 'idVendor', 'idProduct', 'busnum', 'devnum')})
        assert len(devices) == 1 and devices[0]['idVendor'] == '0403' and devices[0]['idProduct'] == '6010'
        (out / 'identity.json').write_text(json.dumps(dict(neo=devices[0], gao_sha256=GAO_SHA,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            bitstream_argument=False, initial_capture_not_started_by_script=True), indent=2) + '\n')
        try:
            rfd, wfd = os.pipe()
            log = (out / 'xvfb.log').open('xb'); logs.append(log)
            xvfb = subprocess.Popen(['/usr/bin/Xvfb', '-displayfd', str(wfd), '-screen', '0',
                '1600x1000x24', '-nolisten', 'tcp'], pass_fds=(wfd,), stdout=log,
                stderr=log, start_new_session=True)
            children.append(xvfb); os.close(wfd)
            assert select.select([rfd], [], [], 10)[0], 'Private display startup timeout'
            display = os.read(rfd, 128).decode().strip(); os.close(rfd)
            assert display.isdecimal()
            for name in ('tmp', 'runtime', 'config'):
                (out / name).mkdir(mode=0o700)
            env = environment(); env.update(DISPLAY=':' + display, QT_QPA_PLATFORM='xcb',
                CONSOLE_GAO_INSPECTION_TOKEN=token, TMPDIR=str(out / 'tmp'),
                XDG_RUNTIME_DIR=str(out / 'runtime'), XDG_CONFIG_HOME=str(out / 'config'))
            if args.start_server:
                server_env = dict(os.environ)
                for name in ('DISPLAY', 'QT_QPA_PLATFORM', 'CONSOLE_GAO_INSPECTION_TOKEN',
                             'TMPDIR', 'XDG_RUNTIME_DIR', 'XDG_CONFIG_HOME'):
                    server_env[name] = env[name]
                log = (out / 'server.log').open('xb'); logs.append(log)
                server = subprocess.Popen(['/home/michael/gowin/Programmer/bin/jtagserver', '-local'],
                    cwd=out, env=server_env, stdout=log, stderr=log, start_new_session=True)
                children.append(server)
                time.sleep(.7)
                assert server.poll() is None, 'Server startup failed; see server.log'
            log = (out / 'gao_gui.log').open('xb'); logs.append(log)
            gui = subprocess.Popen([str(IDE / 'bin/gao_analyzer'), '-gao', str(GAO),
                '-series', 'GW5AST', '-device', 'GW5AST-138C'], cwd=out, env=env,
                stdout=log, stderr=log, start_new_session=True)
            children.append(gui)
            x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
            xtst = ctypes.CDLL(ctypes.util.find_library('Xtst'))
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]; x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
            xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            connection = x11.XOpenDisplay((':' + display).encode()); assert connection
            print(json.dumps(dict(ready=True, display=':' + display, gui_pid=gui.pid,
                commands=['screenshot', 'click x y', 'key keycode', 'close'])), flush=True)
            count = 0
            for line in sys.stdin:
                parts = line.strip().split()
                assert gui.poll() is None, 'GAO window exited'
                if parts == ['close']: break
                if parts == ['screenshot']:
                    count += 1
                    path = out / ('screen_%02d.png' % count)
                    subprocess.run(['/usr/bin/import', '-display', ':' + display, '-window', 'root',
                        str(path)], check=True, timeout=10)
                    print(json.dumps(dict(screenshot=str(path))), flush=True)
                elif len(parts) == 3 and parts[0] == 'click':
                    x, y = map(int, parts[1:]); assert 0 <= x < 1600 and 0 <= y < 1000
                    xtst.XTestFakeMotionEvent(connection, 0, x, y, 0)
                    xtst.XTestFakeButtonEvent(connection, 1, 1, 0)
                    xtst.XTestFakeButtonEvent(connection, 1, 0, 0); x11.XFlush(connection)
                elif len(parts) == 2 and parts[0] == 'key':
                    key = int(parts[1]); assert 8 <= key <= 255
                    xtst.XTestFakeKeyEvent(connection, key, 1, 0)
                    xtst.XTestFakeKeyEvent(connection, key, 0, 0); x11.XFlush(connection)
                else: raise ValueError('Unknown operator command')
        finally:
            for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                signal.signal(signum, signal.SIG_IGN)
            if connection: x11.XCloseDisplay(connection)
            detached = stop_owned_children(children, token)
            for log in logs: log.close()
            (out / 'cleanup.json').write_text(json.dumps(dict(
                owned_child_pids=[c.pid for c in children], owned_detached_server_pids=detached,
                child_returncodes=[c.returncode for c in children]), indent=2) + '\n')


if __name__ == '__main__':
    main()
