#!/usr/bin/env python3
"""Freeze art3/terrain-order exact A/B; no board access or active source edits."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,zlib,difflib
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
TOOLS=REPO/'games/luma3d/tools'
sys.path.insert(0,str(TOOLS))
from build_delta import compress,delta
from prodock_valley_benchmark import fields
BASE=REPO/'games/luma3d/build/valley_living_20261024_art3'
PRIOR=REPO/'games/luma3d/tests/hardware/living_20261024_vl2'
NEW=REPO/'games/luma3d/build/living_order_cpu_20261025_r1'
GAME=REPO/'games/luma3d/candidates/valley_living_r1'
BASE_SHA='7fa1062373664d977c26bf6df2a4a5075d64061b967fc3d6d9b831a841302882'
NEW_SHA='b18bbdc7df441ce267b6db6cfbfd346990e2d9a100e70b187a15f3ff3b76c327'
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def run(cmd):return subprocess.run(list(map(str,cmd)),check=True,capture_output=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
 import re
 assert re.fullmatch(r'to[0-9]+',a.tag)
 old_manifest=json.loads((PRIOR/'manifest.json').read_text());assert old_manifest['game']['sha256']==BASE_SHA
 manifests={}
 for key,build,expected in [('art3',BASE,BASE_SHA),('new',NEW,NEW_SHA)]:
  manifest=json.loads((build/'manifest.json').read_text());assert digest(build/'luma3d-riscv')==manifest['riscv'] and manifest['riscv']['sha256']==expected
  for name,info in manifest['files'].items():
   actual=digest(build/'source'/name);assert actual['sha256']==info['sha256'] and actual['bytes']==info['bytes'],name
  validation=json.loads((build/'validation/result.json').read_text());assert validation['passed'] and not validation['hardware'] and validation['runtime']==manifest['riscv']
  manifests[key]=manifest
 assert manifests['art3']['files'].keys()==manifests['new']['files'].keys()
 changed=[n for n in manifests['art3']['files'] if manifests['art3']['files'][n]!=manifests['new']['files'][n]]
 assert changed==['games/luma3d/include/luma3d_render.h','games/luma3d/src/render.c'],changed
 path_validation=json.loads((NEW/'path_art3_composed.json').read_text())
 assert path_validation['exact'] and len(path_validation['records'])==52
 assert path_validation['identities']==dict(base=digest(BASE/'luma3d-host')['sha256'],new=digest(NEW/'luma3d-host')['sha256'])
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 for name in ('prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','runtime_inspect.c','prodock-uapi.h','helper-host'):
  assert digest(PRIOR/name)==old_manifest['files'][name],name
  shutil.copy2(PRIOR/name,out/name)
 for name in ('prodock_order.py','prepare_ab.py','test_ab.py','PLAN.txt'):shutil.copy2(HERE/name,out/name)
 helper=a.tag+'-helper';shutil.copy2(PRIOR/old_manifest['helper'],out/helper)
 assert digest(out/helper)==old_manifest['files'][old_manifest['helper']]
 for key,build in [('game',NEW),('baseline',BASE)]:shutil.copy2(build/'manifest.json',out/(key+'_manifest.json'))
 shutil.copy2(NEW/'validation/result.json',out/'local_validation.json')
 m=dict(candidate=True,hardware_tested=False,program='luma3d-'+a.tag,tag=a.tag,helper=helper,game=manifests['new']['riscv'],baseline=manifests['art3']['riscv'],
  validation=json.loads((NEW/'validation/result.json').read_text()),path_validation=path_validation,source_changes=changed,
  acceptance=dict(median_gain_min=.05,pose_gain_min=-.03,baseline_drift_max=.03),scenes=[],transfer_files=[helper],
  scope='Identical art3 content; six AB/BA pairs, 30 measured +3 warmup; final art3 arrival drift witness. No percentiles. 120s real adventure only if accepted.')
 refs={}
 for s in old_manifest['scenes'][1:]:
  refs[s['pose']]={k:s[k] for k in ('pixels','hud')}
 for ref in [r for pair in refs.values() for r in pair.values()]+[old_manifest['completion_hud']]:
  assert digest(PRIOR/ref['file'])==old_manifest['files'][ref['file']]
  shutil.copy2(PRIOR/ref['file'],out/ref['file'])
  run([out/'helper-host','verify',out/ref['file'],'unused',ref['bytes'],ref['crc32']])
 m['completion_hud']=old_manifest['completion_hud']
 # Generate only absent initial captures, from the already frozen host.
 for build in (BASE,NEW):
  for name,wide in [('arrival',False),('arrival_720',True)]:
   prefix=build/'captures'/name
   if not prefix.with_suffix('.reference.json').exists():
    run([build/'luma3d-host','--host','--frames','1','--capture',prefix]+(['--720p'] if wide else []))
    run([sys.executable,GAME/'render_preview.py',prefix])
 equality=[]
 for newref in sorted((NEW/'captures').glob('*.reference.json')):
  name=newref.name[:-len('.reference.json')];base=BASE/'captures'/name;new=NEW/'captures'/name
  for ext in ('.rgb565','.memory','.overlay.json'):
   assert base.with_suffix(ext).read_bytes()==new.with_suffix(ext).read_bytes(),(name,ext)
  equality.append(dict(scene=name,pixels_sha256=digest(new.with_suffix('.rgb565'))['sha256'],memory_sha256=digest(new.with_suffix('.memory'))['sha256']))
 m['capture_equality']=equality
 names={0:'arrival',90:'maelle',1450:'silo',2330:'relay',3200:'iria',3800:'completion'}
 records={}
 for variant,build in [('art3',BASE),('new',NEW)]:
  for pose,name in names.items():
   prefix=build/'captures'/name;oracle=json.loads(prefix.with_suffix('.reference.json').read_text());ref=refs[pose]
   assert digest(prefix.with_suffix('.rgb565'))=={k:ref['pixels'][k] for k in ('bytes','sha256','crc32')}
   assert oracle['image_sha256']==ref['pixels']['sha256']
   overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());data=prefix.with_suffix('.memory').read_bytes();start=20<<20
   end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1)
   hud=data[start:end];assert len(hud)==ref['hud']['bytes'] and hashlib.sha256(hud).hexdigest()==ref['hud']['sha256']
   log=run([build/'luma3d-host','--host','--benchmark','--frames','30','--warmup','3','--advance',pose])
   (out/f'host_{variant}_{pose}.log').write_bytes(log.stdout+log.stderr)
   records[pose,variant]=dict(variant=variant,pose=pose,**ref,oracle=oracle,host_benchmark=fields(log.stdout,'LUMA3D_RESULT'))
 for i,pose in enumerate(names):m['scenes'].extend(records[pose,v] for v in (('art3','new') if i%2==0 else ('new','art3')))
 m['scenes'].append(records[0,'art3'])
 patch=delta((BASE/'luma3d-riscv').read_bytes(),(NEW/'luma3d-riscv').read_bytes());assert len(patch)<16<<20
 file=a.tag+'.delta.lz4';(out/file).write_bytes(compress(patch));m['transfer_files'].append(file)
 m['delta']=dict(file=file,old_sha256=BASE_SHA,new_sha256=NEW_SHA,new_bytes=m['game']['bytes'],new_crc32=m['game']['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
 with tempfile.TemporaryDirectory(prefix='luma-order-') as tmp:
  rebuilt=Path('/tmp/'+Path(tmp).name+'.elf')
  try:
   r=run([out/'helper-host','patch',out/file,rebuilt,len(patch),m['delta']['patch_crc32'],BASE/'luma3d-riscv']);assert digest(rebuilt)==m['game'];(out/'reconstruction.log').write_bytes(r.stdout+r.stderr)
  finally:
   if rebuilt.exists():rebuilt.unlink()
 patch=''.join(''.join(difflib.unified_diff((BASE/'source'/f).read_text().splitlines(True),(NEW/'source'/f).read_text().splitlines(True),fromfile='art3/'+f,tofile='cpu-order/'+f)) for f in changed)
 (out/'renderer.patch').write_text(patch)
 for index,record in enumerate(path_validation['composition_inputs']):
  original=REPO/record['path'];assert digest(original)['sha256']==record['sha256'];shutil.copy2(original,out/f'path_chain_{index}.json')
 (out/'path_validation.json').write_text(json.dumps(path_validation,indent=2)+'\n')
 m['files']={f.name:digest(f) for f in sorted(out.iterdir()) if f.is_file()};m['transport_bytes']=sum(m['files'][n]['bytes'] for n in m['transfer_files'])
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print(json.dumps(dict(game=m['game'],transport_bytes=m['transport_bytes'],delta_bytes=m['files'][file]['bytes'],manifest=digest(out/'manifest.json')),indent=2))
if __name__=='__main__':main()
