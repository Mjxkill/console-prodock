#!/usr/bin/env python3
"""Fault injection only: never opens a board, CDC, GPU, or JTAG connection."""
import contextlib,hashlib,io,json,re,struct,subprocess,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
REPO=next((p for p in HERE.parents if (p/'games/luma3d/tools').is_dir()),None)
sys.path.insert(0,str(HERE))
if not (HERE/'prodock_order.py').exists():sys.path.insert(1,str(REPO/'games/luma3d/tests/hardware/amber_20261025_am1'))
import prodock_paths as t

def octal(data):return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in data[i:i+16])).encode() for i in range(0,len(data),16))
def blob(version=4,won=31,active=0):
 data=bytearray(5292 if version==4 else 136);data[:8]=b'L3PROG1\0';struct.pack_into('<3I',data,8,len(data),0x56414c31,version)
 if version==4:struct.pack_into('<8I',data,136,0x34414354,5,active,31,won,1,0,1)
 struct.pack_into('<I',data,20,zlib.crc32(data[24:]));return bytes(data)
def line(prefix,d):return (prefix+' '+' '.join(str(k)+'='+str(v) for k,v in d.items())+'\n').encode()
def counters(frames=3,vertices=0,triangles=0):return line('LUMA3D_COUNTERS',dict(errors=0,underflows=0,fault=0,geometry_errors=0,vertices=vertices,triangles=triangles,slivers=0,frames=frames))
def bench(s,elapsed=3):
 return (line('LUMA3D_BENCHMARK',dict(pose=0,warmup=3,measured_frames=30,fixed_pose=1,hardware=1))+
 line('LUMA3D_RESULT',dict(frames=30,elapsed=elapsed,fps=30/elapsed,commands=60,batches=30,draws_last=1,triangles_last=2,benchmark=1,hardware=1,warmup=3))+
 counters(33,99,66)+line('LUMA3D_BENCHMARK_COUNTERS',dict(cycles=1,vertices=90,raster_triangles=60,culled=0,intersections=0,slivers=0,feed_us=1,wait_us=1,cache_us=1,present_us=1)))
