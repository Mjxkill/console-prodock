#!/usr/bin/env python3
"""Local controller fault injection; never a board/CDC connection."""
import contextlib,hashlib,io,json,re,struct,subprocess,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
sys.path.insert(0,str(HERE))
if not (HERE/'prodock_arcade.py').exists():sys.path.insert(1,str(ROOT/'games/luma3d/tests/hardware/arcade_20261026_ar1_prepared_r2'))
import prodock_showcase as t
import prodock_arcade as core

def line(prefix,**kw):return (prefix+' '+' '.join(str(k)+'='+str(v) for k,v in kw.items())+'\n').encode()
def counters(frames=5000,vertices=3,triangles=2):return line('LUMA3D_COUNTERS',errors=0,underflows=0,fault=0,geometry_errors=0,vertices=vertices,triangles=triangles,slivers=0,frames=frames)
def tour():
 raw=b'LUMA3D_SHOWCASE_START stage=0 simulated=0.000 once=1 saves=disabled\n'
 for i in range(1,17):raw+=line('LUMA3D_SHOWCASE',stage=i,status=1,loops=0,simulated=40*i,wall=50*i,visited='ff',won='ff',commands=i,title='Visite')
 raw+=line('LUMA3D_SHOWCASE',stage=16,status=2,loops=1,simulated=800,wall=900,visited='ff',won='ff',commands=1079,title='Retour')
 raw+=line('LUMA3D_SHOWCASE_RESULT',status=2,stage=16,loops=1,simulated=800,wall=900,visited='ff',won='ff',commands=1079,boss=1,checkpoint=1,crystals=1,hardware=1)
 return raw+counters()+line('LUMA3D_RESULT',frames=5000,elapsed=900,fps=5.55,commands=100,batches=50,hardware=1,benchmark=0)
def manifest():
 ref=dict(file='ref.lz4',bytes=192000,crc32='11111111',bank=20)
 return dict(tag='sc1',program='luma3d-sc1',helper='sc1-helper',game=dict(bytes=100,crc32='22222222'),baseline=dict(bytes=100,crc32='22222222'),transfer_files=['sc1-helper'],delta=dict(file='delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),first=dict(pixels=ref,hud=ref,oracle=dict(vertices=3,triangles=2,slivers=0)),tour_args='--showcase-once',live_args='--showcase',deadline_seconds=3700)
def saved():
 b=bytearray(5292);b[:8]=b'L3PROG1\0';struct.pack_into('<3I',b,8,len(b),0x56414c31,4);struct.pack_into('<8I',b,136,0x34414354,5,0,31,31,1,0,1);struct.pack_into('<I',b,20,zlib.crc32(b[24:]));return b
def octal(b):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in b[i:i+16])).encode() for i in range(0,len(b),16))

