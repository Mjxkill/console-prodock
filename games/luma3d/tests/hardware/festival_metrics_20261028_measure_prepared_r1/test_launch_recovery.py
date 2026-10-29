#!/usr/bin/env python3
"""Exercise real controller/Transport/recovery/stop/process with a target model.

No serial.Serial construction, no remote command execution. Only the command
transport and target /proc/files are modeled; launch state, signal checkpoints,
PID parsing, targeted stop and idempotent GM1 restore are the actual functions.
"""
import json,os,re,signal,struct,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import festival_trial as t
import measure
HERE=Path(__file__).resolve().parent
def octal(data):
 return b'\n'.join((f'{i:07o} '+' '.join(f'{b:03o}' for b in data[i:i+16])).encode() for i in range(0,len(data),16))+f'\n{len(data):07o}\n'.encode()
def stat(pid,program,ticks):return f'{pid} ({program}) '.encode()+b' '.join([b'S']+[b'0']*18+[str(ticks).encode()])+b'\n'

class Target:
 def __init__(self,scenario,m,signals):
  self.scenario,self.m,self.signals=scenario,m,signals;self.commands=[];self.writes=[];self.queue=bytearray();self.timeout=.1
  self.base_alive=False;self.candidate_alive=False;self.base_pid=3158;self.base_ticks=27508908;self.presents=10;self.restore_count=0;self.candidate_stops=0;self.pending_ack_signal=False
  self.files={'/tmp/luma3d-live.pid':3158};self.closed_pidfile='/tmp/fm4measurea_0.pid';self.failed_write=False
  self.save=bytes.fromhex(json.loads((HERE/'prior_result.json').read_text())['save_final']['hex'])
 def write(self,data):
  self.writes.append(bytes(data))
  if self.scenario=='write_exception' and data==b'LAUNCH_BYTE' and not self.failed_write:
   self.failed_write=True;raise OSError('first write delivery unknown')
  return len(data)
 def read(self,n):
  data=bytes(self.queue[:n]);del self.queue[:n]
  if self.pending_ack_signal and not self.queue:self.pending_ack_signal=False;self.signals.handler(signal.SIGTERM,None)
  return data
 def flush(self):pass
 def reset_input_buffer(self):self.queue.clear()
 def alive(self,pid):return (pid==self.base_pid and self.base_alive) or (pid==7000 and self.candidate_alive)
 def process(self,pidfile):
  if pidfile not in self.files:return b'UNPUBLISHED\n'
  pid=self.files[pidfile]
  if pid=='':return b'invalid-empty-pidfile\n'
  if not self.alive(pid):return b'STOPPED\n'
  return (b'luma3d-fm4a' if pid==7000 else b'luma3d-gm1')+b'\nState:\tS (sleeping)\n'
 def command(self,uart,text,seconds):
  self.commands.append(text)
  if text.startswith('( /tmp/luma3d-fm4a '):
   if self.scenario=='before_first_write':self.signals.handler(signal.SIGTERM,None)
   if self.scenario=='exception_before_write':raise OSError('command failed before any write')
   uart.write(b'LAUNCH_BYTE')
   if self.scenario=='timeout_after_write':raise TimeoutError('command reply lost')
   reply=b'\nARCADE_LAUNCHED\n'
   if self.scenario in ('published','completed'):
    self.files[self.closed_pidfile]=7000;self.candidate_alive=True;reply+=b'F9_PID_fm4measurea_0:7000\n'
   if self.scenario=='completed':self.candidate_alive=False;reply+=b'L3_EXIT_fm4measurea_0:0\n'
   if self.scenario=='empty_pidfile':self.files[self.closed_pidfile]=''
   self.signals.handler(signal.SIGTERM,None);return 0,reply
  if text.startswith('/tmp/luma3d-gm1 --showcase '):
   self.restore_count+=1;assert not self.candidate_alive
   self.base_alive=True;self.base_pid=4000;self.base_ticks=8888
   self.files['/tmp/fm4measurea_restore.pid']=4000;return 0,b''
  if text.startswith('cp /tmp/fm4measurea_restore.pid '):self.files['/tmp/luma3d-live.pid']=4000;return 0,b''
  if text.startswith('/tmp/mc1-helper raw '):
   q=self.m['baseline'];return 0,f'LUMA3D_RAW_OK bytes={q["bytes"]} crc32={q["crc32"]}\n'.encode()
  if text=='od -b -v /tmp/op2-live.save':return 0,octal(self.save)
  if text=='prodockctl display':
   self.presents+=1;return 0,f'DISPLAY presents={self.presents} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
  if text=='cat /tmp/fm4measurea_restore.log':return 0,b'LUMA3D_PERF fps=25\n'
  if 'kill -TERM 7000' in text:self.candidate_alive=False;self.candidate_stops+=1;return 0,b''
  if text.startswith('if test -d /proc/7000;'):return 0,b'STOPPED\n' if not self.candidate_alive else stat(7000,'luma3d-fm4a',777)
  pidfile=re.search(r'p=`cat (/tmp/[A-Za-z0-9_.-]+)`',text)
  if pidfile:
   path=pidfile[1]
   if '/comm; cat /proc/$p/status;' in text:return 0,self.process(path)
   if '/stat; od -b -v /proc/$p/cmdline' in text:
    pid=self.files[path];assert pid==self.base_pid and self.base_alive
    return 0,stat(pid,'luma3d-gm1',self.base_ticks)+octal(b'/tmp/luma3d-gm1\0--showcase\0')
   if '/stat;' in text:
    pid=self.files[path]
    return 0,stat(7000,'luma3d-fm4a',777) if self.candidate_alive else b'STOPPED\n'
  if text=='echo LUMA_RECEIVER_STOPPED':return 0,b'LUMA_RECEIVER_STOPPED\n'
  if text=='printf "\\nLMA_CONFIRMED_RX_SHELL\\n"':return 0,b'\nLMA_CONFIRMED_RX_SHELL\n'
  raise AssertionError('Unmodeled command '+text)

