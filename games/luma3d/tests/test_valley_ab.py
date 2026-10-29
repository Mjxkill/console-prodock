#!/usr/bin/env python3
"""R2 failure injection: leave R1 intact, or restore it after the handoff."""
import contextlib,hashlib,io,json,shutil,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parents[1];sys.path.insert(0,str(ROOT/'tools'))
import prodock_valley_ab as trial
RECEIVER=(ROOT.parent/'luma_adventure/tests/hardware/trial_20261024_r9b/uart-receiver').read_bytes()
def counters(n):return f'DISPLAY presents={n} errors=0 uf=0 invalid=0 sprites=0 fault=0\n'.encode()
class Tests(unittest.TestCase):
 def test_stop_waits_for_the_specific_launch_pid(self):
  calls=[];attempt=[0]
  def run(label,command):
   calls.append(command);self.assertIn('/tmp/new-launch.pid',command)
   if '_before_' in label:
    attempt[0]+=1
    return b'UNPUBLISHED\n' if attempt[0]<3 else b'luma3d-r2\nState:\tR (running)\n'
   return b'STOPPED\n'
  with patch.object(trial.time,'sleep',lambda *a:None):trial.stop(types.SimpleNamespace(run=run),'luma3d-r2','test','/tmp/new-launch.pid')
  self.assertEqual(attempt[0],3);self.assertEqual(sum('kill -TERM' in c for c in calls),1)
  with patch.object(trial.time,'sleep',lambda *a:None),self.assertRaises(trial.UnpublishedPID):
   trial.stop(types.SimpleNamespace(run=lambda *a:b'UNPUBLISHED\n'),'luma3d-r2','test','/tmp/new-launch.pid')
 def test_failure_preserves_or_restores_r1(self):
  for failing in ('patch','pixels','endurance_launch'):
   with self.subTest(failing=failing),tempfile.TemporaryDirectory() as folder:
    root=Path(folder);bundle=root/'bundle';bundle.mkdir();script=Path(trial.__file__);shutil.copy2(script,bundle/script.name)
    (root/'tools').mkdir()
    for name in ('check_linux.py','check_gpu_reloads.py'):(root/'tools'/name).write_text('# fixture\n')
    m={'game':{'sha256':trial.NEW_SHA},'delta':{'old_sha256':trial.OLD_SHA,'new_sha256':trial.NEW_SHA,'patch_bytes':100,'patch_crc32':'11111111','new_bytes':200,'new_crc32':'22222222'},
       'reference':{'sha256':'e9449de1c075c23fa37e090c8edf1ce3eb728ea109d7f7b069e6b7fba9988fb4'},
       'files':{script.name:{'bytes':script.stat().st_size,'sha256':trial.sha(script)}}}
    m['shared_tools']={name:trial.sha(root/'tools'/name) for name in ('check_linux.py','check_gpu_reloads.py')}
    (bundle/'manifest.json').write_text(json.dumps(m));active=['luma3d-r1'];calls=[];count=[0]
    class UART:
     def __enter__(self):return self
     def __exit__(self,*args):return False
     def write(self,data):pass
     def flush(self):pass
     def read(self,n):return b''
    class TX:
     def __init__(self,*args):pass
     def transfer(self,path,name):calls.append(('transfer',name));return {'name':name}
     def run(self,label,command,*args):
      calls.append((label,command))
      if label==failing:
       if label=='endurance_launch':active[0]='luma3d-r2';raise KeyboardInterrupt('injected after R2 launch')
       raise RuntimeError('injected '+label)
      if label=='before':return trial.RELEASE+b'\ntmpfs /tmp tmpfs rw 0 0\n'+counters(1)
      if label=='receiver_readback':return b'\n'.join(('%07o '%i+' '.join('%03o'%x for x in RECEIVER[i:i+16])).encode() for i in range(0,len(RECEIVER),16))+b'\n'
      if label=='retained_reference':return b'LUMA3D_VERIFY_OK bytes=192000 crc32=b43a5e60\n'
      if label=='patch':return b'LUMA3D_UNPACK_OK bytes=200 crc32=22222222\n'
      if label.endswith('_term'):active[0]=None;return b''
      if label=='first_launch':active[0]='luma3d-r2';return b''
      if label=='first_status':active[0]=None;return b'0\n'
      if label=='first_frame':return b'LUMA3D_RESULT frames=1 elapsed=1\nLUMA3D_COUNTERS errors=0 underflows=0 fault=0 geometry_errors=0\n'
      if label=='pixels':return b'LUMA3D_PIXELS pixels=96000 mismatch=0 actual_crc=b43a5e60 expected_crc=b43a5e60\n'
      if label=='restore_r1':active[0]='luma3d-r1';return b''
      if 'prodockctl display' in command:count[0]+=10;return counters(count[0])
      if 'cat /proc/$p/status' in command:return (active[0].encode()+b'\nState:\tR (running)\n') if active[0] else b'STOPPED\n'
      if command.startswith('cat /tmp/luma3d-'):return b'LUMA3D_PERF fps=4.5\n'
      return b''
    argv=['ab','--root',str(root),'--bundle',str(bundle),'--out',str(root/'result')]
    with contextlib.ExitStack() as stack:
     stack.enter_context(patch.object(sys,'argv',argv));stack.enter_context(patch.object(trial,'Transport',TX))
     stack.enter_context(patch.object(trial.serial,'Serial',lambda *a,**k:UART()))
     stack.enter_context(patch.object(trial,'open',lambda *a,**k:tempfile.TemporaryFile(),create=True))
     stack.enter_context(patch.object(trial.fcntl,'flock',lambda *a:None))
     stack.enter_context(patch.object(trial.signal,'signal',lambda *a:None))
     stack.enter_context(patch.object(trial.time,'sleep',lambda *a:None))
     stack.enter_context(patch.dict(sys.modules,{'check_linux':types.SimpleNamespace(command=None)}))
     stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
     with self.assertRaises(KeyboardInterrupt if failing=='endurance_launch' else RuntimeError):trial.main()
    result=json.loads((root/'result/result.json').read_text());self.assertFalse(result['passed']);self.assertEqual(active[0],'luma3d-r1')
    self.assertNotIn('cleanup_error',result)
    if failing=='patch':self.assertFalse(any(k in ('stop_r1_term','restore_r1') for k,_ in calls))
    else:self.assertTrue(result['restored_r1']);self.assertTrue(any(k=='restore_r1' for k,_ in calls))
if __name__=='__main__':unittest.main()
