#!/usr/bin/env python3
"""Freeze the Amber/save V3 trial without touching the board."""
import argparse,difflib,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PRIOR=REPO/'games/luma3d/tests/hardware/workshop_20261025_ws1'
BASE=REPO/'games/luma3d/build/adventure_workshop_20261025_r8';NEW=REPO/'games/luma3d/build/adventure_amber_20261025_r9'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta
from prodock_valley_benchmark import fields
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def run(cmd):return subprocess.run(list(map(str,cmd)),check=True,capture_output=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--tag',required=True);a=p.parse_args();assert re.fullmatch(r'am[0-9]+',a.tag)
 manifests={};expected={'ws1':'78afc779447e76f221b509f7b3e4c9a2abb347f98ab405f23001c9567a75050c','new':'62a9178dab260dc5e60be8b9bcea90b35f370357691fb157e5d7fd45a90616ee'}
 for key,build in [('ws1',BASE),('new',NEW)]:
  j=json.loads((build/'manifest.json').read_text());assert digest(build/'luma3d-riscv')==j['riscv'] and j['riscv']['sha256']==expected[key]
  for name,r in j['files'].items():
   q=digest(build/'source'/name);assert q['bytes']==r['bytes'] and q['sha256']==r['sha256'],name
  manifests[key]=j
 v=json.loads((NEW/'local_validation.json').read_text());assert v['passed'] and not v['hardware'] and v['binaries']['riscv']==manifests['new']['riscv']
 for key,r in v['tests'].items():assert digest(NEW/key/'result.json')['sha256']==r['sha256']
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);prior=json.loads((PRIOR/'manifest.json').read_text())
 for name in ('prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','runtime_inspect.c','prodock-uapi.h','helper-host'):
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,out/name)
 for name in ('prodock_amber.py','prepare_trial.py','test_trial.py','TRIAL_PLAN.txt'):shutil.copy2(HERE/name,out/name)
 helper=a.tag+'-helper';shutil.copy2(PRIOR/prior['helper'],out/helper);assert digest(out/helper)==prior['files'][prior['helper']]
 for key,b in [('game',NEW),('baseline',BASE)]:shutil.copy2(b/'manifest.json',out/(key+'_manifest.json'))
 shutil.copy2(NEW/'local_validation.json',out/'local_validation.json')
 m=dict(initial_guard=dict(pid=1331,start_ticks=8373701),candidate=True,hardware_tested=False,tag=a.tag,program='luma3d-'+a.tag,helper=helper,game=manifests['new']['riscv'],baseline=manifests['ws1']['riscv'],validation=v,transfer_files=[helper],new_references=[],scenes=[],acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05))
 base_ref=next(s for s in prior['scenes'] if s['variant']=='new' and s['pose']==0)
 for ref in (base_ref['pixels'],base_ref['hud']):shutil.copy2(PRIOR/ref['file'],out/ref['file']);run([out/'helper-host','verify',out/ref['file'],'unused',ref['bytes'],ref['crc32']])
 records={};names={0:'arrival',10730:'arrival',11990:'routing',12500:'observatory',14720:'valley_return'}
 extra=out/'extra_reference';extra.mkdir()
 for pose in (0,14720):
  prefix=extra/names[pose];run([NEW/'luma3d-host','--host','--frames','1','--advance',pose,'--capture',prefix]);run([sys.executable,REPO/'games/luma3d/candidates/terrain_surface_r1/render_preview.py',prefix])
 for variant,pose in [('ws1',0),('new',0),('new',10730),('new',11990),('new',12500),('new',14720)]:
  b=BASE if variant=='ws1' else NEW;prefix=PRIOR/'extra_reference/arrival' if variant=='ws1' else extra/names[pose] if pose in (0,14720) else b/'captures_final'/names[pose];oracle=json.loads(prefix.with_suffix('.reference.json').read_text())
  pixels=prefix.with_suffix('.rgb565').read_bytes();assert len(pixels)==192000 and hashlib.sha256(pixels).hexdigest()==oracle['image_sha256']
  overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();start=20<<20
  end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1);hud=memory[start:end]
  refs={}
  for key,data in [('pixels',pixels),('hud',hud)]:
   if variant=='ws1':
    ref=base_ref[key];assert hashlib.sha256(data).hexdigest()==ref['sha256'];refs[key]=ref
   else:
    file=f'{a.tag}-{key}-{pose}.lz4';(out/file).write_bytes(compress(data));ref=dict(file=file,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}');refs[key]=ref;m['new_references'].append(file)
    run([out/'helper-host','verify',out/file,'unused',len(data),ref['crc32']])
  log=run([b/'luma3d-host','--host','--benchmark','--frames','30','--warmup','3','--advance',pose]);(out/f'host_{variant}_{pose}.log').write_bytes(log.stdout+log.stderr)
  records[variant,pose]=dict(variant=variant,pose=pose,**refs,oracle=oracle,host_benchmark=fields(log.stdout,'LUMA3D_RESULT'))
 m['scenes']=[records[key] for key in [('ws1',0),('new',0),('new',10730),('new',11990),('new',12500),('new',14720),('ws1',0)]]
 patch=delta((BASE/'luma3d-riscv').read_bytes(),(NEW/'luma3d-riscv').read_bytes());assert len(patch)<16<<20;file=a.tag+'.delta.lz4';(out/file).write_bytes(compress(patch))
 m['delta']=dict(file=file,old_sha256=expected['ws1'],new_sha256=expected['new'],new_bytes=m['game']['bytes'],new_crc32=m['game']['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
 m['transfer_files']+=[file,*m['new_references']]
 with tempfile.TemporaryDirectory(prefix='luma-amber-') as temp:
  rebuilt=Path('/tmp/'+Path(temp).name+'.elf')
  try:
   r=run([out/'helper-host','patch',out/file,rebuilt,len(patch),m['delta']['patch_crc32'],BASE/'luma3d-riscv']);assert digest(rebuilt)==m['game'];(out/'reconstruction.log').write_bytes(r.stdout+r.stderr)
  finally:
   if rebuilt.exists():rebuilt.unlink()
 changed=[];patches=[]
 for name,record in manifests['new']['files'].items():
  if manifests['ws1']['files'].get(name)==record:continue
  changed.append(name)
  if name.endswith(('.c','.h')) and not name.endswith(('data.c','surface_data.h')):
   old=BASE/'source'/name;before=old.read_text().splitlines(True) if old.exists() else [];after=(NEW/'source'/name).read_text().splitlines(True)
   patches.extend(difflib.unified_diff(before,after,fromfile='ws1/'+name,tofile='amber/'+name))
 (out/'source.patch').write_text(''.join(patches));m['source_changes']=changed
 m['files']={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][p]['bytes'] for p in m['transfer_files'])
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(runtime=m['game'],transport_bytes=m['transport_bytes'],manifest=digest(out/'manifest.json')),indent=2))
if __name__=='__main__':main()
