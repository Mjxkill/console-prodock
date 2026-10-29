"""Integration tests of flash_readonly at the real runner boundary.

No hardware, no shell and no network are used here. Exactly two boundaries are
replaced by fakes:

* the reviewed guard context (the global lock and the programmer identity),
* the runner that executes the reviewed argv and writes the tool output.

Everything else stays real: the coordinator, the log grammar, the exclusive
output directory, the file length/SHA checks, the JSON evidence and the
finally block that finishes the result on a failure or on an interruption.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import flash_readonly as fr

# A small but honest geometry: 4 sectors of 64 KiB, displayed as 2Mb.
SECTORS = 4
CAPACITY = SECTORS * 65536
JEDEC = 'ef4018'
MODEL = 'winbond W25Q128'
PAYLOAD = bytes(range(256)) * (CAPACITY // 256)

DETECT_LOG = (b'found 1 devices\n'
              b'index 0:\n'
              b'\tidcode 0x1081b\n'
              b'Detect flash:\n'
              b'JEDEC ID: 0xef4018\n'
              b'Detected: winbond W25Q128 4 sectors size: 2Mb\n'
              b'Done\n')

DUMP_LOG = (b'found 1 devices\n'
            b'index 0:\n'
            b'\tidcode 0x1081b\n'
            b'JEDEC ID: 0xef4018\n'
            b'Detected: winbond W25Q128 4 sectors size: 2Mb\n'
            b'dump flash (May take time)\n'
            b'Open dump file DONE\n'
            b'Read flash 100.00%\n'
            b'Done\n')

DUMP_LOG_WITHOUT_ID = (b'found 1 devices\n'
                       b'index 0:\n'
                       b'\tidcode 0x1081b\n'
                       b'dump flash (May take time)\n'
                       b'Open dump file DONE\n'
                       b'Read flash 100.00%\n'
                       b'Done\n')


class FakeGuard:
    """Stand-in for the reviewed guarded_target() context manager."""

    def __init__(self, state, on_enter=None):
        self.state = state
        self.on_enter = on_enter

    def __enter__(self):
        self.state['entries'] += 1
        self.state['held'] += 1
        if self.on_enter is not None:
            self.on_enter()
        return {'target_serial': fr.SERIAL,
                'target': {'serial': fr.SERIAL, 'idVendor': fr.VENDOR,
                           'idProduct': fr.PRODUCT, 'busnum': 1, 'devnum': 4,
                           'path': '1-1.4'},
                'board': fr.BOARD}

    def __exit__(self, *exc_info):
        self.state['held'] -= 1
        self.state['exits'] += 1
        return False


class FakeRunner:
    """Stand-in for the real subprocess runner.

    A step is a dict with the optional keys 'log' (bytes written into the
    tool log), 'file' (bytes written into the dump file, exactly like the
    tool does), 'rc' (return code) and 'raise' (an exception to raise).
    """

    def __init__(self, state, steps):
        self.state = state
        self.steps = list(steps)

    def __call__(self, argv, stdout, timeout):
        self.state['argv'].append(list(argv))
        self.state['timeouts'].append(timeout)
        self.state['held_when_called'].append(self.state['held'])
        step = self.steps.pop(0) if self.steps else {}
        payload = step.get('log')
        if payload:
            stdout.write(payload)
        if step.get('file') is not None:
            Path(argv[-1]).write_bytes(step['file'])
        if 'raise' in step:
            raise step['raise']
        return step.get('rc', 0)


class CoordinatorCase(unittest.TestCase):
    """Common scaffolding: a fake root, a fake guard and a fake runner."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'TESTS').mkdir()
        self.state = {'entries': 0, 'exits': 0, 'held': 0, 'argv': [],
                      'timeouts': [], 'held_when_called': []}

    # -- fakes ------------------------------------------------------------
    def guard(self, on_enter=None):
        return lambda: FakeGuard(self.state, on_enter)

    def runner(self, steps):
        return FakeRunner(self.state, steps)

    # -- helpers ----------------------------------------------------------
    def coordinator(self, phase, out_dir, runner, **kwargs):
        return fr.Coordinator(phase=phase, out_dir=out_dir, root=self.root,
                              runner=runner, guard_factory=self.guard(),
                              **kwargs)

    def run_detect(self, name='detect-1', steps=None):
        """Run a fake detect pass and return (out_dir, detection path)."""
        out = self.root / 'TESTS' / name
        steps = steps if steps is not None else [{'log': DETECT_LOG, 'rc': 0}]
        result = self.coordinator('detect', out, self.runner(steps)).execute()
        self.assertTrue(result['passed'], result.get('error'))
        return out, out / 'detect.json', result


