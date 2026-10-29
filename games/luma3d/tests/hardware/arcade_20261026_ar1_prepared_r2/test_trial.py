#!/usr/bin/env python3
"""Fault injection only: never opens a board, CDC, GPU, or JTAG connection."""
import contextlib,hashlib,io,json,re,struct,subprocess,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
REPO=next((p for p in HERE.parents if (p/'games/luma3d/tools').is_dir()),None)
sys.path.insert(0,str(HERE))
if not (HERE/'prodock_order.py').exists():sys.path.insert(1,str(REPO/'games/luma3d/tests/hardware/paths_20261026_op2_prepared_r1'))
import prodock_arcade as t

def octal(data):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in data[i:i+16])).encode() for i in range(0,len(data),16))
def blob(version=5,won=255,active=0):
 data=bytearray(5292 if version==4 else 360);data[:8]=b'L3PROG1\0';struct.pack_into('<3I',data,8,len(data),0x56414c31,version)
 if version==4:struct.pack_into('<8I',data,136,0x34414354,5,active,31,31,1,0,1)
 else:
  struct.pack_into('<8I',data,136,0x35414354,128,0,0,0,0,0,1)
  struct.pack_into('<8I',data,232,0x31435241,128,1,0,active,255,won,1)
  struct.pack_into('<I',data,244,zlib.crc32(data[248:]))
 struct.pack_into('<I',data,20,zlib.crc32(data[24:]));return bytes(data)
def line(prefix,d):return (prefix+' '+' '.join(str(k)+'='+str(v) for k,v in d.items())+'\n').encode()
def counters(frames=3,vertices=0,triangles=0):return line('LUMA3D_COUNTERS',dict(errors=0,underflows=0,fault=0,geometry_errors=0,vertices=vertices,triangles=triangles,slivers=0,frames=frames))
def bench(s,elapsed=3):
 return (line('LUMA3D_BENCHMARK',dict(pose=0,warmup=3,measured_frames=30,fixed_pose=1,hardware=1))+
 line('LUMA3D_RESULT',dict(frames=30,elapsed=elapsed,fps=30/elapsed,commands=60,batches=30,draws_last=1,triangles_last=2,benchmark=1,hardware=1,warmup=3))+
 counters(33,99,66)+line('LUMA3D_BENCHMARK_COUNTERS',dict(cycles=1,vertices=90,raster_triangles=60,culled=0,intersections=0,slivers=0,feed_us=1,wait_us=1,cache_us=1,present_us=1)))
def manifest():
 ref=dict(file='ref.lz4',bytes=192000,crc32='11111111',bank=20)
 scenes=[dict(variant=v,pose=0,pixels=ref,hud=ref,oracle=dict(vertices=3,triangles=2,slivers=0),host_benchmark=dict(commands=60,batches=30,draws_last=1,triangles_last=2)) for v in ('op2','new','op2')]
 fixtures=[]
 for name in ['activity_5_flash','activity_5_input','activity_6','activity_6_boss','activity_7','activity_7_mid']:
  active=int(name.split('_')[1])+1
  region=dict(ref,offset=22<<20);regions=[region,dict(region,offset=23<<20)]
  if active==7:regions.extend([dict(ref,offset=28<<20,bytes=491520),dict(ref,offset=30<<20,bytes=65536)])
  fixtures.append(dict(name=name,fixture_name='ar1-'+name+'.save',state=dict(file='state.lz4',bytes=360,crc32='11111111',sha256=hashlib.sha256(blob(active=active)).hexdigest()),pixels=None if active==7 else ref,regions=regions,oracle=dict(vertices=0,triangles=0,slivers=0),host_scene=dict(active=active,won=0,region=1,fixed_fixture=1,frames=3,commands=0,batches=0,draws_last=0,triangles_last=0,mini_uploads=2,mini_bytes=768000),host_present=dict(layers=1,sprites=int(active==7),palette_crc=1,descriptor_crc=2,cpu_descriptor=1)))
 return dict(tag='ar1',program='luma3d-ar1',probe='ar1-probe',helper='ar1-helper',game=dict(bytes=100,crc32='22222222'),baseline=dict(bytes=100,crc32='22222222'),probe_binary=dict(bytes=100,crc32='22222222'),transfer_files=['ar1-helper'],delta=dict(file='delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),probe_delta=dict(file='probe_delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),benchmarks=scenes,fixtures=fixtures,acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05),host_replay=dict(won=255,active=0,region=1,phase=4,met_nils=1,reloads=8,input_steps=18926,activity_steps=1351,zero_dt_steps=589,rendered_frames=1934,accelerated_replay=1),resume_expected=dict(sha256=hashlib.sha256(blob(active=7)).hexdigest()))

