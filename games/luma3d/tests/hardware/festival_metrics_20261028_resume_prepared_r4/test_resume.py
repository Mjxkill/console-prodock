#!/usr/bin/env python3
import copy,hashlib,json,types,unittest
from unittest.mock import patch
import stage,transfer_trial as t
class Tests(unittest.TestCase):
 def proof(self):
  expected=[('clean-'+str(n),bytes((i*73+19)&255 for i in range(n))) for n in (0,513,16384)]+[('nack',bytes(range(256))*2+b'!'),('stop',bytes(range(256))*2),('resume',bytes(range(256))*4)]
  return dict(passed=True,integrity_passed=True,link_stability_passed=True,hardware=True,preserved=True,manifest_sha256=t.RX_MANIFEST,after=dict(identity=t.p.ANCHOR,save=dict(sha256=t.p.SAVE)),stop_gm1=False,relaunch_gm1=False,bootstrap_verified=dict(bytes=13132,sha256=t.RX_SHA),probes=[dict(name=n,integrity_passed=True,link_stability_passed=True,returncode=1 if n=='stop' else 0,readback=dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest())) for n,d in expected])
 def test_new_receiver_board_proof_only(self):
  good=self.proof()
  t.receiver_proof_check(good)
  for key,value in [('hardware',False),('passed',False),('preserved',False),('manifest_sha256','d8995a71c23ad6812ea6db94f01a6b1c62e6a00e33c7fa39d53061b3047aebdf'),('stop_gm1',True),('relaunch_gm1',True),('probes',[])]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.assertRaises(RuntimeError):t.receiver_proof_check(bad)
  bad=copy.deepcopy(good);bad['bootstrap_verified']['sha256']='9a5b401858d72b17be6ea5e6765e9994ba4173c8658f8169dd2de1f529e5810e'
  with self.assertRaises(RuntimeError):t.receiver_proof_check(bad)
 def test_instability_requires_root_but_never_waives_integrity(self):
  good=self.proof();good.update(passed=False,link_stability_passed=False);good['probes'][2]['link_stability_passed']=False
  with self.assertRaises(RuntimeError):t.receiver_proof_check(good)
  with self.assertRaises(RuntimeError):t.receiver_proof_check(good,'true')
  t.receiver_proof_check(good,True)
  for key,value in [('integrity_passed',False),('preserved',False),('error','deadline'),('probes',[])]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.assertRaises(RuntimeError):t.receiver_proof_check(bad,True)
  bad=copy.deepcopy(good);bad['probes'][2]['readback']['sha256']='0'*64
  with self.assertRaises(RuntimeError):t.receiver_proof_check(bad,True)
 def test_wrong_checkpoint_no_data(self):
  class FakeSession:
   calls=[]
   def __init__(self,*args,**kw):pass
   def command(self,*args):return b'reviewed launch'
   def begin(self):return types.SimpleNamespace(offset=904192)
   def block(self):self.calls.append('forbidden DATA')
  class Channel:
   shell=True;current=None
   def text(self,cmd):pass
  for wrong in (None,786432,904704):
   c=Channel()
   with patch.object(stage.sender,'Session',FakeSession),self.assertRaises(ValueError):stage.segment(c,stage.load_plan(),resume=True,expected_offset=wrong)
   self.assertFalse(c.shell);self.assertIsNotNone(c.current);self.assertEqual(FakeSession.calls,[])
 def test_resume_required_before_shell(self):
  with self.assertRaises(RuntimeError):t.stage_files(None,stage.load_plan(),False,[])
if __name__=='__main__':unittest.main()
