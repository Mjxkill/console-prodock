"""Contradictory proof and lifecycle tests, no hardware resources."""
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import flash_write as m
import proofs
import program_log
from fixture_factory import Fixture, sha, store, PROGRAM, BACKUP, CAPACITY

SOURCE = Path(__file__).resolve().parent


class Harden(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name, SOURCE)
        self.out = self.f.tests / 'prepared'
        self.run = self.f.tests / 'run'

    def prep(self):
        m.prepare(self.f.request, sha(self.f.request), self.out, root=self.f.root)
        self.plan = self.out / 'plan.json'
        p = bytes.fromhex('060000000001081b3b0000010000000000000000')
        self.f.after = p + BACKUP[len(p):]

    def execute(self, **kw):
        return m.execute(self.plan, sha(self.plan), self.run, root=self.f.root,
                         runner=self.f.runner, guard_factory=lambda root:self.f.guard(), **kw)

    def update_backups(self, mutation):
        doc = json.loads(self.f.backup_result.read_text())
        mutation(doc)
        self.f.req['backups'] = store(self.f.backup_result, doc)
        acc = json.loads(self.f.acceptance.read_text())
        acc['dump_result_sha256'] = sha(self.f.backup_result)
        self.f.req['acceptance'] = store(self.f.acceptance, acc)
        self.f.sync()

    def test_rounded_progress_can_repeat_before_single_done(self):
        for phase in (b'Writing:', b'Reading:'):
            marker = phase + b' [========] 100.00%\n'
            raw = PROGRAM.replace(marker, marker + marker)
            r = program_log.parse_program(raw, jedec='ef4018', sectors=4)
            self.assertTrue(r['write_verified'])

    def test_two_complete_write_phases_are_rejected(self):
        raw = PROGRAM.replace(b'Verifying write', b'Writing: 100.00%\nDone\nVerifying write')
        with self.assertRaises((ValueError, RuntimeError)):
            program_log.parse_program(raw,jedec='ef4018',sectors=4)

    def test_impossible_1100_percent_is_rejected(self):
        raw = PROGRAM.replace(b'100.00%', b'1100.00%')
        with self.assertRaises((ValueError, RuntimeError)):
            program_log.parse_program(raw,jedec='ef4018',sectors=4)

    def test_backup_missing_digest_is_rejected(self):
        self.update_backups(lambda d:d['dumps']['a'].pop('sha256'))
        with self.assertRaises((ValueError, RuntimeError)):self.prep()
        self.assertEqual(self.f.calls,[])

    def test_backup_inconsistent_second_digest_is_rejected(self):
        self.update_backups(lambda d:d['comparison'].update(sha256_b='0'*64))
        with self.assertRaises((ValueError, RuntimeError)):self.prep()

    def test_reused_log_cannot_prove_independent_read(self):
        self.update_backups(lambda d:d['dumps']['b'].update(log=d['dumps']['a']['log']))
        with self.assertRaises((ValueError, RuntimeError)):self.prep()

    def test_dependency_plan_is_actually_bound(self):
        self.prep()
        d=json.loads(self.plan.read_text())
        d['dependencies']['refs/review/offline.py']='0'*64
        store(self.plan,d)
        with self.assertRaises((ValueError,RuntimeError)):self.execute()
        self.assertEqual(self.f.calls,[])

    def test_default_program_is_inspection_only(self):
        self.prep()
        with mock.patch.object(m,'ROOT',self.f.root), \
             mock.patch.object(m,'execute',side_effect=AssertionError('executed')) as execute, \
             contextlib.redirect_stdout(io.StringIO()) as out:
            rc=m.main(['program','--plan',str(self.plan),'--plan-sha',sha(self.plan),'--out',str(self.run)])
        self.assertEqual(rc,0,out.getvalue())
        execute.assert_not_called()
        self.assertFalse(self.run.exists())

    def test_log_open_failure_is_not_program_attempt(self):
        self.prep()
        original=m.proofs.make_output_dir
        def make(root,out):
            path=original(root,out)
            (path/'program.log').write_bytes(b'foreign existing log')
            return path
        with mock.patch.object(m.proofs,'make_output_dir',side_effect=make):
            r=self.execute()
        self.assertFalse(r['program_attempted'],r)
        self.assertEqual(self.f.calls,[])
        self.assertEqual((self.run/'program.log').read_bytes(),b'foreign existing log')

    def test_all_invalid_deadlines_refused_before_program(self):
        self.prep()
        for t in (None,0,-1,1801,math.inf,math.nan,True):
            with self.subTest(timeout=t):
                with self.assertRaises((ValueError,RuntimeError,TypeError)):
                    self.execute(timeout=t)
        self.assertEqual(self.f.calls,[])

    def test_signal_log_reference_survives(self):
        self.prep()
        self.f.program_fault=KeyboardInterrupt('injected')
        r=self.execute()
        self.assertEqual(r['status'],'inconclusive',r)
        info=r['logs']['program']
        self.assertEqual(info['log_sha256'],sha(self.run/'program.log'))
        self.assertIsNone(info['returncode'])
        self.assertEqual(len(self.f.calls),1)

    def test_no_false_claim_if_image_cleanup_fails(self):
        image=self.f.tests/'image.bin'; image.write_bytes(b'not usable')
        with mock.patch.object(Path,'unlink',side_effect=PermissionError('injected')):
            removed=m._discard_image(image)
        self.assertIs(removed,False)
        self.assertTrue(image.exists())


if __name__=='__main__':unittest.main()