class DetectPhase(CoordinatorCase):
    """The detect pass and its JSON evidence."""

    def test_detect_records_full_evidence(self):
        out, detection, result = self.run_detect()
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['jedec'], JEDEC)
        self.assertEqual(result['model'], MODEL)
        self.assertEqual(result['sectors'], SECTORS)
        self.assertEqual(result['capacity'], CAPACITY)
        self.assertEqual(result['flash_writes'], 0)
        self.assertTrue(result['sram_interrupted'])
        self.assertFalse(result['boot'])
        self.assertFalse(result['gpu'])
        self.assertFalse(result['powercycle'])
        self.assertTrue((out / 'detect.log').exists())

        evidence = json.loads(detection.read_text())
        self.assertTrue(evidence['passed'])
        self.assertEqual(evidence['phase'], 'detect')
        self.assertEqual(evidence['tool_sha256'], fr.TOOL_SHA)
        self.assertEqual(evidence['runtime_sha256'], fr.RUNTIME_SHA)
        self.assertEqual(evidence['target']['serial'], fr.SERIAL)
        self.assertEqual(evidence['target']['idVendor'], fr.VENDOR)
        self.assertEqual(evidence['target']['idProduct'], fr.PRODUCT)
        self.assertEqual(evidence['log_sha256'],
                         fr.sha256_file(out / 'detect.log'))
        self.assertTrue(evidence['sram_interrupted'])
        self.assertEqual(evidence['flash_writes'], 0)

    def test_detect_refuses_a_nonzero_exit(self):
        out = self.root / 'TESTS' / 'detect-rc'
        result = self.coordinator('detect', out,
                                  self.runner([{'log': DETECT_LOG, 'rc': 3}])).execute()
        self.assertFalse(result['passed'])
        self.assertEqual(result['returncode'], 3)
        self.assertTrue((out / 'detect.log').exists())

    def test_detect_refuses_a_log_without_identification(self):
        out = self.root / 'TESTS' / 'detect-noid'
        log = b'found 1 devices\nindex 0:\n\tidcode 0x1081b\nDone\n'
        result = self.coordinator('detect', out,
                                  self.runner([{'log': log, 'rc': 0}])).execute()
        self.assertFalse(result['passed'])
        self.assertTrue((out / 'detect.log').exists())

    def test_detect_refuses_a_log_with_an_error_word(self):
        out = self.root / 'TESTS' / 'detect-err'
        log = DETECT_LOG + b'Failed to read flash\n'
        result = self.coordinator('detect', out,
                                  self.runner([{'log': log, 'rc': 0}])).execute()
        self.assertFalse(result['passed'])
        self.assertIn('error', result['error'].lower())

    def test_prepare_opens_nothing_and_states_the_consequence(self):
        out = self.root / 'TESTS' / 'prepared'
        plan = self.coordinator('detect', out, self.runner([])).prepare()
        self.assertFalse(plan['will_run'])
        self.assertTrue(plan['sram_interrupted'])
        self.assertEqual(plan['flash_writes'], 0)
        self.assertEqual(plan['commands'][0][-1], '--detect')
        self.assertTrue(any('SRAM' in text for text in plan['consequences']))
        self.assertFalse(out.exists())
        self.assertEqual(self.state['argv'], [])


