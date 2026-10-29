#!/usr/bin/env python3
"""Offline transcript/state tests. Never opens an actual device."""
import copy,hashlib,json,struct,tempfile,unittest
from pathlib import Path
import recover as r
ACK=lambda code,n:code+struct.pack('<I',n)
RETURN=ACK(b'N',116)+ACK(b'F',59392)+b'\r\nLMA_RX_EXIT_festival-r9f.delta.lz4:1\r\nprodock# '
class Clock:
 def __init__(self):self.now=0
 def __call__(self):return self.now
 def sleep(self,t):self.now+=t
class UART:
 def __init__(self,clock,reply=RETURN,fragment=3,passive=b'',short=False,interrupt=False,resync=b'\b \b\r\nprodock# '):self.clock=clock;self.reply=reply;self.fragment=fragment;self.pending=passive;self.writes=[];self.sent=0;self.short=short;self.interrupt=interrupt;self.resync=resync
 def read(self,n,timeout):
  self.clock.sleep(timeout);got=self.pending[:min(n,self.fragment)];self.pending=self.pending[len(got):];return got
 def write(self,data):
  if self.interrupt and self.sent>=32:raise InterruptedError('injection')
  self.writes.append(data)
  if self.short:return len(data)-1
  if data==b'\x15\n':self.pending+=self.resync
  else:
   self.sent+=len(data)
   if self.sent==2064:self.pending+=self.reply
  return len(data)
class Tests(unittest.TestCase):
 def trial(self,**kw):
  clock=Clock();uart=UART(clock,**kw);tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);claims=[]
  rec=r.Recovery(uart,Path(tmp.name),clock,clock.sleep,lambda:claims.append('claim'));return rec,uart,claims
 def test_success_fragmented(self):
  for fragment in (1,2,3,4,5,4096):
   with self.subTest(fragment=fragment):
    rec,u,c=self.trial(fragment=fragment);got=rec.run();self.assertTrue(got['shell_confirmed']);self.assertEqual(b''.join(u.writes),r.RECOVERY+b'\x15\n');self.assertEqual(c,['claim']);self.assertEqual(got['bytes_sent'],2064)
 def test_no_second_run(self):
  rec,u,c=self.trial();rec.run();before=list(u.writes)
  with self.assertRaises(r.Refused):rec.run()
  self.assertEqual(before,u.writes)
 def test_durable_claim_exclusive(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'once';r.claim_once(p,{'test':1})
   with self.assertRaises(FileExistsError):r.claim_once(p,{'test':2})
   self.assertEqual(json.loads(p.read_text()),{'test':1})
 def test_passive_data_refuses_even_terminal(self):
  for data in (b'prodock# ',RETURN,b'x',b'\0'):
   rec,u,c=self.trial(passive=data)
   with self.assertRaises(r.Refused):rec.run()
   self.assertEqual(u.writes,[]);self.assertEqual(c,[])
 def test_short_or_interrupted_never_ascii(self):
  for kw in ({'short':True},{'interrupt':True}):
   rec,u,c=self.trial(**kw)
   with self.assertRaises((r.Refused,InterruptedError)):rec.run()
   self.assertNotIn(b'\x15\n',u.writes);self.assertEqual(c,['claim']);self.assertLess(rec.record['bytes_sent'],2064)
 def test_unknown_or_wrong_marker_never_ascii(self):
  for reply in (b'',b'D'+struct.pack('<I',59392),RETURN.replace(b':1',b':0'),RETURN.replace(b'r9f',b'r9e'),b'junk'+RETURN,RETURN+RETURN,RETURN+b'dmesg',RETURN+b'> ',b'\nLMA_RX_EXIT_festival-r9f.delta.lz4:1',ACK(b'F',0)+RETURN):
   rec,u,c=self.trial(reply=reply)
   with self.assertRaises(r.Refused):rec.run()
   self.assertEqual(b''.join(u.writes),r.RECOVERY);self.assertFalse(rec.record['shell_confirmed'])
 def test_return_without_ack_is_allowed(self):
  rec,u,c=self.trial(reply=RETURN[10:]);self.assertTrue(rec.run()['shell_confirmed'])
 def test_early_echo_suffix(self):
  rec,u,c=self.trial(reply=RETURN+b'^@'*500+b'LMA1',fragment=16);self.assertTrue(rec.run()['shell_confirmed'])
 def test_bad_resync_stops_before_query(self):
  rec,u,c=self.trial(resync=b'-sh: LMA1: not found\r\nprodock# ')
  with self.assertRaises(r.Refused):rec.run()
  self.assertEqual(b''.join(u.writes),r.RECOVERY+b'\x15\n');self.assertTrue(rec.record['receiver_return_confirmed']);self.assertFalse(rec.record['shell_confirmed'])
 def test_silent_resync_times_out(self):
  rec,u,c=self.trial(resync=b'')
  with self.assertRaises(r.Refused):rec.run()
  self.assertFalse(rec.record['shell_confirmed'])
 def test_queries_guarded(self):
  rec,u,c=self.trial();q=r.Queries(rec,'test')
  with self.assertRaises(r.Refused):q.run('x','identity')
  self.assertFalse(u.writes)
 def test_payload_has_no_command_separator(self):
  self.assertEqual(len(r.RECOVERY),2064);self.assertEqual(set(r.RECOVERY),set(b'\0LMA1'));self.assertNotIn(b'\n',r.RECOVERY);self.assertNotIn(b'\r',r.RECOVERY)
 def test_review(self):
  d='a'*64;v={'manifest_sha256':d,'r6_manifest_sha256':r.R6_SHA,'r6_review_sha256':r.R6_REVIEW_SHA,'expected_identity':r.ANCHOR,'fpga_sha256':r.FPGA_SHA,'save_sha256':r.SAVE_SHA,'baseline_sha256':r.BASE_SHA,'host':r.HOST,'ssh_alias':r.SSH_ALIAS,'port':r.PORT,'reviewed_unix':1000}
  for key in ('root_authorized_one_shot','r6_state_unchanged_since_incident','no_other_console_session','receiver_or_ordinary_shell_only','not_in_quote_heredoc_or_other_program','no_reconfiguration_since_g22r0'):v[key]=True
  r.check_review(v,d,r.HOST,1100)
  for key in v:
   if key=='reviewed_unix':continue
   altered=copy.deepcopy(v);altered[key]=None
   with self.assertRaises(r.Refused):r.check_review(altered,d,r.HOST,1100)
  with self.assertRaises(r.Refused):r.check_review(v,d,'ax15',1100)
  with self.assertRaises(r.Refused):r.check_review(v,d,r.HOST,3000)
 def test_external_reference(self):
  root=next(p for p in Path(__file__).resolve().parents if (p/'tang/boards/prodock/reference.json').is_file());v=json.loads((root/'tang/boards/prodock/reference.json').read_text());self.assertEqual(v['bitstream_sha256'],r.FPGA_SHA)
if __name__=='__main__':unittest.main()
