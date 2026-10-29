#!/usr/bin/env python3
"""Last-frame oracle: published color and every active UI source, no holes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from probe_metrics import parse
C=Path(__file__).resolve().parent;R=C.parents[3];PREVIEW=C.parent/'maze_events_r1/preview.py'
# kind, frames, restart frame, BACK frame; world only first frame so sky COPY
# never depends on GPU-written scratch omitted from the CPU memory dump.
CASES=[(8,1,0,0),(4,1,0,0),(4,31,0,0),(4,31,16,0),(4,32,16,31),(7,1,0,0),(7,31,0,0),(7,32,16,31)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();q=a.probe.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
m=json.loads((q/'manifest.json').read_text());elf=q/'candidate-host';assert sha(elf)==next(r['elf_sha256'] for r in m['records'] if r['variant']=='candidate' and r['target']=='host');records=[]
for width in (800,1280):
 for kind,frames,restart,back in CASES:
  name=f'fixture_{kind}_{width}_{frames}_r{restart}_b{back}';f=o/name
  cmd=[elf,'--host','--kind',str(kind),'--fixture','--frames',str(frames),'--capture',f]+(['--720p'] if width==1280 else [])+(['--restart-at',str(restart)] if restart else [])+(['--back-at',str(back)] if back else [])
  r=subprocess.run(cmd,capture_output=True,timeout=120);f.with_suffix('.log').write_bytes(r.stdout+r.stderr);r.check_returncode();value=parse(r.stdout,kind,frames,True,False,restart,back)
  r=subprocess.run(['python3',PREVIEW,f],capture_output=True,timeout=120);f.with_suffix('.oracle.log').write_bytes(r.stdout+r.stderr);r.check_returncode()
  info=json.loads(f.with_suffix('.reference.json').read_text());overlay=json.loads(f.with_suffix('.overlay.json').read_text());memory=f.with_suffix('.memory').read_bytes();ui=[]
  for i,layer in enumerate(overlay['layers']):
   if not layer[6]&1:continue
   offset=layer[0]-0x800000;assert 20<<20<=offset<24<<20
   uw,uh=layer[1]&65535,layer[1]>>16;assert layer[6]==3 and uw==width and layer[5]==width
   data=memory[offset:offset+uw*uh];assert len(data)==uw*uh
   ext=f'.ui{i}';f.with_suffix(ext).write_bytes(data)
   ui.append(dict(extension=ext,offset=offset,bytes=len(data),sha256=sha(f.with_suffix(ext))))
  assert 1<=len(ui)<=2
  w,h=width//2,240 if width==800 else 360;assert info['width']==w and info['height']==h and info['scale']==2
  data=f.with_suffix('.rgb565').read_bytes();assert len(data)==w*h*2
  f.with_suffix('.rect').write_bytes(data)
  rect=dict(width=w,height=h,pitch=info['pitch'],offset=info['page']*info['page_bytes'],bytes=len(data),sha256=sha(f.with_suffix('.rect')))
  records.append(dict(name=name,kind=kind,width=width,frames=frames,restart_at=restart,back_at=back,measurement=value,oracle=info,rect=rect,ui=ui));print(name,flush=True)
(o/'result.json').write_text(json.dumps(dict(passed=True,hardware=False,probe_manifest_sha256=sha(q/'manifest.json'),elf_sha256=sha(elf),preview_sha256=sha(PREVIEW),runner_sha256=sha(Path(__file__)),records=records,scope='Actual last-frame GPU commands and all active indexed UI sources. No margins, no composed-LCD claim.'),indent=2)+'\n')
