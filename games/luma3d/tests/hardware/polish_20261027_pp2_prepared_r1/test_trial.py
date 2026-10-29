#!/usr/bin/env python3
"""Local controller fault injection; never a board/CDC connection."""
import contextlib,hashlib,io,json,re,struct,subprocess,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
sys.path.insert(0,str(HERE))
if not (HERE/'prodock_arcade.py').exists():sys.path.insert(1,str(ROOT/'games/luma3d/tests/hardware/showcase_20261026_sc1_prepared_r1'))
import prodock_polish as t
core=t

def line(prefix,**kw):return (prefix+' '+' '.join(str(k)+'='+str(v) for k,v in kw.items())+'\n').encode()
def counters(frames=5000,vertices=3,triangles=2):return line('LUMA3D_COUNTERS',errors=0,underflows=0,fault=0,geometry_errors=0,vertices=vertices,triangles=triangles,slivers=0,frames=frames)
def tour():
 raw=b'LUMA3D_SHOWCASE_START stage=0 simulated=0.000 once=1 saves=disabled\n'
 for i in range(1,17):raw+=line('LUMA3D_SHOWCASE',stage=i,status=1,loops=0,simulated=40*i,wall=50*i,visited='ff',won='ff',commands=i,title='Visite')
 raw+=line('LUMA3D_SHOWCASE',stage=16,status=2,loops=1,simulated=800,wall=900,visited='ff',won='ff',commands=1079,title='Retour')
 raw+=line('LUMA3D_SHOWCASE_RESULT',status=2,stage=16,loops=1,simulated=800,wall=900,visited='ff',won='ff',commands=1079,boss=1,checkpoint=1,crystals=1,hardware=1)

 for k in range(9):
  raw+=line('LUMA3D_ACTIVITY_COST',mode=k,frames=500,simulation=1,adviser=.1,preparation=1,submit=0,present=1,ui_bytes=1,commands=0,batches=0,triangles=0,max_sprites=22 if k==7 else 0,max_layers=4 if k==7 else 1,max_draws=0,frame_sum=100,p95_upper_ms=200,p99_upper_ms=220,p95_overflow=0,p99_overflow=0,over_1020ms=0,over_33ms=400,max_frame=.3,hardware=1)
 return raw+counters(4500)+line('LUMA3D_RESULT',frames=4500,elapsed=900,fps=5.55,commands=100,batches=50,hardware=1,benchmark=0)
def manifest():
 ref=dict(file='ref.lz4',bytes=192000,crc32='11111111',bank=20)
 m=dict(tag='pp1',program='luma3d-pp1',probe='pp1-probe',helper='pp1-helper',game=dict(bytes=100,crc32='22222222'),baseline=dict(bytes=100,crc32='22222222'),transfer_files=['pp1-helper'],delta=dict(file='delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),first=dict(pixels=ref,hud=ref,oracle=dict(vertices=3,triangles=2,slivers=0)),tour_args='--showcase-once',live_args='--showcase',deadline_seconds=3700)
 m['probe_delta']=m['delta'];m['references']=[ref];m['fixtures']=[dict(name='entry_'+str(i),advance=i+1,active=i+1,pixels=ref,regions=[ref],oracle=dict(vertices=3,triangles=2,slivers=0)) for i in range(8)];return m
def saved():
 b=bytearray(5292);b[:8]=b'L3PROG1\0';struct.pack_into('<3I',b,8,len(b),0x56414c31,4);struct.pack_into('<8I',b,136,0x34414354,5,0,31,31,1,0,1);struct.pack_into('<I',b,20,zlib.crc32(b[24:]));return b
def octal(b):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in b[i:i+16])).encode() for i in range(0,len(b),16))