class Tests(unittest.TestCase):
 def test_candidate_term_binds_start_ticks_and_rejects_reuse(self):
  stat=b'52 (ar1-probe) '+b' '.join([b'S']+[b'0']*18+[b'81234'])+b'\n';calls=[]
  def run(label,cmd):
   calls.append((label,cmd))
   if label.endswith('_stat'):return stat
   if '_after_' in label:return b'STOPPED\n'
   return b''
  with patch.object(t,'process',return_value=True):t.stop(types.SimpleNamespace(run=run),'ar1-probe','stop','/tmp/ar1_replay.pid')
  cmd=next(c for n,c in calls if n=='stop_term_guarded');self.assertIn('shift 21 && test "$1" = 81234 && kill -TERM 52',cmd)
  subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True)
  def reused(label,cmd):return stat.replace(b'81234',b'81235') if '_after_' in label else run(label,cmd)
  with patch.object(t,'process',return_value=True):
   with self.assertRaises(AssertionError):t.stop(types.SimpleNamespace(run=reused),'ar1-probe','stop','/tmp/ar1_replay.pid')
 def test_new_banks_compared_exactly_and_mismatch_rejected(self):
  refs=[dict(file='stars.lz4',offset=28<<20,bytes=491520,crc32='12345678'),dict(file='sprite.lz4',offset=30<<20,bytes=65536,crc32='12345678')];calls=[]
  def run(label,cmd,*a):
   calls.append(cmd);p=cmd.split();return f'LUMA3D_MEMORY offset={p[3]} bytes={p[4]} mismatch=0 actual_crc=12345678 expected_crc=12345678\n'.encode()
  t.verify_regions(types.SimpleNamespace(run=run),'ar1-helper','native',refs);self.assertEqual(len(calls),2)
  with self.assertRaises(AssertionError):t.verify_regions(types.SimpleNamespace(run=lambda *a:run(*a).replace(b'mismatch=0',b'mismatch=1')),'ar1-helper','bad',refs)
 def test_bundle_preflight_if_frozen(self):
  if not (HERE/'manifest.json').exists():self.skipTest('Source tests; frozen bundle preflight runs after packaging')
  m=t.preflight(HERE);self.assertEqual(m['game']['sha256'],t.NEW_SHA)
  # Mutate only in-memory manifest links; no frozen file is edited.
  original=t.json.loads
  for key in ('delta','probe_delta'):
   changed=json.loads(json.dumps(m));changed[key]['new_sha256']='0'*64
   def load(data,*a,**kw):
    v=original(data,*a,**kw)
    return changed if isinstance(v,dict) and v.get('tag')==m['tag'] and 'benchmarks' in v else v
   with patch.object(t.json,'loads',load):
    with self.assertRaises(AssertionError):t.preflight(HERE)
 def test_save_length_crc_and_extensions(self):
  for version in (4,5):
   data=blob(version);tx=types.SimpleNamespace(run=lambda *a:octal(data));self.assertEqual(t.saved_bytes(tx,'s','/tmp/test',version)['bytes'],len(data))
   for at in (0,8,12,16,20,100,len(data)-1):
    bad=bytearray(data);bad[at]^=1
    with self.assertRaises(AssertionError):t.saved_bytes(types.SimpleNamespace(run=lambda *a:octal(bad)),'s','/tmp/test',version)
  bad=bytearray(blob(4));struct.pack_into('<I',bad,144,6);struct.pack_into('<I',bad,20,zlib.crc32(bad[24:]))
  with self.assertRaises(AssertionError):t.saved_bytes(types.SimpleNamespace(run=lambda *a:octal(bad)),'s','/tmp/test',4)
 def test_process_identity_and_save_path_are_exact(self):
  rest=[b'S']+[b'0']*18+[b'123456'];stat=b'42 (luma3d-op2) '+b' '.join(rest)
  raw=stat+b'\n/tmp/luma3d-op2\0--save\0/tmp/op2-live.save\0\n'
  with patch.object(t,'process',lambda *a:True):
   self.assertEqual(t.identity(types.SimpleNamespace(run=lambda *a:raw),'id'),dict(pid=42,start_ticks=123456))
   for bad in (raw.replace(b'op2-live.save',b'ws1-live.save'),raw.replace(b') S ',b') Z '),raw[:-1]+b'--save\0/tmp/another.save\0\n',raw.replace(b'--save\0',b'')):
    with self.assertRaises(AssertionError):t.identity(types.SimpleNamespace(run=lambda *a:bad),'id')
 def test_shell_suffix_and_specific_pid(self):
  cmd=t.once('ar1-probe','ar1_replay','--replay /tmp/ar1-replay.save')
  self.assertLess(cmd.index('> /tmp/ar1_replay.pid'),cmd.index('wait "$p"'));self.assertNotIn(t.LIVE,cmd)
  subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True)
 def test_fixed_limits_and_no_gain_promotion(self):
  m=manifest();scenes=[dict(result=dict(elapsed=3.)) for _ in range(3)];self.assertTrue(t.decision(scenes,m['acceptance'])['accepted'])
  scenes[1]['result']['elapsed']=3.4;self.assertFalse(t.decision(scenes,m['acceptance'])['accepted']);scenes[1]['result']['elapsed']=3
  scenes[2]['result']['elapsed']=2.7;self.assertFalse(t.decision(scenes,m['acceptance'])['accepted'])
 def test_unpublished_pid_refuses_second_gpu(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(t,'stop',side_effect=RuntimeError('PID not published')):
   with self.assertRaises(RuntimeError):t.recover(tx,manifest(),('ar1-probe','/tmp/ar1_replay.pid'),True,{})
  self.assertFalse(calls)
 def test_pid_replacement_during_announcement_never_receives_term(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a));expected=dict(pid=1604,start_ticks=12329285)
  # Includes PID reuse: same PID/comm, different start ticks.
  for changed in (dict(pid=1605,start_ticks=12329290),dict(pid=1604,start_ticks=12329290)):
   with patch.object(t,'identity',lambda *a:changed):
    with self.assertRaises(AssertionError):t.stop_baseline(tx,expected)
  self.assertFalse(calls)
  def run(label,cmd):calls.append((label,cmd));return b'STOPPED\n'
  with patch.object(t,'identity',lambda *a:expected):t.stop_baseline(types.SimpleNamespace(run=run),expected)
  command=calls[0][1];self.assertIn('shift 21 && test "$1" = 12329285 && kill -TERM 1604',command);self.assertNotIn('kill -TERM "$p"',command)
  subprocess.run(['sh','-n','-c',command+'; printf DONE'],check=True)
 def test_recovery_is_idempotent_after_launch_or_progress_reply_failure(self):
  for fault in ('launch','progress'):
   calls=[];state={};progress_calls=[0]
   def run(label,cmd):
    calls.append((label,cmd))
    if fault=='launch' and label=='restore_op2':raise TimeoutError('reply lost after background launch')
   def progress(*args):
    progress_calls[0]+=1
    if fault=='progress' and progress_calls[0]==1:raise RuntimeError('first progress query failed')
    return dict(presents=30)
   with patch.object(t,'process',lambda *a:True),patch.object(t,'progress',progress):
    with self.assertRaises((RuntimeError,TimeoutError)):t.recover(types.SimpleNamespace(run=run),manifest(),None,True,state)
    self.assertEqual(t.recover(types.SimpleNamespace(run=run),manifest(),None,True,state),dict(presents=30))
   self.assertEqual(sum(label=='restore_op2' for label,cmd in calls),1)
 def test_terminating_baseline_is_not_misreported_as_preserved(self):
  calls=[];count=[10];expected=dict(pid=1604,start_ticks=12329285)
  def run(label,cmd):
   calls.append((label,cmd));count[0]+=1
   return f'DISPLAY presents={count[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
  with patch.object(t,'process',side_effect=[True,False]),patch.object(t,'identity',return_value=expected),patch.object(t.time,'sleep',lambda *a:None),patch.object(t,'progress',return_value=dict(presents=40)):
   result=t.recover(types.SimpleNamespace(run=run),manifest(),None,False,dict(baseline_identity=expected))
  self.assertEqual(result,dict(presents=40));self.assertEqual(sum(label=='restore_op2' for label,cmd in calls),1)
 def test_real_wait_uses_read_only(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_ar1_fixture:0\n'
   def write(self,b):raise AssertionError('write during window')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'ar1_fixture'),0)
 def test_flow_failures_abort_then_restore_and_success(self):
  failures=(None,'transfer','install_delta','stop_op2','ar1_bench1_launch','ar1_bench1_pixels','slow','ar1_activity_7_mid_launch','ar1_activity_6_boss_memory_2','replay_timeout','replay_save','resume_launch','live_launch','unpublished')
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
      calls.append(('transfer',a));self.receiver_active=True
      if failure=='transfer':raise KeyboardInterrupt('transfer')
      self.receiver_active=False;return dict(bytes=1)
     def run(self,label,cmd,*a):
      calls.append((label,cmd))
      if label==failure or (failure=='unpublished' and label=='ar1_activity_7_mid_launch'):
       if label.endswith('_launch'):alive[0]=m['probe'] if 'activity_' in label else m['program'];raise KeyboardInterrupt(label)
       raise RuntimeError(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label.startswith('install_'):return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
      if label.startswith('unpack_'):return b'LUMA3D_UNPACK_OK bytes=360 crc32=11111111\n'
      if label in ('baseline_file','baseline_running_image'):return b'LUMA3D_RAW_OK bytes=100 crc32=22222222\n'
      if label=='restore_op2':alive[0]=t.BASE
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if match:=re.fullmatch(r'ar1_bench(\d)_log',label):
       alive[0]=None;return bench(m['benchmarks'][int(match[1])],3.4 if failure=='slow' and match[1]=='1' else 3.)
      if match:=re.fullmatch(r'ar1_(activity_[5-7](?:_mid|_flash|_boss|_input)?)_log',label):
       alive[0]=None;s=next(s for s in m['fixtures'] if s['name']==match[1]);return line('AR_SCENE',s['host_scene'])+line('AR_PRESENT',s['host_present'])+line('AR_RENDER',dict(frames=3,elapsed=1.0))+counters()+b'AR_PASS\n'
      if label=='replay_log':
       alive[0]=None;return line('AR_COMPLETE',m['host_replay'])+line('AR_RENDER',dict(frames=1934,elapsed=30.0))+counters(1934)+b'AR_RELOAD active=1\n'*8+b'AR_PASS\n'
      if label=='replay_codec':return b'AR_SAVE won=255\n'
      if label=='resume_log':alive[0]=None;return b'LUMA3D_SAVE loaded\nLUMA3D_SAVE saved\n'+counters(1)
      if label in ('baseline_v4_stopped','baseline_v4_final','baseline_v4_after_live'):return octal(blob(4))
      if label=='replay_save':return octal(blob())
      if label=='resume_save':return octal(blob(active=7))
      if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if '_memory_' in label:
       parts=cmd.split();return f'LUMA3D_MEMORY offset={parts[3]} bytes={parts[4]} mismatch=0 actual_crc={parts[5]} expected_crc={parts[5]}\n'.encode()
      if '_overlay_' in label:return f'LUMA3D_HUD bank={label[-2:]} bytes=192000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'.encode()
      if 'prodockctl display' in cmd:presents[0]+=1;return f'DISPLAY presents={presents[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
      return b''
    def stop(tx,name,label,pidfile=t.LIVE):
     calls.append((label,name))
     if failure=='unpublished' and label=='cleanup_current':raise RuntimeError('PID not published')
     alive[0]=None
     if label==failure:raise KeyboardInterrupt('stop reply lost after TERM')
    def wait(*a,**kw):
     calls.append(('wait_read_only',a[2]))
     if failure=='replay_timeout' and a[2]=='ar1_replay':raise TimeoutError('replay')
     return 0
    with contextlib.ExitStack() as s:
     for name,value in [('preflight',lambda *a:m),('identity',lambda *a:dict(pid=1604,start_ticks=12329285)),('Transport',TX),('readback',lambda *a:None),('wait_exit',wait),('process',lambda *a:alive[0]==a[2]),('stop',stop),('stop_baseline',lambda tx,expected:stop(tx,t.BASE,'stop_op2')),('progress',lambda *a:dict(presents=100)),('abort_receiver',lambda *a:calls.append(('abort_receiver',getattr(a[0],'receiver_active',False))))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result'),'--expected-manifest',hashlib.sha256(b'{}').hexdigest()]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure not in (None,'slow'):
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    result=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',result);self.assertFalse(any(k=='restore_op2' for k,v in calls))
    else:self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure=='transfer':self.assertIn(('abort_receiver',True),calls);self.assertFalse(any(k=='stop_op2' for k,v in calls))
    if failure=='install_delta':self.assertFalse(any(k=='stop_op2' for k,v in calls))
    if failure is None:self.assertTrue(result['passed']);self.assertEqual(len(result['fixtures']),6);self.assertEqual(result['resume_save']['active'],7)
    if failure=='slow':self.assertFalse(result['passed']);self.assertTrue(result['restored_op2']);self.assertFalse(result['fixtures'])

if __name__=='__main__':unittest.main()