class ActualHardware(measure.Hardware):
 def initial(self):return {'identity':t.ANCHOR.copy()}
 def prepare(self):return []
 def recheck(self):pass
 def stop_baseline(self):pass # the target starts after its confirmed stop
 def window(self,row,tag,launch):
  if self.uart.scenario=='pending_presend':self.signals.handler(signal.SIGTERM,None)
  return super().window(row,tag,launch)

RECORDS=[]
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.m=json.loads((HERE/'manifest.json').read_text());cls.modules=t.dependencies(HERE,cls.m)
 def scenario(self,name):
  signals=t.DeferredSignals();target=Target(name,self.m,signals)
  modules=dict(self.modules);modules['check_linux']=types.SimpleNamespace(command=target.command)
  with tempfile.TemporaryDirectory(prefix='festival-recovery-') as out,patch.object(t.time,'sleep',lambda _:None):
   b=ActualHardware(HERE,Path(out),self.m,target,signals,modules);result=t.Session(b,self.m,signals).run()
  RECORDS.append(dict(scenario=name,simulated_result=result,baseline_running_after=target.base_alive,candidate_stops=target.candidate_stops,restore_count=target.restore_count,commands=target.commands,writes=[x.hex() for x in target.writes]))
  return result,target
 def test_certainly_unsent_restores(self):
  for name in ('pending_presend','before_first_write','exception_before_write'):
   r,target=self.scenario(name);self.assertFalse(r['passed']);self.assertTrue(r['restored_gm1']);self.assertNotIn('cleanup_error',r);self.assertEqual(r['interrupted_launch']['state'],'not_sent');self.assertEqual(target.restore_count,1)
   self.assertFalse(any('fm4measurea_0.pid' in x for x in target.commands if not x.startswith('( /tmp/luma3d-fm4a ')))
 def test_uncertain_unpublished_remains_blocking(self):
  for name in ('parent_reply_only','write_exception','timeout_after_write','empty_pidfile'):
   r,target=self.scenario(name);self.assertFalse(r.get('restored_gm1',False));self.assertIn('cleanup_error',r);self.assertEqual(r['interrupted_launch']['state'],'sending_unknown');self.assertEqual(target.restore_count,0);self.assertFalse(target.base_alive)
 def test_published_candidate_is_stopped_then_gm1_restored(self):
  r,target=self.scenario('published');self.assertEqual(r['interrupted_launch']['state'],'published');self.assertEqual(r['interrupted_launch']['pid'],7000);self.assertTrue(r['restored_gm1']);self.assertEqual(target.candidate_stops,1);self.assertEqual(target.restore_count,1)
 def test_completed_candidate_needs_no_stop(self):
  r,target=self.scenario('completed');self.assertEqual(r['interrupted_launch']['state'],'completed');self.assertTrue(r['restored_gm1']);self.assertEqual(target.candidate_stops,0);self.assertEqual(target.restore_count,1)
 def test_parent_echo_is_not_publication(self):
  launch=t.LaunchState('luma3d-fm4a','fm4measurea_0');launch.begin_write();launch.observe(b'ARCADE_LAUNCHED\n');self.assertEqual(launch.state,'sending_unknown');self.assertIsNotNone(launch.cleanup_target())
 def test_fragmented_pid_and_exit_require_complete_lines(self):
  launch=t.LaunchState('luma3d-fm4a','fm4measurea_0');launch.begin_write();launch.observe(b'F9_PID_fm4measurea_0:70');self.assertEqual(launch.state,'sending_unknown')
  launch.observe(b'F9_PID_fm4measurea_0:7000\n');self.assertEqual(launch.pid,7000)
  launch.observe(b'L3_EXIT_fm4measurea_0:1');self.assertEqual(launch.state,'published')
  launch.observe(b'L3_EXIT_fm4measurea_0:10\n');self.assertEqual(launch.exit_code,10)
 def test_raw_ack_cannot_authorize_receiver_exit(self):
  for code in ('D','A'):
   signals=t.DeferredSignals();target=Target('ack',self.m,signals);target.queue.extend(code.encode()+struct.pack('<I',512));target.pending_ack_signal=True
   modules=dict(self.modules);modules['check_linux']=types.SimpleNamespace(command=target.command)
   with tempfile.TemporaryDirectory() as out:
    b=t.Hardware(HERE,Path(out),self.m,target,signals,modules);b.tx.set_state('receiving')
    self.assertEqual(b.tx.ack(),(ord(code),512));self.assertEqual(b.tx.receiver_state,'receiving')
    with self.assertRaises(modules['guarded_transport'].ReceiverUncertain):b.abort_transfer()
    self.assertEqual(target.writes,[])
 def test_atomic_pid_publication_shell(self):
  text=t.launch_command('luma3d-fm4a','fm4measurea_0','--festival --frames 1')
  self.assertIn('> /tmp/fm4measurea_0.pid.tmp && mv /tmp/fm4measurea_0.pid.tmp /tmp/fm4measurea_0.pid',text)
  self.assertLess(text.index('mv /tmp/'),text.index('F9_PID_'))
 def test_resync_only_after_confirmed_receiver_return(self):
  for state in ('returned_error','unknown','received_D','receiving'):
   signals=t.DeferredSignals();signals.cleanup=True;target=Target('resync',self.m,signals)
   modules=dict(self.modules);modules['check_linux']=types.SimpleNamespace(command=target.command)
   with tempfile.TemporaryDirectory() as out,patch.object(t.time,'sleep',lambda _:None):
    b=t.Hardware(HERE,Path(out),self.m,target,signals,modules);b.tx.set_state(state)
    if state=='returned_error':
     b.abort_transfer();self.assertEqual(target.writes,[b'\x03\x15\n']);self.assertEqual(b.tx.receiver_state,'idle');self.assertEqual(len(target.commands),1)
    else:
     with self.assertRaises(modules['guarded_transport'].ReceiverUncertain):b.abort_transfer()
     self.assertEqual(target.writes,[]);self.assertEqual(target.commands,[])

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 proof=dict(passed=result.wasSuccessful(),hardware_access=False,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),exact_functions=['Session.run','Hardware.window','Hardware.recover','CheckedTransport.run','GuardedTransport.run','Transport.run','Transport.ack','trial_guards.recover','trial_guards.identity','prodock_arcade.stop','prodock_valley_ab.process'],manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=t.digest(HERE/'festival_trial.py')['sha256'],test_sha256=t.digest(HERE/'test_launch_recovery.py')['sha256'],records=RECORDS)
 (HERE/'launch_recovery_tests.json').write_text(json.dumps(proof,indent=2)+'\n');raise SystemExit(0 if result.wasSuccessful() else 1)
