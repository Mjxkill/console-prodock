#!/usr/bin/env python3
"""Control-flow and filesystem tests only; no devices opened or child executed."""
import copy
import json
from pathlib import Path
import re
import signal
import tempfile
import unittest
from unittest.mock import patch
import warm_mode1_trial as w


class FakeIO:
    def __init__(self, report, fail=()):
        self.report, self.fail, self.calls = report, set(fail), []
    def called(self, kind, name):
        self.calls.append((kind,name))
        if name in self.fail:raise RuntimeError(name)
    def observe(self, name, code, marker):self.called('observe',name);return marker
    def camera(self, name):self.called('camera',name)
    def send(self, name, before_frame=None, after_frame=None):
        self.called('send',name);self.report[name]={'receipt':'unknown','frame_hex':w.FRAME.hex()}
        if before_frame is not None:before_frame()
        self.called('frame',name)
        if after_frame is not None:after_frame()
        self.called('close',name)
    def program(self, name, path, digest):
        self.report['last_programmed_sha256']=None
        self.report['left_startup_verified']=False
        self.called('program',name)
        self.report['last_programmed_sha256']=digest


class TrialTests(unittest.TestCase):
    def setUp(self):self.handlers={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    def tearDown(self):
        for sig,handler in self.handlers.items():signal.signal(sig,handler)
    def trial(self,fail=()):
        r={'candidate_sha256':'CANDIDATE','last_programmed_sha256':w.t.R19_SHA,
           'left_startup_verified':False,'diagnostic_complete':False}
        io=FakeIO(r,fail);saved=[];error=None
        try:w.execute(io,r,lambda:saved.append(copy.deepcopy(r)),Path('candidate.fs'))
        except BaseException as e:error=e
        return r,io.calls,error,saved
    def test_initial_guard_failure_never_mutates(self):
        r,c,e,_=self.trial(['r19_initial_guard'])
        self.assertIsNotNone(e);self.assertEqual(c,[('observe','r19_initial_guard')])
        self.assertEqual(r['last_programmed_sha256'],w.t.R19_SHA)
    def test_marker_failure_restores_without_uart_or_candidate(self):
        for fail in ('r19_seed_ncp','r19_witness_before_uart'):
            with self.subTest(fail=fail):
                r,c,e,_=self.trial([fail]);self.assertIsNotNone(e)
                self.assertFalse(any(k=='send' for k,_ in c))
                self.assertEqual([n for k,n in c if k=='program'],['restore_r19'])
                self.assertTrue(r['left_startup_verified'])
    def test_r19_frame_or_receipt_failure_prevents_candidate(self):
        for fail in ('r19_mode1','r19_open_before_frame','r19_frame_before_close','r19_after_mode1'):
            with self.subTest(fail=fail):
                r,c,e,_=self.trial([fail]);self.assertIsNotNone(e)
                self.assertNotIn(('program','program_r21'),c)
                self.assertEqual([n for k,n in c if k=='program'],['restore_r19'])
    def test_initial_candidate_success_has_no_second_uart(self):
        r,c,e,_=self.trial();self.assertIsNone(e)
        self.assertEqual([n for k,n in c if k=='send'],['r19_mode1'])
        self.assertEqual(r['outcome'],'R21_started_without_UART_retry')
        self.assertTrue(r['diagnostic_complete']);self.assertEqual(r['last_programmed_sha256'],'CANDIDATE')
    def test_separate_marker_check_precedes_uart(self):
        _,c,_,_=self.trial()
        self.assertLess(c.index(('observe','r19_seed_ncp')),c.index(('observe','r19_witness_before_uart')))
        self.assertLess(c.index(('observe','r19_witness_before_uart')),c.index(('send','r19_mode1')))
        self.assertLess(c.index(('observe','r19_after_mode1')),c.index(('program','program_r21')))
    def test_camera_precedes_each_candidate_dmi(self):
        _,c,e,_=self.trial(['r21_initial_dmi']);self.assertIsNone(e)
        self.assertLess(c.index(('camera','r21_before_initial_dmi')),c.index(('observe','r21_initial_dmi')))
        self.assertLess(c.index(('camera','r21_after_uart_before_dmi')),c.index(('observe','r21_after_mode1_dmi')))
    def test_receipt_witness_is_measured_inside_uart_handle(self):
        _,c,e,_=self.trial();self.assertIsNone(e)
        self.assertLess(c.index(('send','r19_mode1')),c.index(('observe','r19_open_before_frame')))
        self.assertLess(c.index(('observe','r19_open_before_frame')),c.index(('frame','r19_mode1')))
        self.assertLess(c.index(('frame','r19_mode1')),c.index(('observe','r19_frame_before_close')))
        self.assertLess(c.index(('observe','r19_frame_before_close')),c.index(('close','r19_mode1')))
    def test_warm_recovery_does_not_claim_epoch_receipt(self):
        r,c,e,_=self.trial(['r21_initial_dmi']);self.assertIsNone(e)
        self.assertEqual(r['outcome'],'R21_recovered_after_mode1')
        self.assertEqual(r['r21_mode1']['receipt'],'recovery_after_frame_no_independent_epoch')
        self.assertNotIn(('program','restore_r19'),c)
    def test_no_recovery_restores_and_keeps_receipt_unknown(self):
        r,c,e,_=self.trial(['r21_initial_dmi','r21_after_mode1_dmi']);self.assertIsNone(e)
        self.assertEqual(r['outcome'],'R21_no_recovery_UART_receipt_unknown')
        self.assertEqual(r['r21_mode1']['receipt'],'unknown')
        self.assertEqual(r['last_programmed_sha256'],w.t.R19_SHA)
        self.assertTrue(r['diagnostic_complete']);self.assertTrue(r['left_startup_verified'])
    def test_uart_exception_after_candidate_restores(self):
        r,c,e,_=self.trial(['r21_initial_dmi','r21_mode1']);self.assertIsNotNone(e)
        self.assertEqual(r['last_programmed_sha256'],w.t.R19_SHA)
        self.assertTrue(r['left_startup_verified'])
    def test_inner_restore_failure_calls_restore_once(self):
        r,c,e,_=self.trial(['r21_initial_dmi','r21_after_mode1_dmi','restore_r19'])
        self.assertIsNotNone(e);self.assertEqual(c.count(('program','restore_r19')),1)
        self.assertTrue(r['restore_attempted']);self.assertFalse(r['left_startup_verified'])
        self.assertEqual(r['fallback_error'],"RuntimeError('restore_r19')")
    def test_restoration_guard_failure_never_marks_verified(self):
        r,c,e,_=self.trial(['r19_seed_ncp','restored_r19_guard']);self.assertIsNotNone(e)
        self.assertFalse(r['left_startup_verified']);self.assertIn('fallback_error',r)
        self.assertEqual(r['last_programmed_sha256'],w.t.R19_SHA)
    def test_seed_contains_only_ncp_writes(self):
        code=w.seed_code()
        writes=re.findall(r'write_memory\s+(0x[0-9a-f]+)',code)
        self.assertEqual(writes,['0xe9005084','0xe9005088']*2)
        self.assertFalse(any(x in code for x in ('load_image','dump_image','resume','0xe9001010')))
        self.assertEqual(w.FRAME.hex(),'a55a52313501fe0d')
    def test_program_persists_done_before_sleep_and_guard(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);bit=out/'candidate.fs';bit.write_text('fake bitstream')
            digest=w.t.sha(bit);r={};saved=[]
            def save():saved.append(copy.deepcopy(r))
            def child(cmd,log,timeout):
                self.assertIn('-m',cmd);self.assertNotIn('-f',cmd)
                self.assertEqual(timeout,120)
                log.write_text('after program sram: displayReadReg 00026220\n')
            def sleep(_):
                self.assertEqual(saved[-1]['last_programmed_sha256'],digest)
                self.assertFalse(saved[-1]['left_startup_verified'])
                raise RuntimeError('Interrupted after DONE')
            identity={'neo':{'serial':'2025041420','path':'/sys/bus/usb/devices/3-4.4.1'},'programmer_busdev':'3:42'}
            with patch.object(w.hw,'usb_identity',return_value=identity),patch.object(w.hw,'run_child',side_effect=child),patch.object(w.time,'sleep',side_effect=sleep):
                with self.assertRaisesRegex(RuntimeError,'Interrupted after DONE'):
                    w.IO(out,r,save).program('program',bit,digest)
            self.assertEqual(r['last_programmed_sha256'],digest)
    def test_failed_done_never_records_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);bit=out/'candidate.fs';bit.write_text('fake');r={}
            def child(cmd,log,timeout):log.write_text('after program sram: displayReadReg 00024220\n')
            ident={'neo':{'serial':'2025041420','path':'/sys/bus/usb/devices/3-4.4.1'},'programmer_busdev':'3:42'}
            with patch.object(w.hw,'usb_identity',return_value=ident),patch.object(w.hw,'run_child',side_effect=child):
                with self.assertRaises(Exception):w.IO(out,r,lambda:None).program('failed',bit,w.t.sha(bit))
            self.assertIsNone(r['last_programmed_sha256']);self.assertFalse(r['left_startup_verified'])
    def test_camera_file_names_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            r={};out=Path(d)
            def child(cmd,log,timeout):
                self.assertEqual(log.name,'capture_camera.log');self.assertEqual(Path(cmd[-1]).name,'capture.jpg')
                self.assertNotEqual(log,Path(cmd[-1]));raise RuntimeError('camera unavailable')
            with patch.object(w.hw,'run_child',side_effect=child):w.IO(out,r,lambda:None).camera('capture')
            self.assertIn('capture_camera_error',r)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TrialTests))
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,'hardware_access':False,
            'controller_sha256':w.t.sha(Path(w.__file__)),'test_sha256':w.t.sha(Path(__file__)),
            'failures':len(result.failures),'errors':len(result.errors)}
    (w.HERE/'warm_mode1_controller_test_01.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
