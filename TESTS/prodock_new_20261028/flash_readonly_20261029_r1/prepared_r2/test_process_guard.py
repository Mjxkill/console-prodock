"""Local processes only: reproduce the spawn/signal race, timeout and refusal."""
from pathlib import Path
import os
import json
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager

import flash_readonly as flash
import process_guard as guard
from test_owned import CoordinatorCase, CAPACITY, JEDEC


class Interrupted(BaseException):
    pass


class ProcessTests(unittest.TestCase):
    def test_normal_exit(self):
        with tempfile.TemporaryFile() as log:
            rc = guard.run_programmer(['/usr/bin/python3', '-c', 'print("ok")'], log, 5)
            log.seek(0)
            self.assertEqual((rc, log.read()), (0, b'ok\n'))

    def test_timeout_reaps(self):
        children = []

        def spawn(*args, **kwargs):
            child = subprocess.Popen(*args, **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryFile() as log:
            with self.assertRaises(subprocess.TimeoutExpired):
                guard.run_programmer(['/usr/bin/python3', '-c', 'import time;time.sleep(60)'],
                                     log, .05, spawn=spawn)
        self.assertIsNotNone(children[0].poll())

    def test_signal_before_spawn_returns(self):
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=number):
                children = []
                mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())

                def handler(*_):
                    raise Interrupted('actual local signal')

                def spawn(*args, **kwargs):
                    child = subprocess.Popen(*args, **kwargs)
                    children.append(child)
                    os.kill(os.getpid(), number)
                    return child

                previous = signal.signal(number, handler)
                try:
                    with tempfile.TemporaryFile() as log:
                        with self.assertRaises(Interrupted):
                            guard.run_programmer(['/usr/bin/python3', '-c',
                                                  'import time;time.sleep(60)'],
                                                 log, 5, spawn=spawn)
                    self.assertIsNotNone(children[0].poll())
                    self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), mask)
                finally:
                    signal.signal(number, previous)
                    for child in children:
                        if child.poll() is None:
                            child.kill()
                        child.wait(timeout=5)

    def test_unreapable_child_cannot_pass(self):
        class Stuck:
            def poll(self):
                return None

            def kill(self):
                pass

            def wait(self, timeout):
                raise subprocess.TimeoutExpired('fake kernel stall', timeout)

        with tempfile.TemporaryFile() as log:
            with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
                guard.run_programmer(['unused'], log, 1, spawn=lambda *a, **k: Stuck())

    def test_missing_or_wrong_reference_refused_before_spawn(self):
        with patch.object(guard, 'SRAM_SHA', '0' * 64), patch.object(guard.subprocess, 'Popen') as spawn:
            with tempfile.TemporaryFile() as log:
                with self.assertRaisesRegex(ValueError, 'SHA differs'):
                    guard.run_programmer(['unused'], log, 1)
            spawn.assert_not_called()


class EvidenceTests(CoordinatorCase):
    def test_guard_refusal_does_not_claim_programmer_attempt(self):
        @contextmanager
        def refused():
            raise ValueError('wrong target or missing permission')
            yield

        coordinator = self.coordinator('detect', self.root / 'TESTS/refused', self.runner([]))
        coordinator.guard_factory = refused
        result = coordinator.execute()
        self.assertFalse(result['passed'])
        self.assertFalse(result['programmer_attempted'])
        self.assertNotIn('sram_interrupted', result)
        self.assertTrue(result['sram_interrupt_expected'])
        self.assertEqual(self.state['argv'], [])
        recorded = json.loads((self.root / 'TESTS/refused/detect.json').read_text())
        self.assertFalse(recorded['programmer_attempted'])

    def test_fake_runner_attempt_distinct_from_fpga_observation(self):
        _, _, result = self.run_detect()
        self.assertTrue(result['programmer_attempted'])
        self.assertNotIn('sram_interrupted', result)

    def test_contradictory_record_refused_before_guard(self):
        _, path, original = self.run_detect()
        mutations = {'returncode': 1, 'flash_writes': 1,
                     'loader_sha256': '0' * 64, 'capacity': CAPACITY + 1,
                     'model': 'different model'}
        for key, value in mutations.items():
            with self.subTest(key=key):
                edited = dict(original)
                edited[key] = value
                path.write_text(json.dumps(edited))
                calls, locks = len(self.state['argv']), self.state['entries']
                result = self.coordinator(
                    'dump', self.root / 'TESTS' / ('invalid-' + key), self.runner([]),
                    detection=path, detection_sha=flash.sha256_file(path),
                    jedec=JEDEC, capacity=CAPACITY).execute()
                self.assertFalse(result['passed'])
                self.assertEqual((len(self.state['argv']), self.state['entries']),
                                 (calls, locks))


if __name__ == '__main__':
    unittest.main()
