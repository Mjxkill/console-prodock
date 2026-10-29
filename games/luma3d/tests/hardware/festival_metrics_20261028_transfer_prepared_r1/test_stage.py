#!/usr/bin/env python3
import json,time,unittest
from unittest.mock import patch
from pathlib import Path
import stage,transfer_trial as t
class Tests(unittest.TestCase):
 def test_exact_binding(self):
  m,h=t.preflight();self.assertEqual(m['target']['bytes'],16640496);self.assertEqual(m['files'][m['payload_file']]['bytes'],2027641);self.assertEqual(m['transport']['planned_sessions'],8)
 def test_capacity_partial_resume_conservative(self):
  m=stage.load_plan();self.assertEqual(stage.storage_check(33628,m),27056745)
  with self.assertRaises(ValueError):stage.storage_check(25500,m)
  self.assertEqual(stage.storage_check(25500,m,payload_exists=True),25029104)
  source=(stage.HERE/'transfer_trial.py').read_text();self.assertIn("'space_transfer','LC_ALL=C df -Pk /tmp')),m,payload_exists=False)",source)
 def test_memory(self):
  self.assertEqual(t.memory(b'MemAvailable: 65536 kB\n'),65536)
  for raw in (b'',b'MemAvailable: 65535 kB\n',b'MemFree: 999999 kB\n'):
   with self.assertRaises(Exception):t.memory(raw)
 def test_no_game_control(self):
  s=(stage.HERE/'transfer_trial.py').read_text();self.assertNotIn('kill(',s);self.assertNotIn('kill -',s);self.assertNotIn('--showcase',s);self.assertNotIn('readlink ',s);self.assertNotIn('wc -',s)
 def test_invalid_segment(self):
  m=stage.load_plan()
  for n in (0,513,1.5):
   with self.assertRaises(ValueError):stage.segment(None,m,blocks=n)
 def test_shell_guard_before_write(self):
  class C:shell=False;current=None
  with self.assertRaises(ValueError):stage.segment(C(),stage.load_plan())
 def test_payload_changed(self):
  m=stage.load_plan();m['files'][m['payload_file']]['sha256']='0'*64
  with self.assertRaises(ValueError):stage.segment(None,m)
 def test_review(self):
  m,h=t.preflight();r=json.loads((stage.HERE/'review.example.json').read_text());r['reviewed_unix']=time.time()
  for k in ['root_authorized_stage_only','same_gm1_since_rx2_probes','same_g22r0_since_rx2_probes','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session']:r[k]=True
  t.review_check(r,h,t.p.HOST,time.time())
  for key,value in [('host','ax15'),('anchor',{'pid':2925,'start_ticks':1}),('plan_sha256','0'*64),('helper_unchanged_since_full_readback',False)]:
   bad=r.copy();bad[key]=value
   with self.assertRaises(Exception):t.review_check(bad,h,t.p.HOST,time.time())
 def test_helper_exact_readback(self):self.assertEqual((stage.HERE/'mc1-helper').read_bytes(),(stage.HERE/'helper_verified.bin').read_bytes())
if __name__=='__main__':unittest.main()
