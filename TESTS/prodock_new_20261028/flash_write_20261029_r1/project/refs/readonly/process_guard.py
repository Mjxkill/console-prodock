"""Single-thread process lifetime for root-only flash reads.

Signal masking reuses the exact frozen SRAM coordinator. This module never
opens a device by itself. The caller supplies an already-reviewed argv while
holding the diagnostic lock. Kernel-uninterruptible children cannot be promised
to exit: bounded cleanup then raises, so the phase cannot report success.
"""
import hashlib
import importlib.util
from pathlib import Path
import signal
import stat
import subprocess

SRAM_SHA = '18a6c2af3b24703f66cf2df2cbf39ecf6589fb633c1d1ce5c6c74f14dcaca52e'


def signal_guard():
    """Load only the pinned local snapshot, without invoking its CLI or I/O."""
    path = Path(__file__).resolve().parent / 'reference/load_sd_candidate.py'
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('SRAM signal-guard reference is not a regular file')
    if hashlib.sha256(path.read_bytes()).hexdigest() != SRAM_SHA:
        raise ValueError('SRAM signal-guard reference SHA differs')
    spec = importlib.util.spec_from_file_location('flash_read_signal_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.deferred_signals


def run_programmer(argv, stdout, timeout, *, spawn=None):
    """Own child before unmasking signals; kill/reap before releasing caller.

The wrapper is pinned and execs the programmer without background children.
The preexec mask restoration is suitable only for this single-thread CLI.
After timeout/interruption, cleanup has a further bounded three seconds.
"""
    defer = signal_guard()
    spawn = spawn or subprocess.Popen
    child = None
    try:
        with defer() as original_mask:
            child = spawn(list(argv), stdout=stdout, stderr=subprocess.STDOUT,
                          preexec_fn=lambda: signal.pthread_sigmask(
                              signal.SIG_SETMASK, original_mask))
        return child.wait(timeout=timeout)
    finally:
        with defer():
            if child is not None:
                try:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=3)
                except BaseException as error:
                    raise RuntimeError('Programmer cleanup failed; process may '
                                       'remain alive, no success claimed') from error
