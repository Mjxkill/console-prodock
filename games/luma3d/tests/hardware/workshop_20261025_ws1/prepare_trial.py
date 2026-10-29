#!/usr/bin/env python3
"""Freeze the workshop/save V2 trial without touching the board."""
import argparse,difflib,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PRIOR=REPO/'games/luma3d/tests/hardware/surface_save_20261025_sf2'
BASE=REPO/'games/luma3d/build/terrain_surface_20261025_r2';NEW=REPO/'games/luma3d/build/adventure_workshop_20261025_r8'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta
from prodock_valley_benchmark import fields
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def run(cmd):return subprocess.run(list(map(str,cmd)),check=True,capture_output=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--tag',required=True);a=p.parse_args();assert re.fullmatch(r'ws[0-9]+',a.tag)
 manifests={};expected={'sf2':'ad74b613145bf410c55ac3501962ecea9089f448d84a40e3056bff8671f09d8d','new':'78afc779447e76f221b509f7b3e4c9a2abb347f98ab405f23001c9567a75050c'}
 for key,build in [('sf2',BASE),('new',NEW)]:
  j=json.loads((build/'manifest.json').read_text());assert digest(build/'luma3d-riscv')==j['riscv'] and j['riscv']['sha256']==expected[key]
  for name,r in j['files'].items():
   q=digest(build/'source'/name);assert q['bytes']==r['bytes'] and q['sha256']==r['sha256'],name
  manifests[key]=j
 v=json.loads((NEW/'workshop_validation.json').read_text());assert v['passed'] and not v['hardware'] and v['runtime']==manifests['new']['riscv']
 for r in v['reports'].values():assert digest(REPO/r['path'])['sha256']==r['sha256']
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);prior=json.loads((PRIOR/'manifest.json').read_text())
 for name in ('prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','runtime_inspect.c','prodock-uapi.h','helper-host'):
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,out/name)
 for name in ('prodock_workshop.py','prepare_trial.py','test_trial.py','TRIAL_PLAN.txt'):shutil.copy2(HERE/name,out/name)
 helper=a.tag+'-helper';shutil.copy2(PRIOR/prior['helper'],out/helper);assert digest(out/helper)==prior['files'][prior['helper']]
 for key,b in [('game',NEW),('baseline',BASE)]:shutil.copy2(b/'manifest.json',out/(key+'_manifest.json'))
 shutil.copy2(NEW/'workshop_validation.json',out/'local_validation.json')
 m=dict(initial_guard=dict(pid=1193,start_ticks=7812193),candidate=True,hardware_tested=False,tag=a.tag,program='luma3d-'+a.tag,helper=helper,game=manifests['new']['riscv'],baseline=manifests['sf2']['riscv'],validation=v,transfer_files=[helper],new_references=[],scenes=[],acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05))
 base_ref=next(s for s in prior['scenes'] if s['variant']=='new' and s['pose']==0)
 for ref in (base_ref['pixels'],base_ref['hud']):shutil.copy2(PRIOR/ref['file'],out/ref['file']);run([out/'helper-host','verify',out/ref['file'],'unused',ref['bytes'],ref['crc32']])
 records={};names={0:'arrival',6500:'mechanisms',6780:'reserve'}
 extra=out/'extra_reference';extra.mkdir();prefix=extra/'arrival'
 run([NEW/'luma3d-host','--host','--frames','1','--advance','0','--capture',prefix])
 run([sys.executable,REPO/'games/luma3d/candidates/terrain_surface_r1/render_preview.py',prefix])
 for variant,pose in [('sf2',0),('new',0),('new',6500),('new',6780)]:
  b=BASE if variant=='sf2' else NEW;prefix=extra/'arrival' if variant=='new' and pose==0 else b/'captures'/names[pose];oracle=json.loads(prefix.with_suffix('.reference.json').read_text())
  pixels=prefix.with_suffix('.rgb565').read_bytes();assert len(pixels)==192000 and hashlib.sha256(pixels).hexdigest()==oracle['image_sha256']
  overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();start=20<<20
  end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1);hud=memory[start:end]
  refs={}
  for key,data in [('pixels',pixels),('hud',hud)]:
   if variant=='sf2':
    ref=base_ref[key];assert hashlib.sha256(data).hexdigest()==ref['sha256'];refs[key]=ref
   else:
    file=f'{a.tag}-{key}-{pose}.lz4';(out/file).write_bytes(compress(data));ref=dict(file=file,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}');refs[key]=ref;m['new_references'].append(file)
    run([out/'helper-host','verify',out/file,'unused',len(data),ref['crc32']])
  log=run([b/'luma3d-host','--host','--benchmark','--frames','30','--warmup','3','--advance',pose]);(out/f'host_{variant}_{pose}.log').write_bytes(log.stdout+log.stderr)
  records[variant,pose]=dict(variant=variant,pose=pose,**refs,oracle=oracle,host_benchmark=fields(log.stdout,'LUMA3D_RESULT'))
 m['scenes']=[records[key] for key in [('sf2',0),('new',0),('new',6500),('new',6780),('sf2',0)]]
 patch=delta((BASE/'luma3d-riscv').read_bytes(),(NEW/'luma3d-riscv').read_bytes());assert len(patch)<16<<20;file=a.tag+'.delta.lz4';(out/file).write_bytes(compress(patch))
 m['delta']=dict(file=file,old_sha256=expected['sf2'],new_sha256=expected['new'],new_bytes=m['game']['bytes'],new_crc32=m['game']['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
 m['transfer_files']+=[file,*m['new_references']]
 with tempfile.TemporaryDirectory(prefix='luma-workshop-') as temp:
  rebuilt=Path('/tmp/'+Path(temp).name+'.elf')
  try:
   r=run([out/'helper-host','patch',out/file,rebuilt,len(patch),m['delta']['patch_crc32'],BASE/'luma3d-riscv']);assert digest(rebuilt)==m['game'];(out/'reconstruction.log').write_bytes(r.stdout+r.stderr)
  finally:
   if rebuilt.exists():rebuilt.unlink()
 changed=[];patches=[]
 for name,record in manifests['new']['files'].items():
  if manifests['sf2']['files'].get(name)==record:continue
  changed.append(name)
  if name.endswith(('.c','.h')) and not name.endswith(('data.c','surface_data.h')):
   old=BASE/'source'/name;before=old.read_text().splitlines(True) if old.exists() else [];after=(NEW/'source'/name).read_text().splitlines(True)
   patches.extend(difflib.unified_diff(before,after,fromfile='sf2/'+name,tofile='workshop/'+name))
 (out/'source.patch').write_text(''.join(patches));m['source_changes']=changed
 m['files']={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][p]['bytes'] for p in m['transfer_files'])
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(runtime=m['game'],transport_bytes=m['transport_bytes'],manifest=digest(out/'manifest.json')),indent=2))
if __name__=='__main__':main()