class DumpPhase(CoordinatorCase):
    """The two read-only dumps bound to a validated detection."""

    def test_detect_then_two_dumps_succeed(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-ok'
        runner = self.runner([{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
                              {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD}])
        result = self.coordinator(
            'dump', out, runner, detection=detection,
            detection_sha=fr.sha256_file(detection), jedec=JEDEC,
            capacity=CAPACITY).execute()

        self.assertTrue(result['passed'], result.get('error'))
        self.assertTrue(result['comparison']['matching'])
        self.assertEqual(result['dumps']['a']['bytes'], CAPACITY)
        self.assertEqual(result['dumps']['b']['bytes'], CAPACITY)
        self.assertEqual(result['dumps']['a']['sha256'],
                         result['dumps']['b']['sha256'])
        self.assertTrue((out / 'backup_a.bin').exists())
        self.assertTrue((out / 'backup_b.bin').exists())
        self.assertTrue((out / 'backup_a.log').exists())
        self.assertTrue((out / 'backup_b.log').exists())
        self.assertEqual((out / 'backup_a.bin').read_bytes(), PAYLOAD)

        evidence = json.loads((out / 'dump.json').read_text())
        self.assertTrue(evidence['passed'])
        self.assertEqual(evidence['capacity'], CAPACITY)

    def test_one_lock_covers_both_dumps(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-lock'
        runner = self.runner([{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
                              {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD}])
        self.coordinator('dump', out, runner, detection=detection,
                         detection_sha=fr.sha256_file(detection), jedec=JEDEC,
                         capacity=CAPACITY).execute()
        # One guard entry for the whole dump phase and the lock held on every
        # single tool invocation.
        self.assertEqual(self.state['entries'], 2)      # detect + dump phase
        self.assertEqual(self.state['exits'], 2)
        self.assertEqual(self.state['held_when_called'], [1, 1, 1])

    def test_two_separate_invocations_and_output_files(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-two'
        runner = self.runner([{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
                              {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD}])
        self.coordinator('dump', out, runner, detection=detection,
                         detection_sha=fr.sha256_file(detection), jedec=JEDEC,
                         capacity=CAPACITY).execute()
        dumps = [argv for argv in self.state['argv'] if '--dump-flash' in argv]
        self.assertEqual(len(dumps), 2)
        self.assertNotEqual(dumps[0][-1], dumps[1][-1])
        self.assertTrue(dumps[0][-1].endswith('backup_a.bin'))
        self.assertTrue(dumps[1][-1].endswith('backup_b.bin'))
        # Two independent files, not one file copied twice.
        first = os.stat(out / 'backup_a.bin')
        second = os.stat(out / 'backup_b.bin')
        self.assertNotEqual(first.st_ino, second.st_ino)

    def test_detection_mismatch_refuses_before_any_command(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-mismatch'
        before = len(self.state['argv'])
        cases = ({'detection_sha': '0' * 64},
                 {'jedec': 'ef9999'},
                 {'capacity': CAPACITY + 1})
        for case in cases:
            kwargs = {'detection': detection, 'detection_sha': fr.sha256_file(detection),
                      'jedec': JEDEC, 'capacity': CAPACITY}
            kwargs.update(case)
            result = self.coordinator('dump', out, self.runner([]), **kwargs).execute()
            self.assertFalse(result['passed'], case)
            self.assertIn('error', result)
        # No command was ever built and no evidence was created.
        self.assertEqual(len(self.state['argv']), before)
        self.assertFalse(out.exists())

    def test_dump_failure_variants(self):
        _detect_out, detection, _result = self.run_detect()
        variants = (
            # exit 0 but a short dump file
            ('short', [{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD[:100]}]),
            # a failed log
            ('failed-log', [{'log': DUMP_LOG + b'Failed to read flash\n',
                             'rc': 0, 'file': PAYLOAD}]),
            # a log without the flash identification
            ('no-id', [{'log': DUMP_LOG_WITHOUT_ID, 'rc': 0, 'file': PAYLOAD}]),
            # a nonzero exit
            ('rc', [{'log': DUMP_LOG, 'rc': 1, 'file': PAYLOAD}]),
        )
        for name, steps in variants:
            out = self.root / 'TESTS' / ('dump-bad-' + name)
            result = self.coordinator(
                'dump', out, self.runner(steps), detection=detection,
                detection_sha=fr.sha256_file(detection), jedec=JEDEC,
                capacity=CAPACITY).execute()
            self.assertFalse(result['passed'], name)
            self.assertTrue((out / 'backup_a.log').exists(), name)
            self.assertFalse(result.get('comparison'), name)

    def test_second_dump_timeout_keeps_the_first_file_and_log(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-timeout'
        runner = self.runner([
            {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
            {'log': DUMP_LOG[:40], 'rc': 0,
             'raise': subprocess.TimeoutExpired(cmd='openFPGALoader', timeout=900)},
        ])
        result = self.coordinator(
            'dump', out, runner, detection=detection,
            detection_sha=fr.sha256_file(detection), jedec=JEDEC,
            capacity=CAPACITY).execute()

        self.assertFalse(result['passed'])
        self.assertTrue(result['dumps']['b']['timeout'])
        self.assertIn('--dump-flash', result['dumps']['b']['command'])
        self.assertTrue(result['dumps']['b']['command'][-1].endswith('backup_b.bin'))
        # The first dump and its log survive the timeout of the second one.
        self.assertEqual((out / 'backup_a.bin').read_bytes(), PAYLOAD)
        self.assertTrue((out / 'backup_a.log').exists())
        self.assertTrue((out / 'backup_b.log').exists())
        self.assertTrue((out / 'backup_b.log').read_bytes())
        # The failed result is written and it is not a success.
        evidence = json.loads((out / 'dump.json').read_text())
        self.assertFalse(evidence['passed'])
        self.assertTrue(evidence['dumps']['b']['timeout'])

    def test_second_dump_interruption_keeps_the_first_file_and_log(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-signal'
        runner = self.runner([
            {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
            {'log': DUMP_LOG[:40], 'rc': 0, 'raise': KeyboardInterrupt()},
        ])
        result = self.coordinator(
            'dump', out, runner, detection=detection,
            detection_sha=fr.sha256_file(detection), jedec=JEDEC,
            capacity=CAPACITY).execute()

        self.assertFalse(result['passed'])
        self.assertIn('backup_b.bin', result['dumps']['b']['command'][-1])
        self.assertEqual((out / 'backup_a.bin').read_bytes(), PAYLOAD)
        self.assertTrue((out / 'backup_b.log').exists())
        evidence = json.loads((out / 'dump.json').read_text())
        self.assertFalse(evidence['passed'])

    def test_mismatched_second_dump_is_refused(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-differ'
        other = bytes((byte + 1) % 256 for byte in PAYLOAD[:4096]) + PAYLOAD[4096:]
        runner = self.runner([{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
                              {'log': DUMP_LOG, 'rc': 0, 'file': other}])
        result = self.coordinator(
            'dump', out, runner, detection=detection,
            detection_sha=fr.sha256_file(detection), jedec=JEDEC,
            capacity=CAPACITY).execute()
        self.assertFalse(result['passed'])
        self.assertIn('differ', result['error'].lower())
        self.assertTrue((out / 'backup_a.bin').exists())
        self.assertTrue((out / 'backup_b.bin').exists())

    def test_preexisting_output_directory_is_refused_without_overwriting(self):
        out = self.root / 'TESTS' / 'existing'
        out.mkdir(parents=True)
        evidence = out / 'detect.json'
        evidence.write_bytes(b'previous proof preserved')
        result = self.coordinator('detect', out, self.runner([])).execute()
        self.assertFalse(result['passed'])
        self.assertEqual(evidence.read_bytes(), b'previous proof preserved')
        self.assertEqual(self.state['argv'], [])

    def test_second_run_into_the_same_directory_does_not_overwrite(self):
        out, detection, _result = self.run_detect()
        first = detection.read_bytes()
        result = self.coordinator('detect', out, self.runner([])).execute()
        self.assertFalse(result['passed'])
        self.assertEqual(detection.read_bytes(), first)

    def test_failed_result_write_may_not_report_a_success(self):
        out = self.root / 'TESTS' / 'detect-nowrite'

        def sabotage():
            # A directory where the result JSON belongs: the write must fail.
            (out / 'detect.json').mkdir()

        coordinator = fr.Coordinator(phase='detect', out_dir=out, root=self.root,
                                    runner=self.runner([{'log': DETECT_LOG, 'rc': 0}]),
                                    guard_factory=self.guard(sabotage))
        result = coordinator.execute()
        self.assertFalse(result['passed'])
        self.assertIn('result_write_error', result)


class PinnedIdentities(CoordinatorCase):
    """The runtime path, the reviewed guard and the allowlisted commands."""

    def test_runtime_path_is_exact(self):
        coordinator = fr.Coordinator(phase='detect',
                                    out_dir=fr.ROOT / 'TESTS' / 'review-only')
        self.assertEqual(str(coordinator.runtime),
                         str(fr.ROOT / 'runtime' / 'openFPGALoader'))
        self.assertNotIn('bin', coordinator.runtime.parts)

    def test_guard_receives_the_pinned_paths(self):
        captured = {}

        class GuardModule:
            @staticmethod
            def guarded_target(tool, tool_sha, loader, loader_sha, *,
                               runtime, runtime_sha):
                captured.update(tool=tool, tool_sha=tool_sha, loader=loader,
                                loader_sha=loader_sha, runtime=runtime,
                                runtime_sha=runtime_sha)
                return FakeGuard(self.state)

        original = fr.load_target_guard
        fr.load_target_guard = lambda module_dir=None: GuardModule
        try:
            with fr.default_guard_factory(self.root) as identity:
                self.assertEqual(identity['target_serial'], fr.SERIAL)
        finally:
            fr.load_target_guard = original

        self.assertEqual(str(captured['tool']),
                         str(self.root / 'bin' / 'openFPGALoader'))
        self.assertEqual(str(captured['runtime']),
                         str(self.root / 'runtime' / 'openFPGALoader'))
        self.assertEqual(str(captured['loader']),
                         str(self.root / 'TESTS' / 'prodock_new_20261028' / 'load_fpga.py'))
        self.assertEqual(captured['tool_sha'], fr.TOOL_SHA)
        self.assertEqual(captured['runtime_sha'], fr.RUNTIME_SHA)
        self.assertEqual(captured['loader_sha'], fr.LOADER_SHA)

    def test_reviewed_guard_is_the_only_imported_copy(self):
        guard = fr.load_target_guard()
        self.assertTrue(hasattr(guard, 'guarded_target'))
        self.assertTrue(hasattr(guard, 'command'))
        self.assertEqual(fr.GUARD_SHA, fr.sha256_file(
            Path(fr.__file__).resolve().parent / fr.GUARD_RELATIVE))

    def test_no_command_outside_the_allowlist(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-allowlist'
        runner = self.runner([{'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD},
                              {'log': DUMP_LOG, 'rc': 0, 'file': PAYLOAD}])
        self.coordinator('dump', out, runner, detection=detection,
                         detection_sha=fr.sha256_file(detection), jedec=JEDEC,
                         capacity=CAPACITY).execute()

        forbidden = ('--bulk-erase', '--unprotect-flash', '--erase',
                     '--verify', '--program')
        for argv in self.state['argv']:
            self.assertEqual(argv[0], str(self.root / 'bin' / 'openFPGALoader'))
            self.assertEqual(argv[argv.index('--usb-serial-num') + 1], fr.SERIAL)
            self.assertEqual(argv[argv.index('-b') + 1], fr.BOARD)
            self.assertIn('--verbose', argv)
            for flag in forbidden:
                self.assertNotIn(flag, argv)
            if '--write-flash' in argv:
                # The only allowed write flag is the non writing detect mode.
                self.assertIn('--detect', argv)
                self.assertEqual(argv[-1], '--detect')
            if '--dump-flash' in argv:
                self.assertEqual(argv[argv.index('--file-size') + 1],
                                 str(CAPACITY))
                self.assertNotIn('--write-flash', argv)

    def test_prepare_of_the_dump_phase_after_a_fake_detect(self):
        _detect_out, detection, _result = self.run_detect()
        out = self.root / 'TESTS' / 'dump-plan'
        coordinator = self.coordinator(
            'dump', out, self.runner([]), detection=detection,
            detection_sha=fr.sha256_file(detection), jedec=JEDEC,
            capacity=CAPACITY)
        before = len(self.state['argv'])
        plan = coordinator.prepare()
        self.assertEqual(len(plan['commands']), 2)
        self.assertEqual(plan['commands'][0][plan['commands'][0].index('--file-size') + 1],
                         str(CAPACITY))
        self.assertEqual(plan['detection']['capacity'], CAPACITY)
        self.assertTrue(plan['sram_interrupted'])
        # Prepare opens no resource and creates no file.
        self.assertFalse(out.exists())
        self.assertEqual(len(self.state['argv']), before)


if __name__ == '__main__':
    unittest.main()
