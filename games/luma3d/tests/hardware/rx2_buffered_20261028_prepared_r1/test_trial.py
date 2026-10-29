#!/usr/bin/env python3
import hashlib,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import trial as t
class Fake:
 def __init__(self):self.sent=bytearray();self.partial=False
 def write(self,b):n=len(b)-(1 if self.partial else 0);self.sent.extend(b[:n]);return n
 def read(self,n,timeout):return b''
 def close(self):pass
class Tests(unittest.TestCase):
 def test_identity_real(self):
  raw=(t.HERE/'health_identity.log').read_bytes();self.assertEqual(t.identity(raw),t.ANCHOR)
  with self.assertRaises(Exception):t.identity(raw.replace(b'27508908',b'27508909'))
  with self.assertRaises(Exception):t.identity(raw.replace(b'-> /tmp/luma3d-gm1',b'-> /tmp/foreign'))
 def test_save_real(self):self.assertEqual(t.save((t.HERE/'health_save.log').read_bytes())['sha256'],t.SAVE)
 def test_capacity(self):
  b=(t.HERE/'health_space.log').read_bytes();self.assertEqual(t.space(b),34244)
  with self.assertRaises(Exception):t.space(b.replace(b'34244',b'100'))
 def test_unknown_prevents_query(self):
  with tempfile.TemporaryDirectory() as d:
   f=Fake();c=t.Channel(f,Path(d))
   with self.assertRaises(Exception):c.run('fail','uname -r')
   self.assertEqual(f.sent,b'');c.close()
 def test_partial_text_disables_queries(self):
  with tempfile.TemporaryDirectory() as d:
   f=Fake();f.partial=True;c=t.Channel(f,Path(d));c.shell=True
   with self.assertRaises(Exception):c.run('partial','uname -r')
   self.assertFalse(c.shell)
   with self.assertRaises(Exception):c.run('again','uname -r')
   c.close()
 def test_unknown_cleanup_silent(self):
  with tempfile.TemporaryDirectory() as d:
   f=Fake();c=t.Channel(f,Path(d));s=t.sender.Session(c,'0'*32,b'',idle_ms=300,total_ms=1000);c.current=s
   with patch.object(s,'await_return',side_effect=t.sender.Uncertain('none')):
    with self.assertRaises(Exception):c.restore_shell(s)
   self.assertFalse(c.shell);self.assertEqual(f.sent,b'');c.close()
 def test_review(self):
  m,h=t.preflight(t.HERE);r=json.loads((t.HERE/'review.example.json').read_text());r['reviewed_unix']=time.time()
  for k in ['root_authorized_probes','same_g22r0_since_health','same_gm1_since_health','ordinary_shell_confirmed','no_other_console_session']:r[k]=True
  t.review_check(r,h,t.HOST,time.time())
  for key,value in [('host','ax15'),('manifest_sha256','0'*64),('fpga_sha256','0'*64),('ordinary_shell_confirmed',False)]:
   bad=r.copy();bad[key]=value
   with self.assertRaises(Exception):t.review_check(bad,h,t.HOST,time.time())
  with self.assertRaises(Exception):t.review_check(r,h,t.HOST,time.time()+1801)
 def test_external_anchor(self):
  self.assertEqual(json.loads((t.HERE/'fpga_reference.json').read_text())['bitstream_sha256'],t.FPGA)
  with patch.object(t,'FPGA',t.FPGA.replace('f9ed0','f9fd0')):
   with self.assertRaises(Exception):t.preflight(t.HERE)
 def test_probes_have_no_game_control(self):
  source=(t.HERE/'trial.py').read_text();self.assertNotIn('kill(',source);self.assertNotIn('readlink ',source);self.assertNotIn('wc -',source);self.assertNotIn('od -An',source)
 def test_empty_and_missing_dump(self):
  class C:
   def __init__(self,data):self.data=data
   def run(self,*args):return self.data
  path='/tmp/rx2-buffer1-empty.part';row=b'-rw-------    1 0 0 0 '+path.encode()+b'\r\n\r\nRX2_PAYLOAD_BEGIN\r\n\r\nRX2_PAYLOAD_END\r\n'
  self.assertEqual(t.payload_readback(C(row),'empty',path,b'')['bytes'],0)
  for bad in (b'',row.replace(b' 0 '+path.encode(),b' 1 '+path.encode()),row.replace(b'RX2_PAYLOAD_BEGIN\r\n',b'RX2_PAYLOAD_BEGIN\r\n0000000 001\r\n'),row.replace(b'RX2_PAYLOAD_BEGIN\r\n',b'RX2_PAYLOAD_BEGIN\r\nERROR\r\n')):
   with self.assertRaises(Exception):t.payload_readback(C(bad),'bad',path,b'')
  with self.assertRaises(Exception):t.payload_readback(C(row.replace(b' 0 '+path.encode(),b' 1 '+path.encode())),'truncated',path,b'A')
if __name__=='__main__':unittest.main()