class Tests(unittest.TestCase):
 def test_tour_requires_real_full_loop(self):
  self.assertEqual(t.tour_result(tour())['won'],255)
  for raw in [tour().replace(b'won=ff',b'won=7f'),tour().replace(b'boss=1',b'boss=0'),tour().replace(b'hardware=1',b'hardware=0'),tour().replace(b'wall=900',b'wall=0'),tour()+b'LUMA3D_SAVE saved\n',tour()+b'LUMA3D_SHOWCASE_FIXTURE advance=100\n',re.sub(rb'^LUMA3D_SHOWCASE stage=5 [^\n]+\n',b'',tour(),flags=re.M),tour().replace(b'geometry_errors=0',b'geometry_errors=1')]:
   with self.assertRaises(AssertionError):t.tour_result(raw)
 def test_frozen_preflight_and_links(self):
  if not (HERE/'manifest.json').exists():self.skipTest('Packaging pending')
  m=t.preflight(HERE);original=t.json.loads
  for field in ['new_sha256','new_crc32','new_bytes']:
   changed=json.loads(json.dumps(m));changed['delta'][field]='bad'
   def load(data,*a,**kw):
    v=original(data,*a,**kw);return changed if isinstance(v,dict) and v.get('tag')==m['tag'] else v
   with patch.object(t.json,'loads',load):
    with self.assertRaises(AssertionError):t.preflight(HERE)
 def test_guard_replacement_and_duplicate_save(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a));expected=dict(pid=2011,start_ticks=15755109)
  with patch.object(core,'identity',return_value=dict(pid=2011,start_ticks=15755110)):
   with self.assertRaises(AssertionError):t.stop_baseline(tx,expected)
  self.assertFalse(calls)
  raw=b'2011 (luma3d-op2) '+b' '.join([b'S']+[b'0']*18+[b'15755109'])+b'\n/tmp/luma3d-op2\0--save\0/tmp/op2-live.save\0--save\0/tmp/other.save\0\n'
  with patch.object(core,'process',return_value=True):
   with self.assertRaises(AssertionError):t.identity(types.SimpleNamespace(run=lambda *a:raw),'id')
 def test_recovery_one_launch_after_lost_progress(self):
  calls=[];state={};tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(core,'process',return_value=True),patch.object(core,'progress',side_effect=[TimeoutError('reply lost'),dict(presents=5)]):
   with self.assertRaises(TimeoutError):t.recover(tx,manifest(),None,True,state)
   self.assertEqual(t.recover(tx,manifest(),None,True,state),dict(presents=5))
  self.assertEqual(sum(k=='restore_op2' for k,c in calls),1)
 def test_exit_wait_read_only_and_shell(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_sc1_tour:0\n'
   def write(self,b):raise AssertionError('Write during tour')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'sc1_tour'),0)
  for args in ['--showcase','--showcase-once','--showcase --frames 1']:
   cmd=t.once('luma3d-sc1','sc1_tour',args);subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True);self.assertNotIn('--save',cmd)
 def test_faults_cleanup_and_success(self):
  failures=[None,'transfer','install_delta','stop_op2','first_launch','sc1_first_pixels','tour_timeout','tour_bad','live_launch','live_progress','unpublished']
  for failure in failures:
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'manifest.json').write_text('{}');m=manifest();alive=[t.BASE];calls=[];presents=[10]
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
     def run(self,label,cmd,*a):
      calls.append((label,cmd))
      if label==failure or (failure=='unpublished' and label=='tour_launch'):
       if label.endswith('_launch'):alive[0]=m['program'];raise KeyboardInterrupt(label)
       raise RuntimeError(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='install_delta':return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
      if label in ('baseline_file','baseline_running_image'):return b'LUMA3D_RAW_OK bytes=100 crc32=22222222\n'
      if label=='restore_op2':alive[0]=t.BASE
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if label=='first_log':alive[0]=None;return counters(1)
      if label=='tour_log':alive[0]=None;return tour().replace(b'won=ff',b'won=7f') if failure=='tour_bad' else tour()
      if label.startswith('baseline_v4'):return octal(saved())
      if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if '_overlay_' in label:return b'LUMA3D_HUD bank=20 bytes=192000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if label=='live_identity':return b'3010 (luma3d-sc1) S\n/tmp/luma3d-sc1\0--showcase\0\n'
      if 'prodockctl display' in cmd:presents[0]+=1;return f'DISPLAY presents={presents[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
      return b''
    def stop(tx,name,label,pidfile=t.LIVE):
     calls.append((label,name))
     if failure=='unpublished' and label=='cleanup_current':raise RuntimeError('PID not published')
     alive[0]=None
     if label==failure:raise KeyboardInterrupt('reply lost after TERM')
    def wait(*a,**kw):
     calls.append(('wait_read_only',a[2]))
     if failure=='tour_timeout' and a[2]=='sc1_tour':raise TimeoutError('tour')
     return 0
    def progress(*a):
     if failure=='live_progress' and a[3]=='live':raise RuntimeError('progress lost')
     return dict(presents=100)
    with contextlib.ExitStack() as s:
     for module in (t,core):
      for name,value in [('identity',lambda *a:dict(pid=2011,start_ticks=15755109)),('process',lambda *a:alive[0]==a[2]),('stop',stop),('progress',progress)]:s.enter_context(patch.object(module,name,value))
     for name,value in [('preflight',lambda *a:m),('Transport',TX),('readback',lambda *a:None),('wait_exit',wait),('stop_baseline',lambda tx,e:stop(tx,t.BASE,'stop_op2')),('abort_receiver',lambda *a:calls.append(('abort_receiver',getattr(a[0],'receiver_active',False))))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result'),'--expected-manifest',hashlib.sha256(b'{}').hexdigest()]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure:
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    result=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',result);self.assertFalse(any(k=='restore_op2' for k,v in calls))
    else:self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure=='transfer':self.assertIn(('abort_receiver',True),calls);self.assertFalse(any(k=='stop_op2' for k,v in calls))
    if failure is None:self.assertTrue(result['passed']);self.assertEqual(result['tour']['won'],255)
    for label,cmd in calls:
     if label.endswith('_launch'):self.assertNotIn('--save',cmd)

if __name__=='__main__':unittest.main()
