#!/usr/bin/env python3
"""GM1 negative parser, identity and recovery tests. No serial/board access."""
import contextlib,copy,hashlib,io,json,re,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
SOURCE=ROOT/'games/luma3d/candidates/mesh_cache_trial_r1'
sys.path.insert(0,str(HERE));sys.path.insert(1,str(ROOT/'games/luma3d/tests/hardware/polish_20261027_pp2_prepared_r2'))
import prodock_mesh_cache as t
g=t.guard
ANCHOR=dict(pid=2925,start_ticks=26240721)
def octal(b):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in b[i:i+16])).encode() for i in range(0,len(b),16))+f'\n{len(b):07o}\n'.encode()
def manifest():
 wp=json.loads((SOURCE/'probe_tests_r1/result.json').read_text());fp=json.loads((SOURCE/'fixtures_r1/result.json').read_text())
 ref=dict(file='ref.lz4',bytes=384000,crc32='11111111',offset=22<<20)
 binary=dict(bytes=100,sha256='0'*64,crc32='22222222');d=dict(file='delta',patch_bytes=10,patch_crc32='33333333')
 return dict(tag='mc1',helper='mc1-helper',baseline=binary,game=dict(binary=binary),motion_counters_available=dict(baseline=False,candidate=True),expected_identity=ANCHOR,transfer_files=['mc1-helper'],references=[ref],programs={v:dict(program=('luma3d-gm1' if v=='game' else 'mc1-'+v),binary=binary,delta=d) for v in ('baseline','candidate')},fixtures=[dict(kind=k,frames=n,restart_at=r,back_at=b,rect=None,ui=[ref],oracle=dict(vertices=0,triangles=0,slivers=0)) for k,n,r,b in t.FIXTURES],expected_windows=[[{k:p[k] for k in t.EXACT} for p in next(x['result']['phases'] for x in wp['records'] if x['variant']==v and x['kind']==kind and x['width']==800)] for v,kind in t.WINDOWS],expected_copies=[[{k:p[k] for k in t.COPY_EXACT} for p in next(x['result']['copies'] for x in wp['records'] if x['variant']==v and x['kind']==kind and x['width']==800)] for v,kind in t.WINDOWS],windows=[dict(variant=v,kind=k,frames=360) for v,k in t.WINDOWS],deadlines=dict(fixture=240,window=600,showcase=3700))
