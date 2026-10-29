#!/usr/bin/env python3
"""Local controller fault injection. Never opens serial, USB or GPU devices."""
import contextlib,hashlib,io,json,struct,sys,tempfile,types,unittest,zlib
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=next(p for p in HERE.parents if (p/'games/luma3d/tools').is_dir())
sys.path[:0]=[str(HERE),str(REPO/'games/luma3d/tests/hardware/terrain_cpu_20261025_to4')]
import prodock_surface as t
def save():
 w=[4,4,3,1,0,0,0,10,0,1]+list(struct.unpack('<8I',struct.pack('<8f',100,20,40,1,1,.3,100,300)))+[0,0]
 payload=struct.pack('<20I',*w)+b''.join(struct.pack('<2I',0x4c455431+i,1) for i in range(4))
 return b'L3PROG1\0'+struct.pack('<4I',136,0x56414c31,1,zlib.crc32(payload))+payload
def octal(data):
 return b'\n'.join((f'{i:07o} '+' '.join(f'{x:03o}' for x in data[i:i+16])).encode() for i in range(0,len(data),16))
def benchmark(s):
 return (f'LUMA3D_BENCHMARK pose={s["pose"]} warmup=3 measured_frames=30 fixed_pose=1 hardware=1\n'
 'LUMA3D_RESULT frames=30 elapsed=3.0 fps=10 commands=60 batches=30 draws_last=1 triangles_last=2 benchmark=1 hardware=1 warmup=3\n'
 'LUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=99 triangles=66 slivers=0 frames=33\n'
 'LUMA3D_BENCHMARK_COUNTERS cycles=10 vertices=90 raster_triangles=60 culled=0 intersections=0 slivers=0 feed_us=1 wait_us=1 cache_us=1 present_us=1\n').encode()
