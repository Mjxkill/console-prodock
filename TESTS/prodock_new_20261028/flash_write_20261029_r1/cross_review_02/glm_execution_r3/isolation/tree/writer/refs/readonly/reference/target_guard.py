#!/usr/bin/env python3
"""Reusable ROOT-only guard; import and command construction perform no I/O.

No CLI executes hardware. Root can hold this context around reviewed commands.
It deliberately reuses load_fpga.devices(), with its module SHA pinned by root.
This guard establishes programmer identity, not runtime/SD/CPU qualification.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import stat
import subprocess

SERIAL = '2025071717'


def select_target(devices):
    matches = [d for d in devices if
               (d.get('idVendor'), d.get('idProduct'), d.get('serial')) ==
               ('0403', '6010', SERIAL)]
    if len(matches) != 1:
        raise ValueError('Expected exactly one FT2232 serial 2025071717')
    return matches[0]


def command(tool, action, *, output=None, size=None, image=None):
    """Return an argv list only. All operations fix the new programmer serial."""
    base = [str(tool), '--usb-serial-num', SERIAL, '-b', 'tangmega138k', '--verbose']
    if action == 'detect':
        return base + ['--write-flash', '--detect']
    if action == 'dump' and output is not None and isinstance(size, int) and size > 0:
        return base + ['--dump-flash', '--file-size', str(size), str(output)]
    if action == 'program' and image is not None:
        return base + ['--write-flash', '--verify', str(image)]
    raise ValueError('Invalid operation/arguments')


def checked_file(path, sha):
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Expected non-symlink regular file')
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError('File SHA mismatch')
    return path


@contextmanager
def guarded_target(tool, tool_sha, loader, loader_sha, *, runtime, runtime_sha):
    """ROOT hardware use only; one lock held across detect/backup/program/readback.

    Caller separately verifies backup, candidate SRAM qualification, and output
    nonexistence. On interruption no automatic programming/retry is attempted.
    """
    if socket.gethostname().split('.')[0] != 'michael-AX15':
        raise ValueError('Wrong host')
    tool = checked_file(tool, tool_sha)
    checked_file(runtime, runtime_sha)
    loader = checked_file(loader, loader_sha)
    fd = os.open('/tmp/prodock-diagnostic.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openFPGALoader', '-C', 'JLinkExe',
                                 '-C', 'openocd', '-o', 'pid=,comm='],
                                capture_output=True, text=True, timeout=5)
        if active.returncode not in (0, 1) or active.stdout.strip():
            raise ValueError('Hardware client present or inventory failed')
        spec = importlib.util.spec_from_file_location('reviewed_fpga_loader', loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = module.devices()
        target = select_target(before)
        node = Path('/dev/bus/usb') / f"{int(target['busnum']):03}" / f"{int(target['devnum']):03}"
        if not os.access(node, os.R_OK | os.W_OK):
            raise ValueError('Programmer permissions missing')
        yield dict(target_serial=SERIAL, target=target, before=before, tool=str(tool))
