#!/usr/bin/env python3
"""Real frozen sender vs guarded sender, injected replies; no serial devices."""
import hashlib,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from guarded_transport import guarded_class,ReceiverUncertain
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
OLD=HERE/'prodock_transport.py'
assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='fbca604e76cb35f5e3d559644d8add769f40df1b85c129ba343159b327bf772b'
spec=importlib.util.spec_from_file_location('frozen_transport',OLD);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
class Clock:
 def __init__(self):self.now=0
 def __call__(self):self.now+=.03;return self.now
class UART:
 def __init__(self,mode):
  self.mode=mode;self.queue=bytearray();self.line=bytearray();self.packet=bytearray();self.started=False;self.returned=False;self.read_reject=False;self.writes_after_reject=0;self.bytes_after_exit=0;self.data_packets=0;self.attempts=0;self.total=0;self.marker=False;self.last_kind=None
 def flush(self):pass
 def reset_input_buffer(self):self.queue.clear()
 def reply(self,raw,terminal=False,marker=True):
  self.queue+=raw;self.last_kind=raw[:1]
  if terminal:
   self.returned=True
   if self.marker and marker:self.queue+=b'\nLMA_RX_EXIT_probe.bin:1\n'
 def write(self,data):
  if self.read_reject:self.writes_after_reject+=len(data)
  if not self.started:
   self.line+=data
   if data==b'\n':
    self.started=True;self.marker=b'LMA_RX_EXIT_' in self.line
    if self.mode in ('echo','echo_fragmented','startup_exit','ready_then_exit'):self.queue+=self.line[:-1]+b'\r\n'
    if self.mode!='startup_exit':self.queue+=b'R\0\0\0\0'
    if self.mode in ('startup_exit','ready_then_exit'):self.queue+=b'\r\nLMA_RX_EXIT_probe.bin:1\r\n';self.returned=True
   return len(data)
  if self.returned:self.bytes_after_exit+=len(data);return len(data)
  if self.mode=='partial_write':return max(0,len(data)-1)
  if self.mode=='write_error':raise OSError('injected delivery ambiguity')
  self.packet+=data
  if len(self.packet)<16:return len(data)
  magic,seq,n,crc=struct.unpack('<4sIII',self.packet[:16]);assert magic==b'LMA1'
  if self.mode=='F_early' and self.attempts==0:
   self.attempts+=1;self.packet.clear();self.reply(b'F'+struct.pack('<I',self.total),True);return len(data)
  if len(self.packet)<16+n:return len(data)
  self.packet.clear();self.attempts+=1
  if n:
   self.data_packets+=1
   if self.mode=='N_forever' or (self.mode=='N_once' and self.data_packets==1):self.reply(b'N'+struct.pack('<I',seq));return len(data)
   if self.mode in ('F','D_data','text','timeout','partial_ack','N_wrong','exit_without_ack'):
    raw={'F':b'F\0\0\0\0','D_data':b'D\0\0\0\0','text':b'prodo','timeout':b'','partial_ack':b'A\0','N_wrong':b'N\x02\0\0\0','exit_without_ack':b'\nLMA_RX_EXIT_probe.bin:1\r\n'}[self.mode]
    self.reply(raw,True,marker=False);return len(data)
   self.total+=n;self.reply(b'A'+struct.pack('<I',seq))
  else:
   self.returned=True
   if self.mode=='final_wrong_size':self.queue+=b'D'+struct.pack('<I',self.total+1)
   elif self.mode=='final_F':self.queue+=b'F'+struct.pack('<I',self.total)
   else:self.queue+=b'D'+struct.pack('<I',self.total)
   if self.marker and self.mode!='missing_exit':self.queue+=b'\nLMA_RX_EXIT_probeXbin:0\n' if self.mode=='wrong_marker' else b'\nLMA_RX_EXIT_probe.bin:0\n'
  return len(data)
 def read(self,n):
  if self.mode=='echo_fragmented':n=min(n,3)
  if not self.queue:
   if self.returned and not self.marker and self.mode!='timeout':return b'prodock# '[:n]
   return b''
  b=bytes(self.queue[:n]);del self.queue[:n]
  if self.returned and self.last_kind!=b'A':self.read_reject=True
  return b
def trial(mode,guard=True,signal_done=False):
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);payload=p/'payload';payload.write_bytes(bytes(range(256))*2);uart=UART(mode)
  tx=(guarded_class(old.Transport) if guard else old.Transport)(uart,None,p)
  if signal_done:
   def check():
    if tx.receiver_state=='received_D':raise InterruptedError('at validated D')
   tx.rx_checkpoint=check
  error=None
  with patch.object(old.time,'monotonic',Clock()),patch.object(old.time,'sleep',lambda n:None):
   try:tx.transfer(payload,'probe.bin')
   except BaseException as e:error=type(e).__name__+':'+str(e)
  state=getattr(tx,'receiver_state',None);abort_error=None
  if guard:
   before=uart.writes_after_reject
   try:tx.abort()
   except ReceiverUncertain as e:abort_error=str(e)
   assert uart.writes_after_reject==before
  return dict(mode=mode,guard=guard,error=error,state=state,abort_error=abort_error,attempts=uart.attempts,data_packets=uart.data_packets,writes_after_reject=uart.writes_after_reject,bytes_after_exit=uart.bytes_after_exit,trace=tx.trace if guard else [])