class Tests(unittest.TestCase):
 def test_saved_bytes_are_crc_checked_and_semantically_complete(self):
  blob=save();tx=types.SimpleNamespace(run=lambda *a:octal(blob));r=t.saved_bytes(tx,'test','/tmp/test.save');self.assertEqual(r['bytes'],136)
  for at in (8,12,16,20,24,28,104,135):
   bad=bytearray(blob);bad[at]^=1
   with self.assertRaises(AssertionError):t.saved_bytes(types.SimpleNamespace(run=lambda *a:octal(bad)),'test','/tmp/test.save')
 def test_fixed_plan_rejects_slowdown_or_drift(self):
  scenes=[dict(result=dict(elapsed=3.0)) for i in range(5)];limits=dict(max_arrival_slowdown=.10,max_witness_drift=.05)
  self.assertTrue(t.decision(scenes,limits)['accepted']);scenes[1]['result']['elapsed']=3.4;self.assertFalse(t.decision(scenes,limits)['accepted'])
  scenes[1]['result']['elapsed']=3;scenes[-1]['result']['elapsed']=2.7;self.assertFalse(t.decision(scenes,limits)['accepted'])
 def test_supervisor_publishes_pid_before_wait_and_shell_suffix(self):
  cmd=t.once('luma3d-sf1','sf1_resume','--manual --frames 1 --save /tmp/sf1.save')
  self.assertLess(cmd.index('> /tmp/sf1_resume.pid'),cmd.index('wait "$p"'));self.assertIn('SURFACE_LAUNCHED',cmd)
  import subprocess
  subprocess.run(['sh','-n','-c',cmd+'; printf DONE'],check=True)
 def test_flow_failure_paths_and_success(self):
  for failure in (None,'install','sf1_1_launch','sf1_1_pixels','dead_endurance','save_before_resume','resume_launch','slow','restore_progress'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp);(out/'manifest.json').write_text('{}');clock=[0];alive=[t.BASE];calls=[]
    ref=dict(file='ref.lz4',bytes=192000,crc32='11111111')
    scenes=[dict(variant=v,pose=p,pixels=ref,hud=ref,oracle=dict(vertices=3,triangles=2,slivers=0),host_benchmark=dict(commands=60,batches=30,draws_last=1,triangles_last=2)) for v,p in [('art3',0),('new',0),('new',1450),('new',3800),('art3',0)]]
    m=dict(tag='sf1',program='luma3d-sf1',helper='sf1-helper',game=dict(bytes=100,crc32='22222222'),transfer_files=[],delta=dict(file='delta',patch_bytes=10,patch_crc32='33333333'),scenes=scenes,acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05))
    status=b'DISPLAY presents=10 errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
    class UART:
     def __enter__(self):return self
     def __exit__(self,*a):return False
     def write(self,b):calls.append(('write',b))
     def read(self,n):return b''
     def flush(self):pass
    class TX:
     def __init__(self,*a):self.receiver_active=False
     def run(self,label,cmd,*a):
      calls.append((label,cmd))
      if label==failure:
       if label.endswith('_launch'):alive[0]=m['program'];raise KeyboardInterrupt(label)
       raise RuntimeError(label)
      if label=='before':return t.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\n'+status
      if label=='released':return b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 \n'+status
      if label=='install':return b'LUMA3D_UNPACK_OK bytes=100 crc32=22222222\n'
      if label.startswith('verify_'):return b'LUMA3D_VERIFY_OK bytes=192000 crc32=11111111\n'
      if label.endswith('_launch'):alive[0]=m['program'];return b''
      if re_scene:=__import__('re').fullmatch(r'sf1_(\d+)_log',label):
       alive[0]=None;data=benchmark(scenes[int(re_scene[1])]);return data.replace(b'elapsed=3.0',b'elapsed=3.4') if failure in ('slow','restore_progress') and re_scene[1]=='1' else data
      if label=='endurance_log':return b'LUMA3D_RESULT frames=1000 elapsed=130.0 fps=8\nLUMA3D_STORY phase=4 relay=3 discovered=1 collected=4 complete=1 sim=100.0 auto=1\nLUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=1 triangles=1 slivers=0 frames=1000\n'
      if label=='resume_log':return b'LUMA3D_STORY phase=4 relay=3 discovered=1 collected=4 complete=1 sim=100.0 auto=0\nLUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0 vertices=1 triangles=1 slivers=0 frames=1\n'
      if label in ('save_before_resume','save_after_resume'):return octal(save())
      if label.endswith('_pixels'):return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'
      if '_hud_' in label:return f'LUMA3D_HUD bank={label[-2:]} bytes=192000 mismatch=0 actual_crc=11111111 expected_crc=11111111\n'.encode()
      if 'prodockctl display' in cmd:return status
      return b''
    def stop(tx,name,label,pidfile=t.LIVE):calls.append((label,name));alive[0]=None
    def launch(tx,name,log,label,pidfile=t.LIVE):calls.append((label,name));alive[0]=name
    def progress(tx,name,log,label,pidfile=t.LIVE):
     if failure=='restore_progress' and label=='restored_art3':raise RuntimeError(label)
     return dict(presents=10)
    def recover(tx,m,current,ever):
     if current:stop(tx,current[0],'cleanup_current',current[1])
     calls.append(('recovered',t.BASE));alive[0]=t.BASE;return dict(presents=11)
    def mono():clock[0]+=10;return clock[0]
    with contextlib.ExitStack() as s:
     for name,value in [('preflight',lambda *a:m),('identity',lambda *a:dict(pid=1058,start_ticks=7384377)),('Transport',TX),('readback',lambda *a:None),('wait_exit',lambda *a,**k:0),('process',lambda tx,label,name,pidfile:False if failure=='dead_endurance' else alive[0]==name),('stop',stop),('launch',launch),('progress',progress),('recover',recover),('abort_receiver',lambda *a:None)]:s.enter_context(patch.object(t,name,value))
     s.enter_context(patch.object(t.serial,'Serial',lambda *a,**k:UART()));s.enter_context(patch.object(t,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True));s.enter_context(patch.object(t.fcntl,'flock',lambda *a:None));s.enter_context(patch.object(t.signal,'signal',lambda *a:None));s.enter_context(patch.object(t.time,'sleep',lambda *a:None));s.enter_context(patch.object(t.time,'monotonic',mono));s.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}));s.enter_context(patch.object(sys,'argv',['trial','--bundle',tmp,'--out',str(out/'result')]));s.enter_context(contextlib.redirect_stdout(io.StringIO()))
     if failure not in (None,'slow'):
      with self.assertRaises((RuntimeError,AssertionError,KeyboardInterrupt)):t.main()
     else:t.main()
    result=json.loads((out/'result/result.json').read_text())
    self.assertEqual(alive[0],m['program'] if failure is None else t.BASE)
    if failure=='install':self.assertFalse(any(k=='stop_art3' for k,v in calls))
    if failure=='restore_progress':self.assertIn(('cleanup_current',t.BASE),calls)
    if failure is None:self.assertTrue(result['passed']);self.assertIn('save_after_resume',result)
if __name__=='__main__':unittest.main()
