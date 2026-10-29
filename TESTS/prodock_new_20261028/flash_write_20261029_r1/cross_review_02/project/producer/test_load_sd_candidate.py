#!/usr/bin/env python3
"""Fake hardware integration of the real coordinator + frozen boot collector.

No USB, SSH, JTAG, or serial file descriptor is opened. The guard and subprocess
boundary are fake; collector.capture(), FreshPassive and supervision are real.
"""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import load_sd_candidate as c

G, COLLECTOR, LOADER = c.load_dependencies()
SPEC = importlib.util.spec_from_file_location('boot_fixture', c.HERE/'autoboot_validation/project/test_boot_log.py')
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
GOOD = FIXTURE.GOOD
LOG = (c.HERE/'recovery_evidence/fpga_01/program.log').read_bytes()
TARGET = dict(idVendor='0403', idProduct='6010', serial='2025071717', busnum='3', devnum='22')


class Clock:
    def __init__(self): self.t = 0
    def now(self): return self.t
    def sleep(self, duration): self.t += duration


class Child:
    pid = 99999999
    def __init__(self, guard, log, finish, rc):
        self.guard, self.log, self.finish, self.final_rc = guard, log, finish, rc
        self.returncode = None
        self.reaped = False
        self.written = False
    def poll(self):
        if self.returncode is None and self.guard.clock.now() >= self.finish:
            self.returncode = self.final_rc
        if self.returncode is not None and not self.written:
            self.log.write_bytes(LOG if self.returncode == 0 else b'write to ram\nFAIL\n')
            self.written = True
        return self.returncode
    def wait(self, timeout):
        if self.poll() is None:
            raise subprocess.TimeoutExpired('fake programmer', timeout)
        self.reaped = True
        return self.returncode


class UART:
    def __init__(self, guard):
        self.guard, self.opened, self.sent, self.closes = guard, False, False, 0
    def open(self, timeout=5):
        assert self.guard.locked
        identity = self.guard.snapshot()
        self.opened = True
        self.guard.events.append(('uart_open', self.guard.clock.now()))
        return identity
    def read(self, n, timeout):
        assert self.opened and self.guard.locked
        self.guard.clock.sleep(timeout)
        if self.guard.interrupt and self.guard.clock.now() >= .6:
            raise InterruptedError('fake SIGTERM')
        if not self.sent:
            self.sent = True
            self.guard.events.append(('boot_read', self.guard.clock.now()))
            return GOOD
        return b''
    def connected(self): return True
    def close(self):
        self.opened = False
        self.closes += 1
    def write(self, data): raise AssertionError('UART transmission forbidden')


class Guard:
    PORT = G.PORT
    def __init__(self, clock, *, absent=False, stale=False, old=False, initial=False, interrupt=False):
        self.clock, self.absent, self.stale, self.old = clock, absent, stale, old
        self.initial, self.interrupt = initial, interrupt
        self.locked = False
        self.events = []
        self.uart = UART(self)
        self.child = None
    @contextmanager
    def diagnostic_lock(self):
        assert not self.locked
        self.locked = True
        self.events.append(('lock', self.clock.now()))
        try: yield
        finally:
            if self.child is not None:
                assert self.child.reaped, 'Child left alive when lock released'
            assert not self.uart.opened, 'UART must close under lock'
            self.events.append(('unlock', self.clock.now()))
            self.locked = False
    def snapshot(self):
        if self.absent or (not self.initial and self.clock.now() < .2):
            raise FileNotFoundError
        identity = dict(usb_path=str(G.USB), port=str(G.PORT), idVendor='359f',
                        idProduct='2011', serial='11252024', speed='480', tty='ttyACM8',
                        tty_usb_parent=str(G.USB.resolve()), rdev=123, busnum='3',
                        devnum='2' if self.stale or self.clock.now()<.5 else '3')
        if self.old:
            identity['port'] = str(G.PORT).replace('7.1', '7.3')
        return G.validate_identity(identity)
    def quiet_owner(self, result): G.quiet_owner(result)
    def PassiveUART(self): return self.uart
    def stop(self, proc, sig):
        assert self.locked
        self.events.append(('signal', int(sig)))
        proc.returncode = -int(sig)


