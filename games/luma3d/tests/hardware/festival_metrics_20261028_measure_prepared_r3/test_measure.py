#!/usr/bin/env python3
"""Local transcript tests. Synthetic hardware fields are NOT board evidence."""
import copy,json,re,subprocess,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
import measure as m
import test_launch_recovery as previous
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
BUILD=ROOT/'games/luma3d/build/festival_memory_metrics_20261028_r4'
def synthetic(host):
 lines=[]
 for line in host.splitlines():
  line=line.replace('hardware=0','hardware=1')
  if line.startswith('LUMA3D_FESTIVAL_PHASE '):
   row=m.read_metrics.records(line,'LUMA3D_FESTIVAL_PHASE')[0]
   line=' '.join('rate_valid=1' if word=='rate_valid=0' else 'rate=%.6f'%(row['frames']/row['completion_seconds']) if word.startswith('rate=') else word for word in line.split())
  lines.append(line)
 # Host mode has no actual GPU counters: this row is synthetic test data.
 frames=m.read_metrics.one(host,'LUMA3D_RESULT')['frames']
 lines.append(f'LUMA3D_COUNTERS frames={frames} errors=0 underflows=0 fault=0 geometry_errors=0')
 return ('\n'.join(lines)+'\n').encode()
class SuccessfulTarget(previous.Target):
 def command(self,uart,text,seconds):
  if text.startswith('( /tmp/luma3d-fm4a '):
   self.commands.append(text);uart.write(b'LAUNCH_BYTE')
   tag=re.search(r'F9_PID_([a-z0-9_]+):',text)[1]
   return 0,('\nARCADE_LAUNCHED\nF9_PID_'+tag+':7000\nL3_EXIT_'+tag+':0\n').encode()
  hit=re.fullmatch(r'cat /tmp/fm4measurec_([0-5]).log',text)
  if hit:self.commands.append(text);return 0,Fixtures.synthetic[int(hit[1])]
  return super().command(uart,text,seconds)
class Fixtures:
 host=[];synthetic=[]
