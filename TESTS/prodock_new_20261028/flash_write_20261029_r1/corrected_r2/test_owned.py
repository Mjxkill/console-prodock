"""Independent behavior tests; target source supplied by FLASH_WRITER_SOURCE.

All programmer/target boundaries are fakes; no UART/JTAG/USB or network.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fixture_factory import Fixture, BACKUP, CAPACITY, PROGRAM, sha, store

SOURCE = Path(os.environ.get('FLASH_WRITER_SOURCE', Path(__file__).parent)).resolve()
sys.path.insert(0, str(SOURCE))
m = importlib.import_module('flash_write')
PAYLOAD = bytes.fromhex('060000000001081b3b0000010000000000000000')


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name, SOURCE)
        self.plan_out = self.f.tests / 'prepared'
        self.run_out = self.f.tests / 'write'

    def prepare(self):
        m.prepare(self.f.request, sha(self.f.request), self.plan_out, root=self.f.root)
        self.plan = self.plan_out / 'plan.json'
        self.assertTrue(self.plan.is_file())
        self.f.after = PAYLOAD + BACKUP[len(PAYLOAD):]

    def execute(self, **kwargs):
        return m.execute(self.plan, sha(self.plan), self.run_out,
                         root=self.f.root, runner=kwargs.pop('runner', self.f.runner),
                         guard_factory=lambda _root: self.f.guard(), **kwargs)

    def expect_refused_prepare(self):
        with self.assertRaises((ValueError, RuntimeError, OSError)):
            self.prepare()
        self.assertEqual(self.f.calls, [])

    def test_success_uses_one_program_one_full_dump(self):
        self.prepare()
        r = self.execute()
        self.assertEqual(r['status'], 'coldboot_pending', r)
        self.assertTrue(r['full_readback_matches'], r)
        self.assertEqual(len(self.f.calls), 2)
        self.assertIn('--write-flash', self.f.calls[0])
        self.assertIn('--verify', self.f.calls[0])
        self.assertIn('--dump-flash', self.f.calls[1])
        self.assertEqual(int(self.f.calls[1][self.f.calls[1].index('--file-size')+1]), CAPACITY)
        for key in ('boot_tested', 'gpu_tested', 'powercycle_tested'):
            self.assertIs(r[key], False)
        self.assertFalse(self.f.held)

    def test_program_failure_never_retries_or_dumps(self):
        self.prepare()
        def runner(argv, out, timeout):
            self.f.runner(argv, out, timeout)
            return 3
        r = self.execute(runner=runner)
        self.assertNotEqual(r['status'], 'coldboot_pending', r)
        self.assertFalse(r['full_readback_matches'])
        self.assertEqual(len(self.f.calls), 1)
        self.assertFalse(self.f.held)

    def test_program_timeout_retains_unknown_flash_state(self):
        self.prepare()
        self.f.program_fault = subprocess.TimeoutExpired(['fake'], 1)
        r = self.execute(timeout=1)
        self.assertEqual(r['status'], 'inconclusive', r)
        self.assertEqual(len(self.f.calls), 1)
        self.assertTrue((self.run_out / 'result.json').is_file())
        self.assertFalse(self.f.held)

    def test_program_interrupt_preserves_result_without_retry(self):
        self.prepare()
        self.f.program_fault = KeyboardInterrupt('fake signal')
        r = self.execute()
        self.assertEqual(r['status'], 'inconclusive', r)
        self.assertEqual(len(self.f.calls), 1)
        self.assertFalse(self.f.held)

    def test_program_cleanup_fault_cannot_succeed(self):
        self.prepare()
        self.f.program_fault = RuntimeError('Programmer cleanup failed')
        r = self.execute()
        self.assertNotEqual(r['status'], 'coldboot_pending', r)
        self.assertFalse(r['full_readback_matches'])
        self.assertEqual(len(self.f.calls), 1)

    def test_error_after_completion_is_not_ignored(self):
        self.prepare()
        def runner(argv, out, timeout):
            rc = self.f.runner(argv, out, timeout)
            out.write(b'Error: fail to disable flash access\n')
            return rc
        r = self.execute(runner=runner)
        self.assertNotEqual(r['status'], 'coldboot_pending', r)
        self.assertEqual(len(self.f.calls), 1)

    def test_tail_outside_program_region_is_verified(self):
        self.prepare()
        bad = bytearray(self.f.after)
        bad[-19] ^= 0x80
        self.f.after = bytes(bad)
        r = self.execute()
        self.assertNotEqual(r['status'], 'coldboot_pending', r)
        self.assertFalse(r['full_readback_matches'])
        self.assertEqual(len(self.f.calls), 2)

    def test_truncated_readback_with_success_log_is_refused(self):
        self.prepare()
        self.f.after = self.f.after[:-1]
        r = self.execute()
        self.assertNotEqual(r['status'], 'coldboot_pending', r)
        self.assertFalse(r['full_readback_matches'])

    def test_changed_accepted_fs_refuses_before_program(self):
        self.prepare()
        self.f.fs.write_bytes(self.f.fs.read_bytes() + b'0')
        with self.assertRaises((ValueError, RuntimeError, OSError)):
            self.execute()
        self.assertEqual(self.f.calls, [])

    def test_missing_permission_cannot_prepare(self):
        a = json.loads(self.f.acceptance.read_text())
        a['permission_to_program'] = False
        self.f.req['acceptance'] = store(self.f.acceptance, a)
        self.f.sync()
        self.expect_refused_prepare()

    def test_old_target_cannot_prepare(self):
        self.f.req['target_serial'] = '2023112818'
        self.f.sync()
        self.expect_refused_prepare()

    def test_false_sram_pass_is_rejected(self):
        a = json.loads(self.f.sram.read_text())
        a['error'] = 'programmer cleanup failed'
        self.f.req['sram_result'] = store(self.f.sram, a)
        acc = json.loads(self.f.acceptance.read_text())
        acc['sram_result_sha256'] = sha(self.f.sram)
        self.f.req['acceptance'] = store(self.f.acceptance, acc)
        self.f.sync()
        self.expect_refused_prepare()

    def test_backup_same_inode_is_rejected(self):
        a = self.f.tests / 'backup/backup_a.bin'
        b = self.f.tests / 'backup/backup_b.bin'
        b.unlink()
        b.hardlink_to(a)
        self.expect_refused_prepare()

    def test_output_parent_symlink_is_refused(self):
        p = self.f.tests / 'link'
        p.symlink_to(self.f.tests, target_is_directory=True)
        self.plan_out = p / 'prepared'
        self.expect_refused_prepare()

    def test_failed_prepare_does_not_replace_existing_evidence(self):
        self.plan_out.mkdir()
        marker = self.plan_out / 'keep.txt'
        marker.write_text('old proof')
        self.expect_refused_prepare()
        self.assertEqual(marker.read_text(), 'old proof')


if __name__ == '__main__':
    unittest.main()
