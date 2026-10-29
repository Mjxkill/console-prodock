#!/usr/bin/env python3
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
from probe_metrics import parse
C=Path(__file__).resolve().parent;R=C.parents[3];PREVIEW=C.parent/'maze_events_r1/preview.py'
CASES=[(1,1),(3,1),(4,1),(5,1),(6,1),(1,4),(3,4),(5,4)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();q=a.probe.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
m=json.loads((q/'manifest.json').read_text());elf=q/'candidate-host';assert sha(elf)==next(r['elf_sha256'] for r in m['records'] if r['variant']=='candidate' and r['target']=='host');records=[]
for width in (800,1280):
 for kind,frames in CASES:
  name=f'fixture_{kind}_{width}_{frames}';f=o/name
  cmd=[elf,'--host','--kind',str(kind),'--fixture','--frames',str(frames),'--capture',f]+(['--720p'] if width==1280 else [])
  r=subprocess.run(cmd,capture_output=True,timeout=120);f.with_suffix('.log').write_bytes(r.stdout+r.stderr);r.check_returncode();value=parse(r.stdout,kind,frames,True,False)
  r=subprocess.run(['python3',PREVIEW,f],capture_output=True,timeout=120);f.with_suffix('.oracle.log').write_bytes(r.stdout+r.stderr);r.check_returncode()
  info=json.loads(f.with_suffix('.reference.json').read_text());overlay=json.loads(f.with_suffix('.overlay.json').read_text());memory=f.with_suffix('.memory').read_bytes()
  layers=[layer for layer in overlay['layers'] if layer[6]&1 and 22<<20<=layer[0]-0x800000<24<<20]
  assert len(layers)==1;layer=layers[0];uw,uh=layer[1]&65535,layer[1]>>16;assert layer[6]==3 and uw==width and layer[5]==width
  ui_offset=layer[0]-0x800000;ui=memory[ui_offset:ui_offset+uw*uh];assert len(ui)==uw*uh
  f.with_suffix('.ui').write_bytes(ui);roi=None
  if kind in (1,3):
   aui=np.frombuffer(ui,dtype=np.uint8).reshape(uh,uw);ys,xs=np.where(aui==0);assert len(xs)
   x,y=int(xs.min()),int(ys.min());w,h=int(xs.max())-x+1,int(ys.max())-y+1
   assert len(xs)==w*h and not aui[y:y+h,x:x+w].any();assert x%16==0 and w<=1024 and h<=512
  elif kind==5:x=y=0;w,h=width,480 if width==800 else 720
  elif kind==4:x=y=0;w,h=width//2,240 if width==800 else 360
  if kind!=6:
   data=f.with_suffix('.rgb565').read_bytes();stride=info['width']*2
   rect=b''.join(data[(y+j)*stride+x*2:(y+j)*stride+(x+w)*2] for j in range(h));assert len(rect)==w*h*2
   f.with_suffix('.rect').write_bytes(rect);roi=dict(x=x,y=y,width=w,height=h,pitch=info['pitch'],offset=info['page']*info['page_bytes']+y*info['pitch']+x*2,bytes=len(rect),sha256=sha(f.with_suffix('.rect')))
  records.append(dict(name=name,kind=kind,width=width,frames=frames,measurement=value,oracle=info,rect=roi,ui=dict(offset=ui_offset,bytes=len(ui),sha256=sha(f.with_suffix('.ui')))));print(name,flush=True)
(o/'result.json').write_text(json.dumps(dict(passed=True,hardware=False,probe_manifest_sha256=sha(q/'manifest.json'),elf_sha256=sha(elf),preview_sha256=sha(PREVIEW),runner_sha256=sha(Path(__file__)),records=records,scope='Actual emitted GPU commands and native indexed UI; rectangle excludes unpublished margins. No hardware/compositeLCD claim.'),indent=2)+'\n')