class Tests(unittest.TestCase):
 def test_identity_and_pid_replaced(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a));expected=dict(pid=2925,start_ticks=26240721)
  with patch.object(g,'identity',return_value=dict(pid=2925,start_ticks=26240722)):
   with self.assertRaises(AssertionError):g.stop_baseline(tx,expected)
  self.assertFalse(calls)
  prefix=b'2925 (luma3d-gm1) '+b' '.join([b'S']+[b'0']*18+[b'26240721'])+b'\n'
  args=b'/tmp/luma3d-gm1\0--showcase\0'
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
 def test_original_preserved_when_term_was_not_sent(self):
  anchor=dict(pid=2925,start_ticks=26240721);state=dict(baseline_identity=anchor);calls=[]
  tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(g,'identity',return_value=anchor),patch.object(g,'process',return_value=True),patch.object(g,'display',side_effect=[dict(presents=10),dict(presents=11)]),patch.object(g.time,'sleep',lambda *a:None):
   self.assertEqual(g.recover(tx,manifest(),None,False,state),dict(presents=11))
  self.assertEqual(state['identity'],anchor);self.assertFalse(state.get('attempted'));self.assertFalse(any(k=='restore_baseline' for k,c in calls))
 def test_exit_wait_is_read_only(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_mc1_window0:0\n'
   def write(self,b):raise AssertionError('write during measure')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'mc1_window0'),0)
  for args in ('--kind 4 --frames 360','--kind 6 --frames 600','--kind 4 --wall 20'):
   cmd=t.once('mc1-candidate','mc1_window0',args);subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True);self.assertNotIn('--save',cmd)
 def test_metrics_and_performance(self):
  raw=(SOURCE/'probe_tests_r1/candidate_4_800.log').read_bytes();d=t.parse(raw,4);self.assertEqual(d['phases'][2]['frames'],360)
  bad=[raw.replace(b'kind=4',b'kind=3',1),raw.replace(b'frames=360 ',b'frames=359 ',1),re.sub(rb'p99_upper_ms=\d+ ',b'p99_upper_ms=3 ',raw,count=1),raw.replace(b'GPU_DONE',b'LOST_DONE'),re.sub(rb'preparation=[^ ]+',b'preparation=nan',raw,count=1),re.sub(rb'max_index=[^ ]+',b'max_index=999999',raw,count=1),raw+b'LUMA3D_SAVE saved\n',re.sub(rb'queue_overflows=0',b'queue_overflows=1',raw,count=1),re.sub(rb'simulation=[^ ]+',b'simulation=100',raw,count=1)]
  for value in bad:
   with self.assertRaises((AssertionError,ValueError,KeyError)):t.parse(value,4)
  rows=[]
  for variant,kind in t.WINDOWS:
   v=copy.deepcopy(d)
   for p in v['phases']:p.update(wall=p['frames']*.04,fps=25.,p99_upper_ms=48.,max_frame=.06)
   rows.append(dict(variant=variant,kind=kind,result=v))
  self.assertTrue(all(x['accepted'] for x in t.compare(rows)))
  for field,value in [('wall',360*.05),('p99_upper_ms',68),('max_frame',.12),('p99_upper_ms',0)]:
   changed=copy.deepcopy(rows);changed[1]['result']['phases'][2][field]=value
   self.assertFalse(t.compare(changed)[0]['accepted'],field)
  rows[1]['result']['phases'][2]['state_crc32']='12345678'
  with self.assertRaises(AssertionError):t.compare(rows)
 def test_frozen_preflight(self):
  if not (HERE/'manifest.json').exists():self.skipTest('Packaging pending')
  m=t.preflight(HERE);original=t.json.loads
  for field in ('new_sha256','new_crc32','new_bytes'):
   changed=copy.deepcopy(m);changed['programs']['candidate']['delta'][field]='bad'
   def load(data,*a,**kw):
    v=original(data,*a,**kw);return changed if isinstance(v,dict) and v.get('tag')==m['tag'] else v
   with patch.object(t.json,'loads',load):
    with self.assertRaises(AssertionError):t.preflight(HERE)
  for section,field,value in [('expected_identity','start_ticks',1),('performance_policy','max_mean_ratio',2),('deadlines','fixture',500)]:
   changed=copy.deepcopy(m);changed[section][field]=value
   def load(data,*a,**kw):
    v=original(data,*a,**kw);return changed if isinstance(v,dict) and v.get('tag')==m['tag'] else v
   with patch.object(t.json,'loads',load):
    with self.assertRaises(AssertionError):t.preflight(HERE)
 def test_trial_always_restores_exact_gm1(self):
  for failure in (None,'transfer','stop_baseline','mc1_fixture0_launch','mc1_window1_timeout','bad_state','save_final','unpublished','performance'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'manifest.json').write_text('{}');m=manifest();calls=[];alive=[g.BASE];presents=[10]
    source=json.loads((SOURCE/'probe_tests_r1/result.json').read_text())
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
      if label=='launch_live':alive[0]='luma3d-gm1'
      if label==failure or (failure=='unpublished' and label=='mc1_window0_launch'):raise KeyboardInterrupt(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label.startswith('install_'):return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label=='verify_ref.lz4':return b'LUMA3D_VERIFY_OK bytes=384000 crc32=11111111\n'
      if label.endswith('_log'):
       alive[0]=None
       if label=='showcase_log':return b'LUMA3D_SHOWCASE_RESULT status=2 stage=16 loops=1 simulated=770 wall=800 visited=ff won=ff commands=1079 boss=1 checkpoint=1 crystals=1 hardware=1\n'
       return label.encode()
      if 'prodockctl display' in cmd:presents[0]+=1;return f'DISPLAY presents={presents[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
      return b''
    def parse(raw,kind,frames,fixture,hardware,*extra):
     self.assertTrue(hardware)
     if fixture:return dict(phases=[],counters=[],top=[],done={},last=[dict(vertices=0,triangles=0,slivers=0)])
     i=int(re.search(rb'window(\d+)',raw)[1]);v,k=t.WINDOWS[i];value=copy.deepcopy(next(x['result'] for x in source['records'] if x['variant']==v and x['kind']==k and x['width']==800))
     for p in value['phases']:p.update(wall=p['frames']*.04,fps=25.,p99_upper_ms=48.,max_frame=.06)
     if failure=='bad_state' and i==1:value['phases'][2]['state_crc32']='deadbeef'
     if failure=='performance' and i==1:value['phases'][2]['wall']*=2
     return value
    def stop_baseline(*a):
     alive[0]=None
     if failure=='stop_baseline':raise KeyboardInterrupt('lost after TERM')
    def recover(tx,m,current,ever,state):
     if current and failure=='unpublished':raise RuntimeError('PID not published')
     calls.append(('recover',current));alive[0]=g.BASE;state.update(identity=dict(pid=3000,start_ticks=7));return dict(presents=100)
    def identity(tx,label,*a):
     if label==failure:raise AssertionError('died during late save')
     return ANCHOR if label in ('initial_gm1','before_switch') else dict(pid=3000,start_ticks=7)
    def wait(uart,out,tag,**kw):
     if tag+'_timeout'==failure:raise TimeoutError('window timeout')
     return 0
    def save(tx,label,*a):
     if label==failure:raise AssertionError('save changed')
     return dict(sha256=g.SAVE_SHA)
    with contextlib.ExitStack() as s:
     for name,value in [('identity',identity),('recover',recover),('stop_baseline',stop_baseline)]:s.enter_context(patch.object(g,name,value))
     for name,value in [('preflight',lambda *a:m),('Transport',TX),('raw_verify',lambda *a:None),('readback',lambda *a:None),('verify_regions',lambda *a:None),('parse',parse),('game_counters',lambda *a:dict(vertices=0,triangles=0,slivers=0)),('wait_exit',wait),('saved_bytes',save),('abort_receiver',lambda *a:calls.append(('abort',a[0].receiver_active))),('progress',lambda *a:dict(presents=100))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure and failure!='performance':
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.trial(root,root/'result',hashlib.sha256(b'{}').hexdigest())
     else:t.trial(root,root/'result',hashlib.sha256(b'{}').hexdigest())
    record=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',record);self.assertFalse(any(k=='recover' for k,c in calls))
    elif failure is None:self.assertEqual(alive[0],'luma3d-gm1');self.assertTrue(record['passed']);self.assertTrue(record['performance_accepted']);self.assertTrue(record['restored_gm1']);self.assertFalse(record['candidate_promoted'])
    else:self.assertEqual(alive[0],g.BASE)
    if failure=='transfer':self.assertIn(('abort',True),calls);self.assertFalse(any(k=='recover' for k,c in calls))
    if failure=='performance':self.assertTrue(record['functional_passed']);self.assertTrue(record['passed']);self.assertTrue(record['restored_gm1']);self.assertFalse(any(k=='launch_live' for k,c in calls))
    for label,cmd in calls:
     if label.endswith('_launch') or label=='launch_live':self.assertNotIn('--save',cmd)
if __name__=='__main__':unittest.main()
