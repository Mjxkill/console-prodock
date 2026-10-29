#!/usr/bin/env python3
"""MO1 local parser/identity/failure tests. No serial or board access."""
import contextlib,hashlib,io,json,re,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
sys.path.insert(0,str(HERE));sys.path.insert(1,str(ROOT/'games/luma3d/tests/hardware/polish_20261027_pp2_prepared_r2'))
import prodock_motion as t
g=t.guard
def octal(b):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in b[i:i+16])).encode() for i in range(0,len(b),16))+f'\n{len(b):07o}\n'.encode()
def line(name,**kw):return (name+' '+' '.join(f'{k}={v}' for k,v in kw.items())+'\n').encode()
def result(kind=4,frames=360,wall=0):
 count=frames or 200;elapsed=20 if wall else count*.1
 raw=line('MOTION_PROBE',kind=kind,replay_steps=37275,replay_without_render=1,fixed_frames=frames,wall_seconds=wall,hardware=1,saves='disabled')
 raw+=line('MOTION_COMPLETION',activity_exit=0,showcase_status=1,active=kind+1)
 raw+=line('MOTION_RESULT',kind=kind,frames=count,simulated=f'{count/60 if frames else 19.9:.6f}',wall=elapsed,simulation=elapsed*.001,preparation=elapsed*.4,submit=0 if kind==6 else elapsed*.4,present=elapsed*.1,ui_raster=.004,ui_publish=.004,scan_bytes=1234,restore_bytes=0,ui_bytes=100,commands=0 if kind==6 else 100,batches=0 if kind==6 else 10,p95_upper_ms=100,p99_upper_ms=104,overflow=0,max_frame=.1,frame_sum=elapsed,state_crc32='12345678',moves=10,teleports=0,queue_overflows=0,hardware=1,ok=1)
 return raw+line('LUMA3D_COUNTERS',errors=0,underflows=0,fault=0,geometry_errors=0,vertices=0 if kind==6 else 10,triangles=0 if kind==6 else 5,slivers=0,frames=count)
def manifest():
 ref=dict(file='ref.lz4',bytes=384000,crc32='11111111',offset=22<<20)
 binary=dict(bytes=100,sha256='0'*64,crc32='22222222')
 d=dict(file='delta',patch_bytes=10,patch_crc32='33333333')
 return dict(tag='mo1',helper='mo1-helper',baseline=binary,expected_identity=dict(pid=2472,start_ticks=21513398),transfer_files=['mo1-helper'],references=[ref],probes={v:dict(program='mo1-'+v,binary=binary,delta=d) for v in ('baseline','candidate')},fixtures=[dict(kind=k,pixels=None,region=ref,oracle=dict(vertices=10 if k==4 else 0,triangles=5 if k==4 else 0,slivers=0)) for k in (4,6)],windows=t.WINDOWS,wall=dict(kind=4,seconds=20),deadlines=dict(fixture=180,window=600,wall=120))

