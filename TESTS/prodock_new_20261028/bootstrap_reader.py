#!/usr/bin/env python3
"""Prepare/read back a fresh staging helper, then extract FM4A; never launch it.

Root must establish old-board CPU/FPGA/console binding and ordinary shell first.
No append retry after an ambiguous UART result. No flush, reset, FPGA or SD I/O.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import termios
import tty

PORT = Path('/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.3:1.0')
USB = Path('/sys/bus/usb/devices/3-7.3')
TRANSPORT = Path('/tmp/festival_persistent_20261028_prepared_r1')
LOCK = '/tmp/prodock-diagnostic.lock'
HOST = 'michael-AX15'
PROGRAMMER = '2023112818'
KERNEL = '6.12.112-prodock-luma3d-g3d1-r1'
READER_SHA = 'eaebf381b6f14da1e8355857d8427a6ae5698c3ce8f2a6cd92bf6d2ec7d3ae85'
READER_BYTES = 13032
REMOTE = '/tmp/stage_reader'
GAME = '/tmp/luma3d-fm4a'
TRANSPORT_SHA = {
    'probe_channel.py': '20e97d025274cb7caf2aa35b72f9b59fd1002f0a0fc3380f64fac978a3cf9c2d',
    'support.py': '45cf2c8cddcbe8a903f6bf73dca552512052883d88670ffa889815133127c29b',
    'bootstrap.py': '042ad3b207b71f01234c2c42e101dad0c8282d3f347fab73b649bdc409edd33a',
    'sender.py': '94ad0faa516f65b6e3fc8505f596c22f2c12605468369ebe8061c475566533a2',
    'sender_base.py': 'a9fd98347ab14c227f4ed641a6511ee795458e1b2efa63333b38a4d55ef421d2',
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def imports():
    """Pin existing transport code before import; old PID helpers are not called."""
    for name, expected in TRANSPORT_SHA.items():
        p = TRANSPORT / name
        assert not p.is_symlink() and sha(p) == expected, name
    sys.path.insert(0, str(TRANSPORT))
    import probe_channel
    return probe_channel


@contextmanager
def open_channel(out):
    """Exclusive topology-pinned 115200/raw descriptor, with no flush/toggle.

    Yields the existing Channel. Caller owns shell confirmation and commands.
    Every exit closes logs and UART before releasing the diagnostic lock.
    """
    assert socket.gethostname().split('.')[0] == HOST
    out = Path(out)
    assert out.is_dir()
    transport = imports()
    identity = {k: (USB / k).read_text().strip() for k in
                ('idVendor', 'idProduct', 'serial', 'product', 'busnum', 'devnum', 'speed')}
    assert (identity['idVendor'], identity['idProduct'], identity['serial']) == ('359f', '2011', '11252024')
    (out / 'usb.json').write_text(json.dumps(identity, indent=2) + '\n')
    assert stat.S_ISCHR(os.stat(PORT).st_mode)
    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        owner = subprocess.run(['fuser', str(PORT)], capture_output=True)
        assert owner.returncode == 1 and not owner.stdout.strip() and not owner.stderr.strip(), 'UART busy'
        uart = transport.UART.__new__(transport.UART)
        uart.fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        channel = None
        try:
            fcntl.ioctl(uart.fd, termios.TIOCEXCL)
            before = termios.tcgetattr(uart.fd)
            tty.setraw(uart.fd, termios.TCSANOW)
            attrs = termios.tcgetattr(uart.fd)
            attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
            attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(uart.fd, termios.TCSANOW, attrs)
            assert termios.tcgetattr(uart.fd)[4:6] == [termios.B115200] * 2
            (out / 'termios.json').write_text(json.dumps({'before': repr(before), 'raw_115200': True}) + '\n')
            channel = transport.Channel(uart, out)
            yield channel
        finally:
            if channel:
                channel.close()
            uart.close()


def commands(data):
    """Single append per96-byte chunk; no retry/continue state after ambiguity."""
    assert len(data) == READER_BYTES and hashlib.sha256(data).hexdigest() == READER_SHA
    lines = [f"(set -C; umask 077; : > {REMOTE}) && printf '\\nRX2_BOOT_CREATED\\n'"]
    for seq, start in enumerate(range(0, len(data), 96)):
        octal = ''.join('\\%03o' % value for value in data[start:start + 96])
        lines.append(f"printf '{octal}' >> {REMOTE} && printf '\\nRX2_BOOT_{seq:04d}\\n'")
    lines.append(f"printf '\\nRX2_BOOT_READ_BEGIN\\n' && od -b -v {REMOTE} && printf '\\nRX2_BOOT_READ_END\\n'")
    return lines


def execute(channel, data):
    transport = imports()
    channel.initial_shell()
    raw = channel.run('kernel', 'uname -r && cat /proc/mounts && ls -l /proc/[0-9]*/exe')
    assert re.search(rb'^' + KERNEL.encode() + rb'\r?$', raw, re.M), 'Kernel differs'
    assert b'tmpfs /tmp tmpfs ' in raw, '/tmp differs'
    assert not re.search(rb'^l[^\r\n]* /proc/[0-9]+/exe -> [^\r\n]*luma3d-', raw, re.M), 'Game already running'
    raw = channel.run('space', 'LC_ALL=C df -Pk /tmp')
    rows = [r.split() for r in raw.replace(b'\r', b'').splitlines() if r.split() and r.split()[-1] == b'/tmp']
    assert len(rows) == 1 and len(rows[0]) == 6 and rows[0][0] == b'tmpfs' and rows[0][3].isdigit()
    assert int(rows[0][3]) >= 24576, 'Need24MiB tmpfs for extracted ELF and margin'
    lines = commands(data)
    for index, command in enumerate(lines):
        raw = channel.run(f'bootstrap_{index:03d}', command, timeout=120 if index == len(lines) - 1 else 30)
        if index == len(lines) - 1:
            got = transport.bootstrap.validate_readback({'elf_bytes': len(data), 'elf_sha256': READER_SHA}, raw)
            assert got == data, 'Full helper readback differs'
        else:
            marker = 'RX2_BOOT_CREATED' if index == 0 else f'RX2_BOOT_{index-1:04d}'
            assert len(re.findall(rb'^' + marker.encode() + rb'\r?$', raw, re.M)) == 1, 'Chunk marker absent/duplicated'
    channel.run('chmod_verified', 'chmod 700 ' + REMOTE)
    raw = channel.run('extract_fm4a', REMOTE + ' ' + GAME, timeout=120)
    assert len(re.findall(rb'^STAGE_FM4A_OK bytes=16640496 crc=fa358bf4\r?$', raw, re.M)) == 1
    return {'reader_full_readback_sha256': READER_SHA, 'reader_bytes': len(data),
            'game': GAME, 'game_bytes': 16640496, 'game_crc32': 'fa358bf4',
            'game_sha256_hardware_measured': False, 'game_launched': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--out', type=Path)
    p.add_argument('--run', action='store_true')
    p.add_argument('--old-board-bound', action='store_true', help='Root attests fresh physical CPU/FPGA/console binding')
    a = p.parse_args();data = a.elf.read_bytes();lines = commands(data)
    if not a.run:
        print(json.dumps({'prepared': True, 'hardware': False, 'chunks': len(lines)-2, 'reader_sha256': READER_SHA, 'programmer': PROGRAMMER, 'port': str(PORT)}));return
    assert a.old_board_bound and a.out, 'Root binding attestation and new output required'
    a.out.mkdir(parents=True, exist_ok=False)
    result = {'passed': False, 'hardware': True, 'programmer': PROGRAMMER, 'port': str(PORT), 'game_launched': False, 'fpga_writes': 0, 'sd_writes': 0}
    def stop(sig, frame):
        raise InterruptedError('Signal ' + str(sig))
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        with open_channel(a.out) as channel:
            result.update(execute(channel, data));result['passed'] = True
    except BaseException as exc:
        result['error'] = repr(exc);result['automatic_retry'] = False
    finally:
        for sig, handler in previous.items():signal.signal(sig, handler)
        (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result));raise SystemExit(not result['passed'])

if __name__ == '__main__':
    main()