class Tests(unittest.TestCase):
 def test_success_and_explicit_N(self):
  for mode in ('success','N_once','echo','echo_fragmented'):
   r=trial(mode);self.assertIsNone(r['error']);self.assertEqual(r['state'],'complete');self.assertIsNone(r['abort_error'])
 def test_startup_exit_with_echo_preserves_marker_and_sends_no_payload(self):
  for mode in ('startup_exit','ready_then_exit'):
   r=trial(mode);self.assertIsNotNone(r['error']);self.assertEqual(r['state'],'returned_error');self.assertEqual(r['attempts'],0);self.assertEqual(r['bytes_after_exit'],0)
 def test_old_repeats_after_F_guard_never_does(self):
  a=trial('F_early',False);b=trial('F_early');self.assertGreater(a['writes_after_reject'],5000);self.assertEqual(b['writes_after_reject'],0);self.assertEqual(b['state'],'returned_error');self.assertEqual(b['bytes_after_exit'],512)
 def test_uncertain_reply_stops_without_any_retry(self):
  for mode in ('F','D_data','text','timeout','partial_ack','N_wrong'):
   r=trial(mode);self.assertIsNotNone(r['error'],mode);self.assertEqual(r['data_packets'],1,mode);self.assertEqual(r['writes_after_reject'],0,mode);self.assertEqual(r['state'],'unknown',mode);self.assertIsNotNone(r['abort_error'],mode)
 def test_partial_or_exceptional_write_never_replayed(self):
  for mode in ('partial_write','write_error'):
   r=trial(mode);self.assertIsNotNone(r['error']);self.assertEqual(r['state'],'unknown');self.assertEqual(r['attempts'],0)
 def test_D_is_not_a_shell_return(self):
  for mode in ('missing_exit','wrong_marker'):
   r=trial(mode);self.assertIsNotNone(r['error']);self.assertEqual(r['state'],'unknown');self.assertIsNotNone(r['abort_error'])
 def test_exit_marker_prefix_consumed_as_ack_is_preserved(self):
  r=trial('exit_without_ack');self.assertIsNotNone(r['error']);self.assertEqual(r['state'],'returned_error');self.assertEqual(r['writes_after_reject'],0);self.assertIsNone(r['abort_error'])
 def test_fragmented_exit_decimal_needs_newline(self):
  with tempfile.TemporaryDirectory() as tmp:
   uart=UART('success');tx=guarded_class(old.Transport)(uart,None,Path(tmp));tx.rx_carry=b'\nLMA_RX_EXIT_probe.bin:1';uart.queue+=b'0\r\n'
   with patch.object(old.time,'monotonic',Clock()):self.assertEqual(tx.returned_marker('probe.bin'),10)
 def test_changed_payload_refused_before_first_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);payload=p/'payload';payload.write_bytes(b'x');uart=UART('success');tx=guarded_class(old.Transport)(uart,None,p)
   with self.assertRaises(ReceiverUncertain):tx.transfer(payload,'probe.bin',expected=dict(bytes=1,sha256='0'*64,crc32='00000000'))
   self.assertFalse(uart.started);self.assertEqual(uart.line,b'');self.assertEqual(tx.receiver_state,'idle')
 def test_explicit_N_has_bounded_retries(self):
  r=trial('N_forever');self.assertIsNotNone(r['error']);self.assertEqual(r['data_packets'],12);self.assertEqual(r['state'],'unknown');self.assertIsNotNone(r['abort_error'])
 def test_unresolved_states_forbid_shell_commands(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def command(*args):calls.append(args);return 0,b''
   tx=guarded_class(old.Transport)(UART('success'),command,Path(tmp))
   for state in ('unknown','received_D','receiving'):
    tx.set_state(state)
    with self.assertRaises(ReceiverUncertain):tx.run('not_sent','echo sentinel')
   self.assertEqual(calls,[])
 def test_invalid_terminal_tuple_never_succeeds(self):
  for mode in ('final_wrong_size','final_F'):
   r=trial(mode);self.assertIsNotNone(r['error']);self.assertEqual(r['state'],'returned_error');self.assertEqual(r['writes_after_reject'],0)
 def test_signal_after_D_only_reads_return_marker(self):
  r=trial('success',signal_done=True);self.assertIn('InterruptedError',r['error']);self.assertEqual(r['state'],'complete');self.assertEqual(r['writes_after_reject'],0);self.assertIsNone(r['abort_error'])
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=2).run(suite)
 cases=[trial(mode,guard) for mode,guard in [('F_early',False),*[(x,True) for x in ('success','N_once','F_early','F','D_data','text','timeout','partial_ack','N_wrong','partial_write','write_error','missing_exit','final_wrong_size','final_F')]]]
 result=dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,cases=cases,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),HERE/'guarded_transport.py',OLD)})
 (HERE/'guard_tests.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