def manifest():
 ref=dict(file='ref.lz4',bytes=192000,crc32='11111111',bank=20)
 scenes=[dict(variant=v,pose=0,pixels=ref,hud=ref,oracle=dict(vertices=3,triangles=2,slivers=0),host_benchmark=dict(commands=60,batches=30,draws_last=1,triangles_last=2)) for v in ('am1','new','am1')]
 fixtures=[]
 for name in ['garden','house_entry',*['activity_'+str(i) for i in range(5)]]:
  active=int(name[-1])+1 if name.startswith('activity') else 0
  fixtures.append(dict(name=name,fixture_name='op1-'+name+'.save',state=dict(file='state.lz4',bytes=5292,crc32='11111111',sha256=hashlib.sha256(blob(active=1)).hexdigest()),pixels=None if active in (1,2,3,4) else ref,hud=dict(ref,bank=22 if active else 20),oracle=dict(vertices=0,triangles=0,slivers=0),host_scene=dict(active=active,won=0,region=1,fixed_fixture=1,frames=3,commands=0,batches=0,draws_last=0,triangles_last=0,mini_uploads=2,mini_bytes=768000),host_present=dict(layers=1,palette_crc=1,descriptor_crc=2,cpu_descriptor=1)))
 return dict(tag='op1',program='luma3d-op1',probe='op1-probe',helper='op1-helper',game=dict(bytes=100,crc32='22222222'),baseline=dict(bytes=100,crc32='22222222'),probe_binary=dict(bytes=100,crc32='22222222'),transfer_files=['op1-helper'],delta=dict(file='delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),probe_delta=dict(file='probe_delta',patch_bytes=10,patch_crc32='33333333',new_bytes=100,new_crc32='22222222'),benchmarks=scenes,fixtures=fixtures,acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05),host_replay=dict(won=31,active=0,region=1,phase=4,met_nils=1,reloads=5,input_steps=16544,rendered_frames=426,accelerated_replay=1))

class Tests(unittest.TestCase):
 def test_save_length_crc_and_extensions(self):
  for version in (3,4):
   data=blob(version);tx=types.SimpleNamespace(run=lambda *a:octal(data));self.assertEqual(t.saved_bytes(tx,'s','/tmp/test',version)['bytes'],len(data))
   for at in (0,8,12,16,20,100,len(data)-1):
    bad=bytearray(data);bad[at]^=1
    with self.assertRaises(AssertionError):t.saved_bytes(types.SimpleNamespace(run=lambda *a:octal(bad)),'s','/tmp/test',version)
  bad=bytearray(blob());struct.pack_into('<I',bad,144,6);struct.pack_into('<I',bad,20,zlib.crc32(bad[24:]))
  with self.assertRaises(AssertionError):t.saved_bytes(types.SimpleNamespace(run=lambda *a:octal(bad)),'s','/tmp/test',4)
 def test_process_identity_and_save_path_are_exact(self):
  rest=[b'S']+[b'0']*18+[b'123456'];stat=b'42 (luma3d-am1) '+b' '.join(rest)
  raw=stat+b'\n/tmp/luma3d-am1\0--save\0/tmp/op1-am1-recovery.save\0\n'
  with patch.object(t,'process',lambda *a:True):
   self.assertEqual(t.identity(types.SimpleNamespace(run=lambda *a:raw),'id'),dict(pid=42,start_ticks=123456))
   for bad in (raw.replace(b'op1-am1-recovery.save',b'ws1-live.save'),raw.replace(b') S ',b') Z '),raw[:-1]+b'--save\0/tmp/another.save\0\n',raw.replace(b'--save\0',b'')):
    with self.assertRaises(AssertionError):t.identity(types.SimpleNamespace(run=lambda *a:bad),'id')
 def test_shell_suffix_and_specific_pid(self):
  cmd=t.once('op1-probe','op1_replay','--replay /tmp/op1-replay.save')
  self.assertLess(cmd.index('> /tmp/op1_replay.pid'),cmd.index('wait "$p"'));self.assertNotIn(t.LIVE,cmd)
  subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True)
 def test_fixed_limits_and_no_gain_promotion(self):
  m=manifest();scenes=[dict(result=dict(elapsed=3.)) for _ in range(3)];self.assertTrue(t.decision(scenes,m['acceptance'])['accepted'])
  scenes[1]['result']['elapsed']=3.4;self.assertFalse(t.decision(scenes,m['acceptance'])['accepted']);scenes[1]['result']['elapsed']=3
  scenes[2]['result']['elapsed']=2.7;self.assertFalse(t.decision(scenes,m['acceptance'])['accepted'])
 def test_unpublished_pid_refuses_second_gpu(self):
  calls=[];tx=types.SimpleNamespace(run=lambda *a:calls.append(a))
  with patch.object(t,'stop',side_effect=RuntimeError('PID not published')):
   with self.assertRaises(RuntimeError):t.recover(tx,manifest(),('op1-probe','/tmp/op1_replay.pid'),True,{})
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
    if fault=='launch' and label=='restore_am1':raise TimeoutError('reply lost after background launch')
   def progress(*args):
    progress_calls[0]+=1
    if fault=='progress' and progress_calls[0]==1:raise RuntimeError('first progress query failed')
    return dict(presents=30)
   with patch.object(t,'process',lambda *a:True),patch.object(t,'progress',progress):
    with self.assertRaises((RuntimeError,TimeoutError)):t.recover(types.SimpleNamespace(run=run),manifest(),None,True,state)
    self.assertEqual(t.recover(types.SimpleNamespace(run=run),manifest(),None,True,state),dict(presents=30))
   self.assertEqual(sum(label=='restore_am1' for label,cmd in calls),1)
 def test_terminating_baseline_is_not_misreported_as_preserved(self):
  calls=[];count=[10];expected=dict(pid=1604,start_ticks=12329285)
  def run(label,cmd):
   calls.append((label,cmd));count[0]+=1
   return f'DISPLAY presents={count[0]} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
  with patch.object(t,'process',side_effect=[True,False]),patch.object(t,'identity',return_value=expected),patch.object(t.time,'sleep',lambda *a:None),patch.object(t,'progress',return_value=dict(presents=40)):
   result=t.recover(types.SimpleNamespace(run=run),manifest(),None,False,dict(baseline_identity=expected))
  self.assertEqual(result,dict(presents=40));self.assertEqual(sum(label=='restore_am1' for label,cmd in calls),1)
 def test_real_wait_uses_read_only(self):
  class UART:
   def read(self,n):return b'\nL3_EXIT_op1_fixture:0\n'
   def write(self,b):raise AssertionError('write during window')
  with tempfile.TemporaryDirectory() as out:self.assertEqual(t.wait_exit(UART(),Path(out),'op1_fixture'),0)
 def test_flow_failures_abort_then_restore_and_success(self):
  failures=(None,'transfer','install_delta','stop_am1','op1_bench1_launch','op1_bench1_pixels','slow','op1_activity_4_launch','op1_activity_4_overlay_22','replay_timeout','replay_save','resume_launch','live_launch','unpublished')
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
      if label==failure or (failure=='unpublished' and label=='op1_activity_4_launch'):
       if label.endswith('_launch'):alive[0]=m['probe'] if 'activity_' in label else m['program'];raise KeyboardInterrupt(label)
       raise RuntimeError(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\nDISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \nDISPLAY presents=20 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
      if label.startswith('install_'):return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
      if label.startswith('unpack_'):return b'LUMA3D_UNPACK_OK bytes=5292 crc32=11111111\n'
      if label in ('baseline_file','baseline_running_image'):return b'LUMA3D_RAW_OK bytes=100 crc32=22222222\n'
      if label=='restore_am1':alive[0]=t.BASE
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if match:=re.fullmatch(r'op1_bench(\d)_log',label):
       alive[0]=None;return bench(m['benchmarks'][int(match[1])],3.4 if failure=='slow' and match[1]=='1' else 3.)
      if match:=re.fullmatch(r'op1_(garden|house_entry|activity_[0-4])_log',label):
       alive[0]=None;s=next(s for s in m['fixtures'] if s['name']==match[1]);return line('OP1_SCENE',s['host_scene'])+line('OP1_PRESENT',s['host_present'])+line('OP1_RENDER',dict(frames=3,elapsed=1.0))+counters()+b'OP1_PASS\n'
      if label=='replay_log':
       alive[0]=None;return line('OP1_COMPLETE',m['host_replay'])+line('OP1_RENDER',dict(frames=426,elapsed=30.0))+counters(426)+b'OP1_RELOAD active=1\n'*5+b'OP1_PASS\n'
      if label=='replay_codec':return b'OP1_SAVE won=31\n'
      if label=='resume_log':alive[0]=None;return b'LUMA3D_SAVE loaded\nLUMA3D_SAVE saved\n'+counters(1)
      if label in ('baseline_v3_stopped','baseline_v3_final'):return octal(blob(3))
      if label=='replay_save':return octal(blob())
      if label=='resume_save':return octal(blob(active=1))
      if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
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
     if failure=='replay_timeout' and a[2]=='op1_replay':raise TimeoutError('replay')
     return 0
    with contextlib.ExitStack() as s:
     for name,value in [('preflight',lambda *a:m),('identity',lambda *a:dict(pid=1604,start_ticks=12329285)),('Transport',TX),('readback',lambda *a:None),('wait_exit',wait),('process',lambda *a:alive[0]==a[2]),('stop',stop),('stop_baseline',lambda tx,expected:stop(tx,t.BASE,'stop_am1')),('progress',lambda *a:dict(presents=100)),('abort_receiver',lambda *a:calls.append(('abort_receiver',getattr(a[0],'receiver_active',False))))]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**kw:UART()));s.enter_context(patch.object(t,'open',lambda *a,**kw:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['test','--bundle',tmp,'--out',str(root/'result')]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure not in (None,'slow'):
      with self.assertRaises((AssertionError,RuntimeError,KeyboardInterrupt,TimeoutError)):t.main()
     else:t.main()
    result=json.loads((root/'result/result.json').read_text())
    if failure=='unpublished':self.assertIn('cleanup_error',result);self.assertFalse(any(k=='restore_am1' for k,v in calls))
    else:self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure=='transfer':self.assertIn(('abort_receiver',True),calls);self.assertFalse(any(k=='stop_am1' for k,v in calls))
    if failure=='install_delta':self.assertFalse(any(k=='stop_am1' for k,v in calls))
    if failure is None:self.assertTrue(result['passed']);self.assertEqual(len(result['fixtures']),7);self.assertEqual(result['resume_save']['active'],1)
    if failure=='slow':self.assertFalse(result['passed']);self.assertTrue(result['restored_am1']);self.assertFalse(result['fixtures'])

if __name__=='__main__':unittest.main()
