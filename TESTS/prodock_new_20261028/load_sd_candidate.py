#!/usr/bin/env python3
"""Prepare or load new Pro Dock SRAM while collecting passive early boot.

Root alone may invoke --run on ax15. One diagnostic lock covers programming
and capture. No thread, flash, CPU JTAG, UART transmission or flush is used.
The child programmer is polled during capture and reaped on every exit path.
Program completion, boot log observations and GPU/cold-boot tests are distinct.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/michael/console-validation-20261001')
SERIAL = '2025071717'
HOST = 'michael-AX15'
TOOL = ROOT / 'bin/openFPGALoader'
RUNTIME = ROOT / 'runtime/openFPGALoader'
TOOL_SHA = '1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066'
RUNTIME_SHA = '101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873'
LOADER_SHA = 'f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4'
COLLECTOR_MANIFEST = '634d7a738265dd49d4b2e9c80c722d3f9a2ca03d159bc3a7ee99f326b27a5d22'
COLLECTOR_FILES = {
    'collector.py': 'e71d3076fc66bd3df583e33f7340f8c979d176befa6658777275d8f6f1b7b7bd',
    'serial_guard.py': '730dc2d2042f7dc303f29d55a385762aa4a08a8179a916b2967fb75f31bd2ae1',
    'boot_log.py': '918ba7a002ad2570fad4991b83241e128da341d55bbc23e20826b76b56aa1dc2',
}


def need(value, text):
    if not value:
        raise RuntimeError(text)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_file(path, expected):
    path = Path(path)
    need(stat.S_ISREG(path.lstat().st_mode), 'Not a regular non-symlink file: ' + str(path))
    need(sha(path) == expected, 'SHA differs: ' + str(path))
    return path


def scoped_path(path, base, *, existing):
    """Reject aliases outside ROOT and symlink components before any hardware."""
    path = Path(path)
    need(path.is_absolute(), 'Absolute path required')
    need('..' not in path.parts, 'Parent traversal refused')
    need(path.is_relative_to(base) and path != base, 'Path outside approved root')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        need(not current.is_symlink(), 'Symlink path component refused')
    resolved = path.resolve(strict=existing)
    need(resolved == path, 'Path is not canonical')
    return path


def validate_args(bit, digest, out, seconds):
    need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Invalid SHA')
    need(isinstance(seconds, (float, int)) and math.isfinite(seconds) and 1 <= seconds <= 120,
         'Total capture/program budget must be 1..120 seconds')
    bit = scoped_path(bit, ROOT, existing=False)
    out = scoped_path(out, ROOT / 'TESTS', existing=False)
    need(bit.suffix == '.fs', 'Only an exact .fs SRAM candidate is accepted')
    need(bit != out and not bit.is_relative_to(out), 'Output cannot contain input')
    return bit, out


def load_dependencies():
    """Imports only already-pinned modules; import itself does not open devices."""
    bundle = HERE / 'autoboot_validation'
    checked_file(bundle / 'manifest.json', COLLECTOR_MANIFEST)
    for name, digest in COLLECTOR_FILES.items():
        checked_file(bundle / name, digest)
    checked_file(HERE / 'load_fpga.py', LOADER_SHA)
    sys.path.insert(0, str(bundle))
    try:
        import serial_guard
        import collector
        need(Path(serial_guard.__file__).resolve() == bundle/'serial_guard.py', 'Wrong guard import')
        need(Path(collector.__file__).resolve() == bundle/'collector.py', 'Wrong collector import')
        collector.preflight(COLLECTOR_MANIFEST)
    finally:
        sys.path.pop(0)
    spec = importlib.util.spec_from_file_location('sd_candidate_fpga_loader', HERE/'load_fpga.py')
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    # capture() imports boot_log lazily; pre-load the exact module without
    # leaving a mutable working-directory import path behind.
    spec = importlib.util.spec_from_file_location('boot_log', bundle/'boot_log.py')
    boot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boot)
    sys.modules['boot_log'] = boot
    return serial_guard, collector, loader


def select_target(devices):
    targets = [d for d in devices if
               (d.get('idVendor'), d.get('idProduct'), d.get('serial')) ==
               ('0403', '6010', SERIAL)]
    need(len(targets) == 1, 'Missing or ambiguous new programmer 2025071717')
    return targets[0]


def command(bit):
    return [str(TOOL), '--usb-serial-num', SERIAL, '-b', 'tangmega138k',
            '-m', '--verbose', str(bit)]


def validate_program_log(raw, returncode):
    """Gowin programSRAM can return void after failure; exit zero alone is weak.

    Require the exact verbose post-program status with DONE_FINAL, correct
    physical ID, and no explicit FAIL/Error diagnostic. Historical auto_boot
    bits describe the previous flash attempt and are not parsed as a FAIL line.
    """
    text = raw.decode('utf-8', errors='replace').replace('\r', '\n')
    statuses = re.findall(r'^after program sram: displayReadReg ([0-9a-fA-F]{8})\s*$', text, re.M)
    ids = re.findall(r'^\s*idcode 0x([0-9a-fA-F]+)\s*$', text, re.M)
    failure = bool(re.search(r'\bFAIL\b|\bError\b|\bERROR\b', text))
    final = int(statuses[-1], 16) if statuses else None
    passed = bool(returncode == 0 and text.startswith('write to ram\n') and
                  ids == ['1081b'] and final is not None and final & 0x2000 and
                  not final & 0x8000f and not failure and 'write to flash' not in text)
    return dict(configuration_completed=passed, returncode=returncode,
                final_status=final, status_done_final=bool(final is not None and final & 0x2000),
                explicit_failure=failure, physical_idcodes=ids,
                proof_scope='tool DONE_FINAL/status; not independent FPGA configuration readback')


def save_json(path, result):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    os.replace(temporary, path)


@contextmanager
def deferred_signals():
    """Close the Popen→owner-assignment and child-reaping signal windows."""
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK,
                                    {signal.SIGINT, signal.SIGTERM, signal.SIGHUP})
    try:
        yield blocked
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)


class ProgramWatch:
    """Single-thread child supervision, updated by the UART capture loop."""
    def __init__(self, child, log, report, out, deadline, clock=time.monotonic):
        self.child, self.log, self.report, self.out = child, log, report, out
        self.deadline, self.clock, self.observed = deadline, clock, False

    def poll(self, *, enforce=True):
        rc = self.child.poll()
        if rc is not None and not self.observed:
            self.observed = True
            self.report.update(validate_program_log(self.log.read_bytes(), rc))
            self.report['program_finished_unix'] = time.time()
            save_json(self.out/'program_result.json', self.report)
        if enforce:
            if rc is None and self.clock() >= self.deadline:
                raise TimeoutError('SRAM programmer deadline')
            if self.observed and not self.report['configuration_completed']:
                raise RuntimeError('SRAM configuration not confirmed; see program.log')
        return rc

    def reap(self, stop_group):
        """No orphan on ordinary failure/signal; report a kernel-level exception.

        A process stuck uninterruptibly in the kernel cannot be guaranteed to
        exit within userspace deadlines. Never label that cleanup successful.
        """
        try:
            if self.child.poll() is None:
                stop_group(self.child, signal.SIGTERM)
                try:
                    self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    stop_group(self.child, signal.SIGKILL)
                    self.child.wait(timeout=2)
            else:
                self.child.wait(timeout=0)
            self.poll(enforce=False)
            self.report['programmer_reaped'] = True
        except BaseException as exc:
            self.report['programmer_reaped'] = False
            self.report['programmer_cleanup_error'] = repr(exc)


class FreshPassive:
    """Capture only a fresh new-board USB enumeration after programming starts.

    If the previous enumeration never disappears/changes, capture is
    inconclusive rather than accepting buffered output from an earlier boot.
    No fallback to 7.3 is permitted. Frozen PassiveUART owns/validates its fd.
    """
    def __init__(self, uart, guard, watch, initial):
        self.uart, self.guard, self.watch, self.initial = uart, guard, watch, initial
        self.saw_absent = initial is None
        self.fresh = False
        self.fresh_identity = None

    def open(self, timeout=5):
        self.watch.poll()
        try:
            identity = self.guard.snapshot()
        except FileNotFoundError:
            self.saw_absent = True
            raise
        if not self.fresh:
            changed = self.initial is not None and (
                identity['busnum'], identity['devnum']) != (
                self.initial['busnum'], self.initial['devnum'])
            if not self.saw_absent and not changed:
                raise FileNotFoundError('Waiting for new-board USB re-enumeration')
        result = self.uart.open(timeout=min(timeout, .5))
        self.fresh = True
        self.fresh_identity = result
        return result

    def read(self, size, timeout):
        self.watch.poll()
        return self.uart.read(size, min(timeout, .1))

    def connected(self):
        return self.uart.connected()

    def close(self):
        self.uart.close()


def run_session(out, bit, digest, seconds, guard, collector, loader, *,
                spawn=subprocess.Popen, clock=time.monotonic, sleep=time.sleep,
                stop_group=lambda p, s: os.killpg(p.pid, s), check_permissions=os.access):
    """Root-only orchestration. Dependency injection is exclusively for fakes."""
    report = dict(target_serial=SERIAL, bitstream_sha256=digest, bitstream=str(bit),
                  configuration_completed=False, flash_writes=0, sd_writes=0,
                  cpu_jtag_access=False, uart_tx_bytes=0, gpu_tested=False,
                  powercycle_validated=False, log_checks_passed=False,
                  programmer_reaped=False, started_unix=time.time(),
                  tool_sha256=TOOL_SHA, runtime_sha256=RUNTIME_SHA,
                  loader_sha256=LOADER_SHA, collector_manifest_sha256=COLLECTOR_MANIFEST,
                  port=str(guard.PORT), seconds_budget=seconds)
    watcher = None
    io = None
    started = clock()
    save_json(out/'program_result.json', report)
    try:
        with guard.diagnostic_lock():
            active = subprocess.run(['ps', '-C', 'openFPGALoader', '-C', 'JLinkExe',
                                     '-C', 'openocd', '-o', 'pid=,comm='],
                                    capture_output=True, text=True, timeout=5)
            need(active.returncode in (0, 1) and not active.stdout.strip(), 'Another JTAG client or failed ps')
            report['before'] = loader.devices()
            target = select_target(report['before'])
            node = Path('/dev/bus/usb') / f"{int(target['busnum']):03}" / f"{int(target['devnum']):03}"
            need(check_permissions(node, os.R_OK | os.W_OK), 'Programmer permissions missing')
            try:
                initial = guard.snapshot()
                guard.quiet_owner(subprocess.run(['fuser', str(guard.PORT)], capture_output=True, timeout=2))
            except FileNotFoundError:
                initial = None
            report['initial_console'] = initial
            try:
                uart = guard.PassiveUART()  # validates support before programming
                report['command'] = command(bit)
                with (out/'program.log').open('xb', buffering=0) as log:
                    # Defer signals until an owner can reap the process. Popen
                    # execs a fixed wrapper, which itself execs the pinned ELF.
                    with deferred_signals() as original_mask:
                        child = spawn(report['command'], stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True,
                                      preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, original_mask))
                        watcher = ProgramWatch(child, out/'program.log', report, out,
                                               min(started+seconds, clock()+90), clock)
                    io = FreshPassive(uart, guard, watcher, initial)
                    report['programmer_pid'] = child.pid
                    save_json(out/'program_result.json', report)
                    remaining = started + seconds - clock()
                    need(remaining > 0, 'No capture time remains')
                    report['capture'] = collector.capture(io, out, remaining, clock, sleep)
                    report['fresh_console_observed'] = io.fresh
                    report['fresh_console_identity'] = io.fresh_identity
                    report['game_launch_observed'] = report['capture']['game_launch_observed']
            finally:
                # Both process reaping and descriptor close happen before the
                # diagnostic lock is released, including pre-capture failures.
                with deferred_signals():
                    if watcher is not None:
                        watcher.reap(stop_group)
                    if io is not None:
                        io.close()
                if 'capture' in report:
                    report['log_checks_passed'] = bool(report['configuration_completed'] and
                        report['programmer_reaped'] and io.fresh and report['capture']['log_checks_passed'])
    except BaseException as exc:
        report['error'] = repr(exc)
    finally:
        report['elapsed_seconds'] = clock()-started
        report['finished_unix'] = time.time()
        report['passed'] = bool(report['log_checks_passed'] and not report.get('error') and
                                not report.get('uart_cleanup_error'))
        save_json(out/'program_result.json', report)
        save_json(out/'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bit', required=True, type=Path)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    bit, out = validate_args(args.bit, args.sha, args.out, args.seconds)
    guard, collector, loader = load_dependencies()
    if not args.run:
        print(json.dumps(dict(prepared=True, hardware_access=False, command=command(bit),
                              bitstream_sha256=args.sha, out=str(out), target_serial=SERIAL,
                              port=str(guard.PORT), seconds=args.seconds, flash_writes=0)))
        return 0
    need(socket.gethostname().split('.')[0] == HOST, 'Wrong execution host')
    scoped_path(bit, ROOT, existing=True)
    checked_file(bit, args.sha)
    checked_file(TOOL, TOOL_SHA)
    checked_file(RUNTIME, RUNTIME_SHA)
    out.mkdir(parents=True, exist_ok=False)
    (out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
    def stop(sig, frame):
        raise InterruptedError('Signal ' + str(sig))
    previous = {s:signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        result = run_session(out, bit, args.sha, args.seconds, guard, collector, loader)
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)
    print(json.dumps({k:result.get(k) for k in ('configuration_completed','log_checks_passed',
                    'game_launch_observed','gpu_tested','powercycle_validated','passed','error')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
