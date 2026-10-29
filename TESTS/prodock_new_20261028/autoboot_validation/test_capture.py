"""Fake-clock/port integration tests; no hardware or real waits."""
import errno
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import collector

p=Path(__file__).parent/'project/test_boot_log.py'
s=importlib.util.spec_from_file_location('fixture',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
GOOD=m.GOOD
class Clock:
 def __init__(self):self.value=0
 def now(self):return self.value
 def sleep(self,n):self.value+=n
class Fake:
 def __init__(self,clock,streams,disconnect=False,absent=False,error=None):
  self.clock=clock;self.streams=streams;self.disconnect=disconnect;self.absent=absent;self.error=error;self.index=-1;self.opened=False;self.sent=False;self.closed=0;self.reads=0;self.opens=0
 def open(self,timeout=5):
  self.opens+=1
  if self.absent:raise FileNotFoundError
  self.index+=1;self.opened=True;self.sent=False
  return {'usb_path':'/sys/bus/usb/devices/3-7.1','session':self.index}
 def read(self,n,timeout):
  self.clock.sleep(timeout);self.reads+=1
  if self.error and self.reads==2:raise self.error
  if not self.sent:
   self.sent=True;return self.streams[min(self.index,len(self.streams)-1)]
  return b''
 def connected(self):
  return not (self.disconnect and self.index==0)
 def close(self):self.closed+=1;self.opened=False
 def write(self,data):raise AssertionError('No TX permitted')
class Tests(unittest.TestCase):
 def run_capture(self,streams,**kwargs):
  clock=Clock();io=Fake(clock,streams,**kwargs)
  with tempfile.TemporaryDirectory() as t:
   result=collector.capture(io,Path(t),2,clock.now,clock.sleep)
   json.dumps(result)
   for seg in result['segments']:self.assertEqual((Path(t)/seg['file']).stat().st_size,seg['bytes'])
  self.assertLessEqual(clock.now(),2.001);self.assertFalse(io.opened);self.assertEqual(result['uart_tx_bytes'],0)
  return result,io
 def test_complete(self):
  r,_=self.run_capture([GOOD]);self.assertTrue(r['log_checks_passed']);self.assertTrue(r['game_launch_observed']);self.assertFalse(r['gpu_tested']);self.assertFalse(r['powercycle_validated'])
 def test_late(self):
  r,_=self.run_capture([GOOD[GOOD.index(b'Linux version'):]]);self.assertFalse(r['log_checks_passed'])
 def test_reconnect_latest_incomplete(self):
  r,_=self.run_capture([GOOD,b'PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN\n'],disconnect=True);self.assertEqual(len(r['segments']),2);self.assertFalse(r['log_checks_passed'])
 def test_reconnect_latest_complete(self):
  r,_=self.run_capture([b'bad earlier attempt\n',GOOD],disconnect=True);self.assertEqual(len(r['segments']),2);self.assertTrue(r['log_checks_passed'])
 def test_absent_bounded(self):
  r,io=self.run_capture([b''],absent=True);self.assertFalse(r['log_checks_passed']);self.assertLessEqual(io.opens,21)
 def test_interrupt_logs_retained(self):
  r,_=self.run_capture([GOOD],error=InterruptedError('fake SIGTERM'));self.assertFalse(r['capture_completed']);self.assertFalse(r['log_checks_passed']);self.assertGreater(r['bytes'],0)
 def test_output_bound(self):
  r,_=self.run_capture([b'x'*(collector.LIMIT+1)]);self.assertFalse(r['log_checks_passed']);self.assertIn('limit',r['error'])
 def test_invalid_duration(self):
  with tempfile.TemporaryDirectory() as t:
   for v in (0,-1,121,float('inf')):
    with self.assertRaises(RuntimeError):collector.capture(None,Path(t),v)
if __name__=='__main__':unittest.main()
