#!/usr/bin/env python3
"""Failure-flow tests; no devices or children are opened."""
import json
from pathlib import Path
import signal
import unittest
import trial_coupled_startup as trial


class FakeIO:
    def __init__(self,report,fail):self.report,self.fail,self.calls=report,set(fail),[]
    def called(self,kind,name):
        self.calls.append((kind,name))
        if name in self.fail:raise RuntimeError(name)
    def observe(self,name,code,marker):self.called('observe',name);return marker
    def camera(self,name):self.called('camera',name)
    def program(self,name,path,digest):
        self.report.update(last_programmed_sha256=None,left_startup_verified=False)
        self.called('program',name)
        self.report['last_programmed_sha256']=digest


class Cases(unittest.TestCase):
    def setUp(self):self.signals={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    def tearDown(self):
        for sig,handler in self.signals.items():signal.signal(sig,handler)
    def run_case(self,*fail):
        report=dict(candidate_sha256='candidate',last_programmed_sha256=trial.prior.t.R19_SHA,
                    candidate_startup_verified=False,left_startup_verified=False)
        io=FakeIO(report,fail);error=None
        try:trial.execute(io,report,lambda:None,Path('candidate.fs'))
        except BaseException as exc:error=exc
        return report,io.calls,error
    def test_guard_failure_never_programs(self):
        r,c,e=self.run_case('r19_initial_guard');self.assertIsNotNone(e)
        self.assertEqual(c,[('observe','r19_initial_guard')])
    def test_success_is_one_program_and_camera_before_dmi(self):
        r,c,e=self.run_case();self.assertIsNone(e);self.assertTrue(r['candidate_startup_verified'])
        self.assertEqual([n for k,n in c if k=='program'],['program_coupled'])
        self.assertLess(c.index(('camera','coupled_before_dmi')),c.index(('observe','coupled_startup')))
        self.assertEqual(r['last_programmed_sha256'],'candidate')
    def test_program_and_dmi_failure_restore_once(self):
        for fault in ('program_coupled','coupled_startup'):
            with self.subTest(fault=fault):
                r,c,e=self.run_case(fault);self.assertIsNotNone(e)
                self.assertEqual(c.count(('program','restore_r19')),1)
                self.assertFalse(r['candidate_startup_verified']);self.assertTrue(r['left_startup_verified'])
                self.assertEqual(r['last_programmed_sha256'],trial.prior.t.R19_SHA)
    def test_restore_failure_not_retried_or_declared_verified(self):
        r,c,e=self.run_case('coupled_startup','restore_r19');self.assertIsNotNone(e)
        self.assertEqual(c.count(('program','restore_r19')),1)
        self.assertFalse(r['left_startup_verified']);self.assertIsNone(r['last_programmed_sha256'])
    def test_restore_guard_failure_keeps_programmed_distinct_from_verified(self):
        r,c,e=self.run_case('coupled_startup','restored_guard');self.assertIsNotNone(e)
        self.assertEqual(r['last_programmed_sha256'],trial.prior.t.R19_SHA)
        self.assertFalse(r['left_startup_verified']);self.assertIn('fallback_error',r)
    def test_guard_has_no_memory_write_or_resume(self):
        code=trial.prior.check_code(0)
        for token in ('write_memory','load_image','dump_image','resume','reset halt','reset run'):
            self.assertNotIn(token,code)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    out=Path(__file__).with_name('startup_controller_test_01.json')
    assert not out.exists()
    out.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,hardware_access=False,
                       controller_sha256=trial.prior.t.sha(Path(trial.__file__)),
                       test_sha256=trial.prior.t.sha(Path(__file__)),
                       reused_io_sha256=trial.prior.t.sha(Path(trial.prior.__file__))),indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
