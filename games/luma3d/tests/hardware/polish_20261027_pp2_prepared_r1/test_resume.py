#!/usr/bin/env python3
"""PP2 local tests only. No serial access; strict helper ranges and cleanup."""
import contextlib,hashlib,io,json,re,struct,subprocess,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import prodock_polish as t
import test_trial as previous
class ResumeTests(unittest.TestCase):
 def test_preflight(self):
  m=t.preflight(HERE);self.assertEqual(m['expected_identity'],dict(pid=2376,start_ticks=21307354));self.assertEqual(m['transfer_files'],['pp2-helper'])
  self.assertEqual(m['game']['sha256'],'d8f65131f8ad4834501850d39354be98a666e484822085004dea13c8fd1c0a48')
 def test_unchanged_identity_and_recovery_contracts(self):
  names=['test_guard_replacement_and_strict_argv','test_recovery_one_launch_after_lost_progress','test_recovery_dies_during_last_display','test_exit_wait_read_only_and_shell','test_tour_requires_real_full_loop','test_helper_owned_memory_bounds']
  result=unittest.TestResult();unittest.TestSuite(previous.Tests(n) for n in names).run(result);self.assertTrue(result.wasSuccessful(),result.errors+result.failures);self.assertFalse(result.skipped)
 def test_slice_rejections_before_gpu(self):
  ref=HERE/'pp1-boss-art.lz4';helper=HERE/'helper-host';full='4194304';crc='7f5699bd'
  for skip,n in [('1','4'),('0','0'),('0','3'),('4194304','4'),('4294967292','8'),('0','4294967295'),('-4','4')]:
   p=subprocess.run([helper,'memory-slice',ref,'29360128',full,crc,skip,n],capture_output=True);self.assertEqual(p.returncode,2)
  # Valid slicing reaches the device open on host, then fails; no file created.
  p=subprocess.run([helper,'memory-slice',ref,'29360128',full,crc,'0','835584'],capture_output=True);self.assertEqual(p.returncode,1)
 def test_flow_failures_and_success(self):
  manifest=json.loads((HERE/'manifest.json').read_text())
  failures=[None,'transfer','staged_game','verify_pp1-boss-art.lz4','pp2_boss_slice_0','pp2_boss_slice_3145728','pp2_checkpoint_launch','tour_timeout','tour_bad','live_after_save','unpublished']
  for failure in failures:
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'manifest.json').write_text('{}');m=manifest;alive=[t.BASE];calls=[];identity=m['expected_identity']
    class UART:
     def __enter__(self):return self
     def __exit__(self,*a):return False
     def write(self,b):calls.append(('write',b))
     def read(self,n):return b''
     def flush(self):pass
    class TX:
     def __init__(self,*a):self.receiver_active=False
     def transfer(self,*a):
      self.receiver_active=True;calls.append(('transfer',a))
      if failure=='transfer':raise KeyboardInterrupt('transfer')
      self.receiver_active=False;return dict(bytes=1)
     def run(self,label,cmd,*args):
      calls.append((label,cmd))
      if label==failure:raise RuntimeError(label)
      if failure=='unpublished' and label=='tour_launch':alive[0]=m['program'];raise KeyboardInterrupt('unpublished')
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='restore_sc1':alive[0]=t.BASE
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if label.startswith('verify_'):
       ref=next(r for r in m['references'] if r['file']==label[7:]);return f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}\n'.encode()
      if '_slice_' in label:
       q=next(q for q in m['publication_ranges'] if label.endswith('_'+str(q['source_offset'])));return f'LUMA3D_MEMORY offset={q["gpu_offset"]} bytes={q["bytes"]} mismatch=0 actual_crc={q["crc32"]} expected_crc={q["crc32"]}\n'.encode()
      if label in ('pp2_boss_log','pp2_checkpoint_log'):
       f=next(f for f in m['fixtures'] if label=='pp2_'+f['name']+'_log');alive[0]=None;return previous.line('LUMA3D_POLISH_PROBE',advance=f['advance'],replay_without_render=1,active=f['active'],hardware=1,saves='disabled')+previous.counters(1,vertices=f['oracle']['vertices'],triangles=f['oracle']['triangles'])
      if label=='tour_log':alive[0]=None;return previous.tour().replace(b'won=ff',b'won=7f') if failure=='tour_bad' else previous.tour()
      if 'prodockctl display' in cmd:return b'DISPLAY presents=30 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      return b''
    def stop(tx,name,label,pidfile=t.LIVE):
     calls.append((label,name))
     if failure=='unpublished' and label=='cleanup_current':raise RuntimeError('Unknown PID')
     alive[0]=None
    def ident(tx,label,*args):
     if failure=='live_after_save' and label=='live_after_save':raise AssertionError('died')
     return identity
    def raw_verify(tx,helper,label,path,record):
     calls.append((label,path))
     if label==failure:raise RuntimeError(label)
    def wait(*a,**kw):
     calls.append(('wait_read_only',a[2]))
     if failure=='tour_timeout' and a[2]=='pp2_tour':raise TimeoutError('tour')
     return 0
    with contextlib.ExitStack() as s:
     for name,value in [('identity',ident),('process',lambda *a:alive[0]==a[2]),('stop',stop),('progress',lambda *a:dict(presents=50)),('preflight',lambda *a:m),('Transport',TX),('readback',lambda *a:None),('raw_verify',raw_verify),('saved_bytes',lambda *a:dict(sha256=t.SAVE_SHA)),('verify_pixels',lambda *a:None),('verify_regions',lambda *a:None),('wait_exit',wait),('stop_baseline',lambda tx,e:stop(tx,t.BASE,'stop_sc1')),('abort_receiver',lambda *a:calls.append(('abort_receiver',a[0].receiver_active)))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result'),'--expected-manifest',hashlib.sha256(b'{}').hexdigest()]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure:
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    result=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',result);self.assertFalse(any(k=='restore_sc1' for k,v in calls))
    else:self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure in ('transfer','staged_game','verify_pp1-boss-art.lz4'):self.assertFalse(any(k=='stop_sc1' for k,v in calls))
    self.assertLessEqual(sum(k=='restore_sc1' for k,v in calls),1)
    self.assertFalse(any(k=='first_launch' or k.startswith('pp2_entry_') for k,v in calls))
    if failure is None:self.assertTrue(result['passed']);self.assertEqual(result['tour']['won'],255)
if __name__=='__main__':unittest.main()
