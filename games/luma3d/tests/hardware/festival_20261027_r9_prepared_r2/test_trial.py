#!/usr/bin/env python3
"""Local negative guards and cleanup tests; never instantiate serial.Serial."""
import copy,hashlib,importlib.util,json,os,signal,subprocess,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('festival_trial',HERE/'festival_trial.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

def manifest():return json.loads((HERE/'manifest.json').read_text())
def review(m):return dict(approved=True,reviewer='root',ssh_host='ax15',local_hostname='michael-AX15',manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=m['files']['festival_trial.py']['sha256'],board='prodock',expected_identity=t.ANCHOR.copy(),fpga='G22r0',fpga_sha256=t.FPGA_SHA,continuity_confirmed=True,kernel=t.RELEASE,save_sha256=t.SAVE_SHA)
def log(row):
 return (f'LUMA3D_RESULT frames={row["frames"]} elapsed=10.000 fps={row["frames"]/10:.2f} commands=200 batches=10 feed_seconds=1.0 present_seconds=2.0 draws_last=0 triangles_last=0 benchmark=0 hardware=1 warmup=0\n'
         f'LUMA3D_FESTIVAL active=1 mode={row["kind"]} visited=f won=0 time=10.000 hardware=1\n'
         f'LUMA3D_COUNTERS frames={row["frames"]} errors=0 underflows=0 fault=0 geometry_errors=0\n').encode()
class Backend:
 def __init__(self,failure=None,signals=None):self.calls=[];self.failure=failure;self.signals=signals;self.running='gm1'
 def call(self,name):
  self.calls.append(name)
  if self.failure==name:raise RuntimeError('injected '+name)
 def initial(self):self.call('initial');return {'identity':t.ANCHOR.copy()}
 def prepare(self):self.call('prepare');return []
 def recheck(self):self.call('recheck')
 def stop_baseline(self):self.running=None;self.call('stop')
 def window(self,row,tag,launch):
  launch.begin_write()
  self.running='candidate';self.call('window_'+row['name'])
  if self.failure=='signal':os.kill(os.getpid(),signal.SIGTERM);self.signals.checkpoint()
  self.running=None;launch.observe(('\nL3_EXIT_'+tag+':0\n').encode());return {'window':row,'measurement':t.parse_window(log(row),row)}
 def abort_transfer(self):self.call('abort')
 def preserved(self):self.call('preserved');assert self.running=='gm1';return True
 def recover(self,current,ever,recovery):
  self.call('recover')
  if self.failure=='signal':os.kill(os.getpid(),signal.SIGHUP);self.signals.checkpoint()
  if self.running=='candidate':assert current is not None
  self.running='gm1';return {'identity':{'pid':4000,'start_ticks':8888}}

class Tests(unittest.TestCase):
 def test_frozen_preflight(self):self.assertEqual(t.preflight(HERE)['expected_identity'],dict(pid=3158,start_ticks=27508908))
 def test_stale_anchor_and_schedule(self):
  original=manifest()
  for field,value in [('expected_identity',dict(pid=2925,start_ticks=26240721)),('program','luma3d-f8'),('normal_exit','leave_candidate'),('board','neo'),('host','other'),('local_hostname','ax15'),('kernel','wrong'),('transfer_files',['other']),('windows',[])]:
   changed=copy.deepcopy(original);changed[field]=value
   with patch.object(t.json,'loads',return_value=changed):
    with self.assertRaises(RuntimeError):t.preflight(HERE)
 def test_hash_rejection(self):
  original=t.digest
  for name in ['festival_trial.py',*t.DEPS,'f9-helper','festival-r9.delta.lz4']:
   def corrupted(path):
    value=original(path)
    if Path(path).name==name:value['sha256']='0'*64
    return value
   with patch.object(t,'digest',side_effect=corrupted):
    with self.assertRaises(RuntimeError,msg=name):t.preflight(HERE)
 def test_review_bound_to_exact_inputs(self):
  m=manifest();r=review(m);sha=t.digest(HERE/'manifest.json')['sha256'];t.check_review(r,m,sha,'michael-AX15')
  for key,value in [('approved',False),('reviewer','automatic'),('ssh_host','other'),('local_hostname','ax15'),('manifest_sha256','0'*64),('controller_sha256','0'*64),('board','neo'),('expected_identity',{'pid':2925,'start_ticks':1}),('continuity_confirmed',False),('kernel','wrong'),('save_sha256','0'*64)]:
   other=copy.deepcopy(r);other[key]=value
   with self.assertRaises(RuntimeError,msg=key):t.check_review(other,m,sha,'michael-AX15')
  with self.assertRaises(RuntimeError):t.check_review(r,m,sha,'another_pc')
  # The SSH alias is not the machine hostname observed by root. Never accept it
  # as a replacement for an actual runtime identity check.
  with self.assertRaises(RuntimeError):t.check_review(r,m,sha,'ax15')
 def test_exact_arguments_no_mutations(self):
  for row in t.schedule():
   args=t.arguments(row);self.assertNotIn('--save',args);self.assertNotIn('--festival-save',args);self.assertNotIn('--benchmark',args);self.assertNotIn('--showcase',args)
   self.assertEqual('--manual' in args,row['manual']);subprocess.run(['sh','-n','-c',t.launch_command('luma3d-f9','festivalr9_0',args)],check=True)
 def test_metrics_negative(self):
  row=t.schedule()[0];raw=log(row);t.parse_window(raw,row)
  for old,new in [(b'hardware=1',b'hardware=0'),(b'elapsed=10.000',b'elapsed=nan'),(b'frames=120',b'frames=119'),(b'fps=12.00',b'fps=120.00'),(b'mode=0',b'mode=1'),(b'errors=0',b'errors=1'),(b'geometry_errors=0',b'geometry_errors=1'),(b'active=1',b'active=0'),(b'LUMA3D_RESULT',b'NO_RESULT')]:
   with self.assertRaises((RuntimeError,KeyError,ValueError),msg=old):t.parse_window(raw.replace(old,new,1),row)
  for extra in [raw,b'LUMA3D_SAVE saved\n',b'LUMA3D_PERF fps=12.0\n']:
   with self.assertRaises(RuntimeError):t.parse_window(raw+extra,row)
 def test_success_always_restores(self):
  b=Backend();s=t.Session(b,manifest(),t.DeferredSignals());r=s.run();self.assertTrue(r['passed']);self.assertEqual(b.running,'gm1');self.assertEqual(b.calls.count('recover'),1)
  self.assertEqual(len(r['windows']),6);self.assertFalse(r['candidate_promoted']);self.assertEqual(b.calls[-2:],['abort','recover'])
 def test_failure_preserves_or_recovers(self):
  for failure in ('initial','prepare','recheck','stop','window_othello','window_solitaire','window_chroma','window_hangman','window_garden','window_automatic_tour','recover'):
   b=Backend(failure);r=t.Session(b,manifest(),t.DeferredSignals()).run();self.assertFalse(r['passed'])
   if failure in ('initial','prepare','recheck'):self.assertNotIn('recover',b.calls);self.assertEqual(b.running,'gm1')
   elif failure!='recover':self.assertTrue(r['restored_gm1']);self.assertEqual(b.running,'gm1');self.assertEqual(b.calls.count('recover'),1)
   else:self.assertIn('cleanup_error',r)
 def test_primary_and_recovery_error_kept(self):
  b=Backend('window_othello')
  def failed_recover(*unused):raise RuntimeError('separate cleanup failure')
  b.recover=failed_recover;r=t.Session(b,manifest(),t.DeferredSignals()).run();self.assertIn('window_othello',r['error']);self.assertIn('separate cleanup failure',r['cleanup_error'])
 def test_repeated_real_signals_do_not_interrupt_recovery(self):
  old=[signal.getsignal(n) for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)]
  with t.DeferredSignals() as signals:
   b=Backend('signal',signals);r=t.Session(b,manifest(),signals).run();self.assertFalse(r['passed']);self.assertTrue(r['restored_gm1']);self.assertEqual(r['signals'],[signal.SIGTERM,signal.SIGHUP]);self.assertEqual(b.calls.count('recover'),1)
  self.assertEqual(old,[signal.getsignal(n) for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)])
 def test_signal_before_start_touches_nothing(self):
  signals=t.DeferredSignals();signals.handler(signal.SIGTERM,None);b=Backend();r=t.Session(b,manifest(),signals).run();self.assertFalse(r['passed']);self.assertEqual(b.calls,['abort']);self.assertEqual(b.running,'gm1')
 def test_lock_required_before_uart(self):
  # The controller acquires a nonblocking lock before constructing Hardware.
  source=(HERE/'festival_trial.py').read_text();self.assertLess(source.index('fcntl.flock(lock,'),source.index('with serial.Serial(PORT,'));self.assertIn('exclusive=True',source)
  with tempfile.TemporaryDirectory() as tmp:
   with open(Path(tmp)/'lock','a+') as a,open(Path(tmp)/'lock','a+') as b:
    t.fcntl.flock(a,t.fcntl.LOCK_EX|t.fcntl.LOCK_NB)
    with self.assertRaises(BlockingIOError):t.fcntl.flock(b,t.fcntl.LOCK_EX|t.fcntl.LOCK_NB)
 def test_no_hardware_in_default_cli(self):
  q=subprocess.run(['python3',str(HERE/'festival_trial.py')],capture_output=True,check=True);r=json.loads(q.stdout);self.assertTrue(r['preflight_passed']);self.assertFalse(r['hardware_access'])
 def test_optimized_python_refused(self):
  q=subprocess.run(['python3','-O',str(HERE/'festival_trial.py')],capture_output=True);self.assertNotEqual(q.returncode,0);self.assertIn(b'disable guards',q.stderr)
 def test_delta_corruption_rejected_before_output(self):
  m=manifest();d=m['delta'];root=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').exists());base=root/'games/luma3d/build/maze_events_20261027_r4/luma3d-riscv'
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);bad=bytearray((HERE/d['file']).read_bytes());bad[0]^=255;(tmp/'bad').write_bytes(bad);out=Path('/tmp/'+tmp.name+'.elf')
   try:
    q=subprocess.run([str(HERE/'helper-host'),'patch',str(tmp/'bad'),str(out),str(d['patch_bytes']),d['patch_crc32'],str(base)],capture_output=True)
    self.assertNotEqual(q.returncode,0);self.assertFalse(out.exists())
   finally:
    if out.exists():out.unlink()

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 proof=dict(passed=result.wasSuccessful(),hardware=False,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=t.digest(HERE/'festival_trial.py')['sha256'],test_sha256=t.digest(HERE/'test_trial.py')['sha256'])
 (HERE/'local_tests.json').write_text(json.dumps(proof,indent=2)+'\n');raise SystemExit(0 if result.wasSuccessful() else 1)
