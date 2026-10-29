#!/usr/bin/env python3
"""Actual Session/Hardware/guard transfer cleanup with simulated UART+/proc."""
import hashlib,json,signal,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import festival_trial as t
from test_launch_recovery import Target
from test_transport_guard import UART,Clock
HERE=Path(__file__).resolve().parent
RECORDS=[]
class Combined(Target):
 def __init__(self,mode,m,signals):
  super().__init__('transport',m,signals);self.mode=mode;self.serial=UART('F_early' if mode=='resync_failure' else mode);self.base_alive=True
 def write(self,data):self.writes.append(data);return self.serial.write(data)
 def read(self,n):return self.serial.read(n)
 def reset_input_buffer(self):self.serial.reset_input_buffer()
 def command(self,uart,text,seconds):
  if self.mode=='resync_failure' and 'LMA_CONFIRMED_RX_SHELL' in text:self.commands.append(text);return 0,b'wrong output\n'
  return super().command(uart,text,seconds)
class Actual(t.Hardware):
 def initial(self):return dict(identity=t.ANCHOR.copy())
 def prepare(self):
  payload=self.out/'payload';payload.write_bytes(bytes(range(256))*2)
  self.tx.transfer(payload,'probe.bin')
  raise RuntimeError('Test ends after transfer, before any baseline stop')
class Tests(unittest.TestCase):
 def test_real_transfer_error_to_controller_cleanup(self):
  m=json.loads((HERE/'manifest.json').read_text());modules=t.dependencies(HERE,m)
  for mode in ('F_early','F','success','resync_failure'):
   signals=t.DeferredSignals();target=Combined(mode,m,signals);mods=dict(modules);mods['check_linux']=types.SimpleNamespace(command=target.command)
   with tempfile.TemporaryDirectory() as tmp,patch.object(t.time,'sleep',lambda _:None),patch.object(t.time,'monotonic',Clock()):
    b=Actual(HERE,Path(tmp),m,target,signals,mods);result=t.Session(b,m,signals).run()
   self.assertTrue(target.base_alive);self.assertEqual(target.restore_count,0);self.assertFalse(result['passed']);self.assertEqual(result['windows'],[])
   if mode=='resync_failure':
    self.assertIn('cleanup_blocked',result);self.assertTrue(result['receiver_resync_attempted']);self.assertTrue(result['manual_recovery_required']);self.assertEqual(len(target.commands),1)
   elif mode=='F':
    self.assertEqual(b.tx.receiver_state,'unknown');self.assertIn('cleanup_blocked',result);self.assertEqual(target.commands,[]);self.assertEqual(target.serial.writes_after_reject,0)
   else:
    self.assertTrue(result['preserved_gm1']);self.assertNotIn('cleanup_blocked',result)
    if mode=='F_early':self.assertEqual(b.tx.receiver_state,'idle');self.assertIn(b'\x03\x15\n',target.writes)
   RECORDS.append(dict(mode=mode,result=result,state=b.tx.receiver_state,commands=target.commands,baseline_active=target.base_alive))
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 proof=dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,records=RECORDS,manifest_sha256=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 (HERE/'transport_integration_tests.json').write_text(json.dumps(proof,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