class Tests(unittest.TestCase):
 def test_metrics(self):
  d=t.parse_result(result(),4,360)['result'];self.assertAlmostEqual(d['fps'],10);self.assertAlmostEqual(d['preparation_ms_per_frame'],40)
  t.parse_result(result(6,600),6,600);t.parse_result(result(4,0,20),4,wall=20)
  invalid=[result().replace(b'preparation=14.4',b'preparation=nan'),result().replace(b'frames=360',b'frames=359'),result().replace(b'queue_overflows=0',b'queue_overflows=1'),result().replace(b'state_crc32=12345678',b'state_crc32=bad'),result().replace(b'p99_upper_ms=104',b'p99_upper_ms=105'),result().replace(b'geometry_errors=0',b'geometry_errors=1'),re.sub(rb'simulation=[^ ]+',b'simulation=100',result()),result()+b'LUMA3D_SAVE saved\n',result().replace(b'showcase_status=1',b'showcase_status=3')]
  for raw in invalid:
   with self.assertRaises((AssertionError,ValueError)):t.parse_result(raw,4,360)
  rows=[dict(**w,measurement=t.parse_result(result(w['kind'],w['frames']),w['kind'],w['frames'])) for w in t.WINDOWS]
  self.assertEqual(len(t.compare(rows)),2)
  rows[1]['measurement']['result']['state_crc32']='12345679'
  with self.assertRaises(AssertionError):t.compare(rows)
 def test_identity_and_pid_replaced(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a));expected=dict(pid=2472,start_ticks=21513398)
  with patch.object(g,'identity',return_value=dict(pid=2472,start_ticks=21513399)):
   with self.assertRaises(AssertionError):g.stop_baseline(tx,expected)
  self.assertFalse(calls)
  prefix=b'2472 (luma3d-pp1) '+b' '.join([b'S']+[b'0']*18+[b'21513398'])+b'\n'
  args=b'/tmp/luma3d-pp1\0--showcase\0'
  with patch.object(g,'process',return_value=True):
   self.assertEqual(g.identity(types.SimpleNamespace(run=lambda *a:prefix+octal(args)),'id'),expected)
   for extra in (b'--save\0/tmp/x\0',b'\n--save\0/tmp/x\0',b'\r--save\0/tmp/x\0',b'\0'):
    with self.assertRaises(AssertionError):g.identity(types.SimpleNamespace(run=lambda *a:prefix+octal(args+extra)),'id')
 def test_recovery_idempotent_and_final_identity(self):
  calls=[];state={};tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(g,'identity',return_value=dict(pid=3000,start_ticks=7)),patch.object(g,'progress',side_effect=[TimeoutError('lost reply'),dict(presents=5)]):
   with self.assertRaises(TimeoutError):g.recover(tx,manifest(),None,True,state)
   self.assertEqual(g.recover(tx,manifest(),None,True,state),dict(presents=5))
  self.assertEqual(sum(k=='restore_baseline' for k,c in calls),1)
  calls=[];state={}
  with patch.object(g,'identity',side_effect=[dict(pid=3000,start_ticks=7),AssertionError('died during display')]),patch.object(g,'progress',return_value=dict(presents=11)):
   with self.assertRaises(AssertionError):g.recover(tx,manifest(),None,True,state)
  with patch.object(g,'identity',side_effect=AssertionError('still dead')):
   with self.assertRaises(AssertionError):g.recover(tx,manifest(),None,True,state)
  self.assertEqual(sum(k=='restore_baseline' for k,c in calls),1);self.assertFalse(any(k=='publish_restored_pid' for k,c in calls))
 def test_exit_wait_is_read_only(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_mo1_window0:0\n'
   def write(self,b):raise AssertionError('write during measure')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'mo1_window0'),0)
  for args in ('--kind 4 --frames 360','--kind 6 --frames 600','--kind 4 --wall 20'):
   cmd=t.once('mo1-candidate','mo1_window0',args);subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True);self.assertNotIn('--save',cmd)
 def test_frozen_preflight(self):
  if not (HERE/'manifest.json').exists():self.skipTest('Packaging pending')
  m=t.preflight(HERE);original=t.json.loads
  for field in ('new_sha256','new_crc32','new_bytes'):
   changed=json.loads(json.dumps(m));changed['probes']['candidate']['delta'][field]='bad'
   def load(data,*a,**kw):
    v=original(data,*a,**kw);return changed if isinstance(v,dict) and v.get('tag')==m['tag'] else v
   with patch.object(t.json,'loads',load):
    with self.assertRaises(AssertionError):t.preflight(HERE)
 def test_main_failures_restore_exact_r6(self):
  for failure in (None,'transfer','stop_baseline','mo1_fixture4_launch','mo1_window1_timeout','bad_state','mo1_wall_launch','save_final','unpublished'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'manifest.json').write_text('{}');m=manifest();calls=[];alive=[g.BASE];presents=[10];recovery={}
    class UART:
     def __enter__(self):return self
     def __exit__(self,*a):return False
     def write(self,b):calls.append(('uart_write',b))
     def read(self,n):return b''
     def flush(self):pass
    class TX:
     def __init__(self,*a):self.receiver_active=False
     def transfer(self,*a):
      self.receiver_active=True
      if failure=='transfer':raise KeyboardInterrupt('transfer')
      self.receiver_active=False;return dict(bytes=1)
     def run(self,label,cmd,*a):
      calls.append((label,cmd))
      if label.endswith('_launch'):alive[0]='probe'
      if label==failure or (failure=='unpublished' and label=='mo1_window0_launch'):raise KeyboardInterrupt(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label.startswith('install_'):return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label=='verify_ref.lz4':return b'LUMA3D_VERIFY_OK bytes=384000 crc32=11111111\n'
      if label.endswith('_log'):
       alive[0]=None
       if 'fixture' in label:return result(4 if 'fixture4' in label else 6,1)
       if 'wall' in label:return result(4,0,20)
       i=int(re.search(r'window(\d)',label)[1]);w=t.WINDOWS[i];raw=result(w['kind'],w['frames'])
       return raw.replace(b'state_crc32=12345678',b'state_crc32=bad') if failure=='bad_state' and i==1 else raw
      if 'prodockctl display' in cmd:presents[0]+=1;return f'DISPLAY presents={presents[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
      return b''
    def stop_baseline(*a):
     alive[0]=None
     if failure=='stop_baseline':raise KeyboardInterrupt('lost after TERM')
    def recover(tx,m,current,ever,state):
     if current and failure=='unpublished':raise RuntimeError('PID not published')
     calls.append(('recover',current));alive[0]=g.BASE;state.update(identity=dict(pid=3000,start_ticks=7));return dict(presents=100)
    def identity(tx,label,*a):return dict(pid=2472,start_ticks=21513398) if label in ('initial_r6','before_switch') else dict(pid=3000,start_ticks=7)
    def wait(uart,out,tag,**kw):
     if tag+'_timeout'==failure:raise TimeoutError('window timeout')
     return 0
    def save(tx,label,*a):
     if label==failure:raise AssertionError('save changed')
     return dict(sha256=g.SAVE_SHA)
    with contextlib.ExitStack() as s:
     for name,value in [('identity',identity),('recover',recover),('stop_baseline',stop_baseline)]:s.enter_context(patch.object(g,name,value))
     for name,value in [('preflight',lambda *a:m),('Transport',TX),('raw_verify',lambda *a:None),('readback',lambda *a:None),('verify_regions',lambda *a:None),('verify_pixels',lambda *a:None),('wait_exit',wait),('saved_bytes',save),('abort_receiver',lambda *a:calls.append(('abort',a[0].receiver_active)))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result'),'--expected-manifest',hashlib.sha256(b'{}').hexdigest()]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure:
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    record=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',record);self.assertFalse(any(k=='recover' for k,c in calls))
    else:self.assertEqual(alive[0],g.BASE)
    if failure=='transfer':self.assertIn(('abort',True),calls);self.assertFalse(any(k=='recover' for k,c in calls))
    if failure is None:self.assertTrue(record['passed']);self.assertTrue(record['restored_r6'])
    for label,cmd in calls:
     if label.endswith('_launch'):self.assertNotIn('--save',cmd)
if __name__=='__main__':unittest.main()