def fixtures():
 if Fixtures.host:return
 manifest,_=m.preflight()
 out=HERE/'host_fixtures';out.mkdir(exist_ok=True)
 for row in manifest['windows']:
  q=subprocess.run([str(BUILD/'luma3d-host'),'--host']+row['args'],capture_output=True,text=True,timeout=60)
  assert q.returncode==0,q.stderr
  (out/(row['name']+'.log')).write_text(q.stdout+q.stderr)
  Fixtures.host.append(q.stdout);Fixtures.synthetic.append(synthetic(q.stdout))
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.manifest,cls.sha=m.preflight();cls.mods=m.legacy.dependencies(HERE,cls.manifest);fixtures()
 def test_all_six_actual_windows_and_restore(self):
  signals=m.legacy.DeferredSignals();target=SuccessfulTarget('success',self.manifest,signals)
  modules=dict(self.mods);modules['check_linux']=types.SimpleNamespace(command=target.command)
  with tempfile.TemporaryDirectory() as out,patch.object(m.legacy.time,'sleep',lambda _:None):
   hw=previous.ActualHardware(HERE,Path(out),self.manifest,target,signals,modules)
   result=m.legacy.Session(hw,self.manifest,signals).run()
  self.assertTrue(result['passed'],result);self.assertEqual(len(result['windows']),6);self.assertEqual(target.restore_count,1)
  self.assertEqual([x['measurement']['mode'] for x in result['windows']],[0,1,2,3,5,4])
  self.assertFalse(any('luma-rx' in x for x in target.commands))
  (HERE/'successful_synthetic_transcript.json').write_text(json.dumps(dict(hardware_access=False,synthetic_only=True,result=result,commands=target.commands),indent=2)+'\n')
 def test_host_logs_never_hardware(self):
  for row,host in zip(self.manifest['windows'],Fixtures.host):
   with self.assertRaises(ValueError):m.measurement(host.encode(),row)
 def test_fault_and_missing_presents_refused(self):
  row=self.manifest['windows'][0];log=Fixtures.synthetic[0]
  for key in ('errors','underflows','fault','geometry_errors'):
   changed=re.sub(rb'(^LUMA3D_COUNTERS [^\r\n]*?\b'+key.encode()+rb'=)0',rb'\g<1>1',log,flags=re.M)
   self.assertNotEqual(log,changed)
   with self.assertRaises(RuntimeError):m.measurement(changed,row)
  changed=re.sub(rb'(^LUMA3D_COUNTERS [^\r\n]*?\bframes=)\d+',rb'\g<1>0',log,flags=re.M)
  with self.assertRaises(RuntimeError):m.measurement(changed,row)
 def test_action_early_exit_refused(self):
  for row,log in zip(self.manifest['windows'][:5],Fixtures.synthetic[:5]):
   with self.assertRaises(ValueError):m.measurement(log.replace(b'complete=1',b'complete=0'),row)
 def test_only_small_log_space_reserved(self):
  for free in (1024,15000):self.assertEqual(m.log_capacity(f'tmpfs 186556 160000 {free} 90% /tmp\n'.encode()),free)
  for raw in (b'tmpfs 186556 186555 1 99% /tmp\n',b'tmpfs 1 1 15000 0% /tmp\n',b'other 186556 160000 15000 90% /tmp\n',b''):
   with self.assertRaises(RuntimeError):m.log_capacity(raw)
 def test_exact_stage_result_required(self):
  good=dict(passed=True,hardware=True,preserved=True,plan_sha256=m.STAGE_SHA,after=dict(identity=m.p.ANCHOR,save=dict(sha256=m.p.SAVE)),stop_gm1=False,game_executed=False,staged=dict(elf='/tmp/luma3d-fm4a',expected_sha256=m.TARGET_SHA,runtime_crc32='fa358bf4',game_executed=False))
  m.stage_result_check(good)
  for key,value in [('passed',False),('hardware',False),('preserved',False),('plan_sha256','0'*64),('stop_gm1',True),('game_executed',True)]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.assertRaises(RuntimeError):m.stage_result_check(bad)
  for key,value in [('elf','/tmp/luma3d-gm1'),('runtime_crc32','00000000'),('expected_sha256','0'*64)]:
   bad=copy.deepcopy(good);bad['staged'][key]=value
   with self.assertRaises(RuntimeError):m.stage_result_check(bad)
 def test_review_host_alias_expiry_and_stage(self):
  r=dict(host=m.p.HOST,port=m.p.PORT,manifest_sha256=self.sha,stage_result_sha256='1'*64,anchor=m.p.ANCHOR,fpga_sha256=m.p.FPGA,save_sha256=m.p.SAVE,target_sha256=m.TARGET_SHA,reviewed_unix=100)
  for k in ['root_authorized_six_windows_and_restore','same_gm1_since_stage','same_g22r0_since_stage','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session']:r[k]=True
  m.review_check(r,self.sha,'1'*64,'michael-AX15',100)
  for host,now,stage in [('ax15',100,'1'*64),('michael-AX15',1901,'1'*64),('michael-AX15',99,'1'*64),('michael-AX15',100,'2'*64)]:
   with self.assertRaises(RuntimeError):m.review_check(r,self.sha,stage,host,now)
 def test_runtime_target_and_helper_crc(self):
  commands=[];checks=[]
  obj=object.__new__(m.Hardware);obj.m=self.manifest
  obj.tx=types.SimpleNamespace(run=lambda *a:commands.append(a))
  obj.arcade=types.SimpleNamespace(raw_verify=lambda *a:checks.append(a))
  self.assertEqual(obj.prepare(),[])
  self.assertEqual([x[3] for x in checks],['/tmp/mc1-helper','/tmp/luma3d-gm1','/proc/3158/exe','/tmp/luma3d-fm4a'])
  self.assertEqual(checks[-1][4]['crc32'],'fa358bf4');self.assertIn('test ! -L /tmp/mc1-helper',commands[0][1])
 def test_manifest_bound_schedule_and_inputs(self):
  self.assertEqual([x['mode'] for x in self.manifest['windows']],[0,1,2,3,5,4])
  for x in self.manifest['windows']:
   self.assertEqual(x['timeout_seconds'],180);self.assertFalse(any('save' in arg or 'capture' in arg or 'benchmark' in arg for arg in x['args']))
  self.assertEqual(self.manifest['fpga_sha256'],json.loads((ROOT/'tang/boards/prodock/reference.json').read_text())['bitstream_sha256'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 (HERE/'measure_tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),hardware_access=False,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),synthetic_hardware_fields_not_measurement=True,manifest_sha256=m.p.sha(HERE/'manifest.json')),indent=2)+'\n');raise SystemExit(not result.wasSuccessful())