class Tests(unittest.TestCase):
    def session(self, *, devices=None, finish=1, rc=0, seconds=2, capture=COLLECTOR,
                spawn_error=False, signal_during_spawn=False, **kwargs):
        clock = Clock()
        guard = Guard(clock, **kwargs)
        loader = SimpleNamespace(devices=lambda: [TARGET] if devices is None else devices)
        def spawn(argv, **kw):
            assert guard.locked
            self.assertEqual(argv[1:3], ['--usb-serial-num', '2025071717'])
            self.assertIn('-m', argv)
            self.assertNotIn('--write-flash', argv)
            self.assertTrue(kw['start_new_session'])
            self.assertTrue(callable(kw['preexec_fn']))
            if spawn_error: raise OSError('fake exec failure')
            guard.child = Child(guard, Path(kw['stdout'].name), finish, rc)
            if signal_during_spawn:
                os.kill(os.getpid(), signal.SIGTERM)
            return guard.child
        def run(argv, **kw):
            if argv[0] in ('ps', 'fuser'):
                return SimpleNamespace(returncode=1, stdout='', stderr='')
            raise AssertionError('Unplanned subprocess: ' + repr(argv))
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'run', run):
            out = Path(tmp)
            result = c.run_session(out, c.ROOT/'TESTS/candidate.fs', 'a'*64, seconds,
                guard, capture, loader, spawn=spawn, clock=clock.now, sleep=clock.sleep,
                stop_group=guard.stop, check_permissions=lambda p, mode: True)
            self.assertEqual(json.loads((out/'result.json').read_text()), result)
            self.assertEqual(json.loads((out/'program_result.json').read_text()), result)
            if 'capture' in result:
                for segment in result['capture']['segments']:
                    self.assertEqual((out/segment['file']).stat().st_size, segment['bytes'])
        self.assertFalse(guard.locked)
        self.assertEqual(result['flash_writes'], 0)
        self.assertEqual(result['uart_tx_bytes'], 0)
        self.assertFalse(result['gpu_tested'])
        self.assertFalse(result['powercycle_validated'])
        self.assertLessEqual(clock.now(), seconds+.001)
        return result, guard

    def test_early_boot_is_captured_before_programmer_exit(self):
        result, guard = self.session()
        self.assertTrue(result['passed'])
        self.assertTrue(result['configuration_completed'])
        read_time = next(t for event,t in guard.events if event == 'boot_read')
        self.assertLess(read_time, 1)
        self.assertTrue(guard.child.reaped)

    def test_existing_enumeration_never_qualifies(self):
        result, guard = self.session(initial=True, stale=True)
        self.assertTrue(result['configuration_completed'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['capture']['bytes'], 0)
        self.assertFalse(any(e == 'uart_open' for e,t in guard.events))

    def test_changed_devnum_is_fresh(self):
        result, guard = self.session(initial=True)
        self.assertTrue(result['passed'])
        opened = next(t for event,t in guard.events if event == 'uart_open')
        self.assertGreaterEqual(opened, .5)

    def test_no_uart_keeps_load_result(self):
        result, guard = self.session(absent=True)
        self.assertTrue(result['configuration_completed'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['capture']['segments'], [])
        self.assertTrue(guard.child.reaped)

    def test_old_or_ambiguous_programmer_before_spawn(self):
        old = dict(TARGET, serial='2023112818')
        for devices in ([old], [TARGET,TARGET], []):
            result, guard = self.session(devices=devices)
            self.assertIsNone(guard.child)
            self.assertFalse(result['configuration_completed'])
            self.assertIn('ambiguous', result['error'])

    def test_old_console_refused_before_spawn(self):
        result, guard = self.session(old=True, initial=True)
        self.assertIsNone(guard.child)
        self.assertFalse(result['passed'])

    def test_program_failure_preserves_log_and_reaps(self):
        result, guard = self.session(rc=1)
        self.assertFalse(result['configuration_completed'])
        self.assertFalse(result['capture']['capture_completed'])
        self.assertTrue(guard.child.reaped)
        self.assertFalse(result['passed'])

    def test_timeout_terminates_under_lock(self):
        result, guard = self.session(finish=999, absent=True)
        self.assertFalse(result['configuration_completed'])
        self.assertTrue(guard.child.reaped)
        self.assertIn(('signal', int(signal.SIGTERM)), guard.events)

    def test_interrupt_before_child_exit_reaps_and_saves_capture(self):
        result, guard = self.session(interrupt=True, finish=999)
        self.assertFalse(result['passed'])
        self.assertGreater(result['capture']['bytes'], 0)
        self.assertFalse(result['capture']['capture_completed'])
        self.assertTrue(guard.child.reaped)

    def test_uncaught_capture_exception_reaps_under_lock(self):
        def crash(*a): raise RuntimeError('fake unexpected capture failure')
        result, guard = self.session(capture=SimpleNamespace(capture=crash), finish=999)
        self.assertFalse(result['passed'])
        self.assertTrue(guard.child.reaped)
        self.assertIn('unexpected', result['error'])

    def test_spawn_failure_has_final_report(self):
        result, guard = self.session(spawn_error=True)
        self.assertFalse(result['passed'])
        self.assertIn('exec failure', result['error'])

    def test_real_signal_between_spawn_and_owner_assignment(self):
        def stop(sig, frame): raise InterruptedError('real test SIGTERM')
        previous = signal.signal(signal.SIGTERM, stop)
        try:
            result, guard = self.session(signal_during_spawn=True, finish=999)
        finally:
            signal.signal(signal.SIGTERM, previous)
        self.assertFalse(result['passed'])
        self.assertTrue(guard.child.reaped)
        self.assertIn('real test SIGTERM', result['error'])

    def test_real_child_signal_mask_and_reaping(self):
        # Local Python child only; it cannot access a board. Its default TERM
        # must work, rather than inheriting the temporarily blocked parent mask.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            log = out/'program.log'
            log.write_bytes(b'')
            report = {'configuration_completed': False}
            with c.deferred_signals() as mask:
                child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                    start_new_session=True,
                    preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
                watch = c.ProgramWatch(child, log, report, out, float('inf'))
            try:
                watch.reap(lambda p,s: os.killpg(p.pid, s))
                self.assertTrue(report['programmer_reaped'])
                self.assertEqual(child.returncode, -int(signal.SIGTERM))
            finally:
                if child.poll() is None:
                    child.kill(); child.wait(timeout=2)

    def test_real_log_and_silent_zero_failure(self):
        self.assertTrue(c.validate_program_log(LOG, 0)['configuration_completed'])
        for raw in (LOG.replace(b'after program sram:', b'missing status:'),
                    LOG.replace(b'00026220', b'00024220'), LOG + b'\nFAIL\n',
                    LOG.replace(b'idcode 0x1081b', b'idcode 0x12345')):
            self.assertFalse(c.validate_program_log(raw, 0)['configuration_completed'])

    def test_argument_scope_and_budgets(self):
        for bit in ('/tmp/new.fs', str(c.ROOT/'TESTS/../escape.fs'), str(c.ROOT/'TESTS/x.bin')):
            with self.assertRaises(RuntimeError):
                c.validate_args(Path(bit), 'a'*64, c.ROOT/'TESTS/new', 120)
        for seconds in (0, -1, float('nan'), float('inf'), 121):
            with self.assertRaises(RuntimeError):
                c.validate_args(c.ROOT/'TESTS/x.fs', 'a'*64, c.ROOT/'TESTS/new', seconds)
        c.validate_args(c.ROOT/'TESTS/x.fs', 'a'*64, c.ROOT/'TESTS/new', 120)


if __name__ == '__main__':
    unittest.main()