class Tests(unittest.TestCase):
 def test_tour_requires_real_full_loop(self):
  self.assertEqual(t.tour_result(tour())['won'],255)
  for raw in [tour().replace(b'won=ff',b'won=7f'),tour().replace(b'boss=1',b'boss=0'),tour().replace(b'hardware=1',b'hardware=0'),tour().replace(b'wall=900',b'wall=0'),tour()+b'LUMA3D_SAVE saved\n',tour()+b'LUMA3D_SHOWCASE_FIXTURE advance=100\n',re.sub(rb'^LUMA3D_SHOWCASE stage=5 [^\n]+\n',b'',tour(),flags=re.M),tour().replace(b'geometry_errors=0',b'geometry_errors=1')]:
   with self.assertRaises(AssertionError):t.tour_result(raw)
  for raw in [tour().replace(b'adviser=0.1',b'adviser=99'),tour().replace(b'present=1',b'present=nan'),tour().replace(b'p99_upper_ms=220',b'p99_upper_ms=221'),tour().replace(b'max_sprites=22',b'max_sprites=65'),re.sub(rb'^LUMA3D_ACTIVITY_COST mode=4 [^\n]+\n',b'',tour(),flags=re.M)]:
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
 def test_guard_replacement_and_strict_argv(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a));expected=dict(pid=2011,start_ticks=15755109)
  with patch.object(core,'identity',return_value=dict(pid=2011,start_ticks=15755110)):
   with self.assertRaises(AssertionError):t.stop_baseline(tx,expected)
  self.assertFalse(calls)
  prefix=b'2011 (luma3d-sc1) '+b' '.join([b'S']+[b'0']*18+[b'15755109'])+b'\n'
  def encoded(args):return prefix+octal(args)+b'\n'+f'{len(args):07o}\n'.encode()
  args=b'/tmp/luma3d-sc1\0--showcase\0'
  with patch.object(t,'process',return_value=True):
   self.assertEqual(t.identity(types.SimpleNamespace(run=lambda *a:encoded(args)),'id'),expected)
   for extra in (b'--save\0/tmp/other.save\0',b'\n--save\0/tmp/other.save\0',b'\r--save\0/tmp/other.save\0',b'\0'):
    with self.assertRaises(AssertionError):t.identity(types.SimpleNamespace(run=lambda *a:encoded(args+extra)),'id')
 def test_recovery_one_launch_after_lost_progress(self):
  calls=[];state={};tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(core,'identity',return_value=dict(pid=3000,start_ticks=7)),patch.object(core,'process',return_value=True),patch.object(core,'progress',side_effect=[TimeoutError('reply lost'),dict(presents=5)]):
   with self.assertRaises(TimeoutError):t.recover(tx,manifest(),None,True,state)
   self.assertEqual(t.recover(tx,manifest(),None,True,state),dict(presents=5))
  self.assertEqual(sum(k=='restore_sc1' for k,c in calls),1)
 def test_recovery_dies_during_last_display(self):
  calls=[];state={};tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(t,'identity',side_effect=[dict(pid=3000,start_ticks=7),AssertionError('process died during display')]),patch.object(t,'progress',return_value=dict(presents=11)):
   with self.assertRaises(AssertionError):t.recover(tx,manifest(),None,True,state)
  self.assertTrue(state['attempted']);self.assertEqual(state['identity'],dict(pid=3000,start_ticks=7))
  self.assertFalse(any(k=='publish_restored_pid' for k,c in calls))
  with patch.object(t,'identity',side_effect=AssertionError('still dead')):
   with self.assertRaises(AssertionError):t.recover(tx,manifest(),None,True,state)
  self.assertEqual(sum(k=='restore_sc1' for k,c in calls),1)
 def test_exit_wait_read_only_and_shell(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_pp1_tour:0\n'
   def write(self,b):raise AssertionError('Write during tour')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'pp1_tour'),0)
  for args in ['--showcase','--showcase-once','--showcase --frames 1']:
   cmd=t.once('luma3d-sc1','pp1_tour',args);subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True);self.assertNotIn('--save',cmd)
 def test_faults_cleanup_and_success(self):
  failures=[None,'transfer','install_delta','install_probe','stop_sc1','first_launch','pp1_first_pixels','pp1_entry_4_launch','tour_timeout','tour_bad','live_launch','live_progress','live_after_save','unpublished']
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
      if label=='install_delta' or label=='install_probe':return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
      if label in ('baseline_file','baseline_running_image'):return b'LUMA3D_RAW_OK bytes=100 crc32=22222222\n'
      if label=='restore_sc1':alive[0]=t.BASE
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if label.startswith('pp1_entry_') and label.endswith('_log'):
       i=int(label.split('_')[2]);alive[0]=None;return line('LUMA3D_POLISH_PROBE',advance=i+1,replay_without_render=1,active=i+1,hardware=1,saves='disabled')+counters(1)
      if label=='first_log':alive[0]=None;return counters(1)
      if label=='tour_log':alive[0]=None;return tour().replace(b'won=ff',b'won=7f') if failure=='tour_bad' else tour()
      if label.startswith('baseline_v4'):return octal(saved())
      if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if '_overlay_' in label:return b'LUMA3D_HUD bank=20 bytes=192000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if label=='live_identity':return b'3010 (luma3d-pp1) S\n/tmp/luma3d-pp1\0--showcase\0\n'
      if 'prodockctl display' in cmd:presents[0]+=1;return f'DISPLAY presents={presents[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
      return b''
    def stop(tx,name,label,pidfile=t.LIVE):
     calls.append((label,name))
     if failure=='unpublished' and label=='cleanup_current':raise RuntimeError('PID not published')
     alive[0]=None
     if label==failure:raise KeyboardInterrupt('reply lost after TERM')
    def wait(*a,**kw):
     calls.append(('wait_read_only',a[2]))
     if failure=='tour_timeout' and a[2]=='pp1_tour':raise TimeoutError('tour')
     return 0
    def progress(*a):
     if failure=='live_progress' and a[3]=='live':raise RuntimeError('progress lost')
     return dict(presents=100)
    def identity(tx,label,*args):
     if failure=='live_after_save' and label=='live_after_save':raise AssertionError('candidate died during save readback')
     return dict(pid=2011,start_ticks=15755109)
    with contextlib.ExitStack() as s:
     for module in (t,):
      for name,value in [('identity',identity),('process',lambda *a:alive[0]==a[2]),('stop',stop),('progress',progress)]:s.enter_context(patch.object(module,name,value))
     for name,value in [('SAVE_SHA',hashlib.sha256(saved()).hexdigest()),('verify_regions',lambda *a:None),('preflight',lambda *a:m),('Transport',TX),('readback',lambda *a:None),('wait_exit',wait),('stop_baseline',lambda tx,e:stop(tx,t.BASE,'stop_sc1')),('abort_receiver',lambda *a:calls.append(('abort_receiver',getattr(a[0],'receiver_active',False))))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result'),'--expected-manifest',hashlib.sha256(b'{}').hexdigest()]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure:
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    result=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',result);self.assertFalse(any(k=='restore_sc1' for k,v in calls))
    else:self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure=='transfer':self.assertIn(('abort_receiver',True),calls);self.assertFalse(any(k=='stop_sc1' for k,v in calls))
    if failure is None:self.assertTrue(result['passed']);self.assertEqual(result['tour']['won'],255)
    for label,cmd in calls:
     if label.endswith('_launch'):self.assertNotIn('--save',cmd)

 def test_helper_owned_memory_bounds(self):
  if not (HERE/'runtime_inspect.c').exists():self.skipTest('Packaged helper pending')
  source='#define main helper_main\n#include "'+str(HERE/'runtime_inspect.c')+'"\n#undef main\n#include <assert.h>\nint main(void){assert(memory_region_valid(20u<<20,384000));assert(memory_region_valid(28u<<20,4u<<20));assert(memory_region_valid((32u<<20)-4,4));assert(!memory_region_valid(19u<<20,4));assert(!memory_region_valid(24u<<20,4));assert(!memory_region_valid(31u<<20,(1u<<20)+4));assert(!memory_region_valid(32u<<20,4));assert(!memory_region_valid(28u<<20,3));assert(!memory_region_valid((28u<<20)+1,4));return 0;}'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'bounds.c').write_text(source)
   subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(HERE),p/'bounds.c','-o',p/'bounds'],check=True)
   subprocess.run([p/'bounds'],check=True)

if __name__=='__main__':unittest.main()
