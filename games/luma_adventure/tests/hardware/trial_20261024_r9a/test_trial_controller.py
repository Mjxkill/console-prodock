#!/usr/bin/env python3
"""Controller success/failure test with fake UART and shell; no board access."""
import argparse,contextlib,hashlib,importlib.util,io,json,re,struct,sys,tempfile,types,zlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);args=p.parse_args();bundle=args.bundle.resolve()
state={};gpu=b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 done=0 errors=0 uf=0 frames=1 fault=0\n';display=b'DISPLAY errors=0 uf=0 invalid=0 sprites=0 fault=0\n'
class UART:
 def __init__(self,*args,**kwargs):state['opened']+=1;self.rx=bytearray();self.line=bytearray();self.packet=bytearray();self.receiving=False;self.waiting=False;self.files={};state['uart']=self
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def flush(self):pass
 def reset_input_buffer(self):self.rx.clear()
 def read(self,n):
  data=bytes(self.rx[:n]);del self.rx[:n]
  if b'__LUMA_COMPLETE_' in data:self.waiting=False
  return data
 def write(self,data):
  assert not self.waiting,'controller wrote UART before reading the exit marker'
  if self.receiving:
   self.packet.extend(data)
   if len(self.packet)<16:return len(data)
   magic,seq,n,crc=struct.unpack('<4sIII',self.packet[:16]);assert magic==b'LMA1'
   if len(self.packet)<16+n:return len(data)
   body=bytes(self.packet[16:16+n]);assert len(self.packet)==16+n;self.packet.clear()
   if n:assert zlib.crc32(body)==crc;self.files[self.target].extend(body);self.rx.extend(b'A'+struct.pack('<I',seq))
   else:assert zlib.crc32(self.files[self.target])==crc;self.rx.extend(b'D'+struct.pack('<I',len(self.files[self.target])));self.receiving=False
  else:
   self.line.extend(data)
   if self.line.endswith(b'\n'):
    line=self.line.decode();self.line.clear()
    if line.startswith('/tmp/luma-rx '):self.target=line.split()[1];self.files[self.target]=bytearray();self.receiving=True;self.rx.extend(b'R\0\0\0\0')
    elif '__LUMA_COMPLETE_' in line:
     name=re.search(r'__LUMA_COMPLETE_(\w+)__',line)[1];state['last']=name;self.waiting=True
     code=1 if state['fail_final'] and name=='final_inputs' else 0
     self.rx.extend(f'\n__LUMA_COMPLETE_{name}__:{code}\n'.encode())
  return len(data)
def command(uart,cmd,timeout):
 assert not uart.waiting,'shell command issued during a measurement'
 state['commands'].append(cmd)
 if cmd.startswith('uname '):return 0,b'Linux prodock 6.12.112-prodock\n'+gpu+display+b'rootfs / rootfs rw 0 0\n101\n'
 if cmd.startswith('od '):
  blob=(bundle/'uart-receiver').read_bytes();return 0,b'\n'.join((f'{i:07o} '+' '.join(f'{c:03o}' for c in blob[i:i+16])).encode() for i in range(0,len(blob),16))+b'\n'
 if 'kill -TERM' in cmd:state['nebula']=False;return 0,b''
 if cmd.startswith('nebula --demo') or 'if test "`cat /proc/$p/comm`" != nebula' in cmd:state['nebula']=True;state['restores']+=1;return 0,b''
 if cmd=='cat /tmp/luma-trial.log':
  name=state['last'];spec=next((s for s in state['manifest']['scenarios'] if s['name']==name),None)
  if spec:
   return 0,(f'LUMA_WARMUP frames=120 seconds=2.2\nLUMA_RATE frames=600 seconds=12.0 fps=50.0 updates=720 commands=0 max_sprites=32\nLUMA_FRAME_TIME samples=600 p95_ms_upper=30.0 p99_ms_upper=40.0 max_ms=45.0 over_33_333_ms=12\nLUMA_RESULT world={spec["world"]} flags=0 status=0\n').encode()
  case='final' if name=='final_inputs' else 'first';start,end,gallery=(35,2,2) if case=='final' else (26,27,0)
  return 0,(f'LUMA_PROBE_FIXTURE case={case} direct_start={start} outer_prerequisites_seeded={int(case=="final")} saving_disabled=1 render_every_four_steps_and_interactions=1\nLUMA_PROBE_PASS case={case} start_world={start} end_world={end} steps=100 rendered_frames=30 rotations=1 beam_changes=2 max_beams=3 beam_frames=28 gallery={gallery} loading_scenes=1 status=0\n').encode()
 if 'prodockctl display' in cmd:return 0,gpu+display
 return 0,b''
sys.modules['serial']=types.SimpleNamespace(Serial=UART);sys.modules['check_linux']=types.SimpleNamespace(command=command)
spec=importlib.util.spec_from_file_location('trial',root/'tools/prodock_scene_trial.py');trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial);trial.time.sleep=lambda _:None
print('Controller SHA256',hashlib.sha256((root/'tools/prodock_scene_trial.py').read_bytes()).hexdigest())
with tempfile.TemporaryDirectory(prefix='trial-controller-',dir=root/'build') as tmp:
 tmp=Path(tmp);test_bundle=tmp/'bundle';test_bundle.mkdir();manifest=json.loads((bundle/'manifest.json').read_text())
 for name in manifest['runtime']:
  source=root/'tools/prodock_scene_trial.py' if name=='prodock_scene_trial.py' else bundle/name
  (test_bundle/name).symlink_to(source)
 script=(root/'tools/prodock_scene_trial.py').read_bytes();manifest['runtime']['prodock_scene_trial.py']={'bytes':len(script),'sha256':hashlib.sha256(script).hexdigest()};(test_bundle/'manifest.json').write_text(json.dumps(manifest))
 for fail in [False,True]:
  state.clear();state.update(opened=0,commands=[],nebula=True,restores=0,fail_final=fail,manifest=manifest)
  output=tmp/('failure' if fail else 'success');sys.argv=['trial','--root',str(root.parents[1]),'--bundle',str(test_bundle),'--out',str(output),'--reuse-bootstrap']
  rejected=False
  with contextlib.redirect_stdout(io.StringIO()):
   try:trial.main()
   except AssertionError:rejected=True
  report=json.loads((output/'result.json').read_text());assert rejected==fail and report['passed']==(not fail)
  assert state['nebula'] and state['restores']==1 and not any(report['restored_display'].values())
  assert len(report['transfers'])==8
  if fail:assert any('luma-probe' in c and 'kill -TERM' in c for c in state['commands'])
  print('PASS fake UART', 'injected final-probe failure restored NEBULA' if fail else 'success, payload CRCs, quiet waits and restoration')
 state['opened']=0;manifest['runtime']['luma-riscv']['sha256']='invalid';(test_bundle/'manifest.json').write_text(json.dumps(manifest));sys.argv=['trial','--bundle',str(test_bundle),'--out',str(tmp/'wrong_identity')]
 try:trial.main()
 except AssertionError:pass
 else:raise AssertionError('wrong identity accepted')
 assert state['opened']==0;print('PASS wrong candidate rejected before UART access\nLUMA_TRIAL_CONTROLLER_PASS no hardware accessed')
