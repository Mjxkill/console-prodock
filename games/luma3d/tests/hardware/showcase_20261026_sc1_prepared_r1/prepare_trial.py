#!/usr/bin/env python3
"""Freeze one showcase trial from locally verified files. No board access."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
PRIOR=R/'games/luma3d/tests/hardware/arcade_20261026_ar1_prepared_r2'
BASE=R/'games/luma3d/build/amber_paths_20261026_r5'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta

def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--tag',required=True);a=p.parse_args();assert re.fullmatch(r'sc[0-9]+',a.tag)
 b=a.build.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 manifests={}
 for k,d in [('game',b),('baseline',BASE)]:
  m=json.loads((d/'manifest.json').read_text());assert digest(d/'luma3d-riscv')==m['riscv']
  for n,v in m['files'].items():assert digest(d/'source'/n)['sha256']==v['sha256']
  manifests[k]=m;shutil.copy2(d/'manifest.json',o/(k+'_manifest.json'))
 assert manifests['baseline']['riscv']['sha256']=='8f7500184ccf9977502243e5ddfbfb3b27f4b5b224dde46c606d8bdcf8f18981'
 for name in ['local_validation.json','rv32_validation.json']:
  v=json.loads((b/name).read_text());assert v['passed'] and v['manifest_sha256']==digest(b/'manifest.json')['sha256'];shutil.copy2(b/name,o/name)
 common=json.loads((b/'common_regression_status.json').read_text());assert common['passed'] and common['tests']==11 and not common['changed'];shutil.copy2(b/'common_regression_status.json',o/'common_regression_status.json')
 prior=json.loads((PRIOR/'manifest.json').read_text());assert digest(PRIOR/'manifest.json')['sha256']=='b71c7289558d7de5263829b40f18a329de3e9ad67e28809c082d00a41fbb477c'
 for name in ['prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','helper-host','runtime_inspect.c','prodock-uapi.h']:
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,o/name)
 assert digest(PRIOR/'ar1-helper')==prior['files']['ar1-helper'];shutil.copy2(PRIOR/'ar1-helper',o/(a.tag+'-helper'))
 for name in ['prodock_showcase.py','prepare_trial.py','test_trial.py','TRIAL_PLAN.txt','README.md']:shutil.copy2(C/name,o/name)
 m=dict(candidate=True,hardware_tested=False,tag=a.tag,program='luma3d-'+a.tag,helper=a.tag+'-helper',game=manifests['game']['riscv'],baseline=manifests['baseline']['riscv'],deadline_seconds=3700,tour_args='--showcase-once',live_args='--showcase')
 old=(BASE/'luma3d-riscv').read_bytes();new=(b/'luma3d-riscv').read_bytes();patch=delta(old,new);assert len(patch)<16<<20
 name=a.tag+'-delta.lz4';(o/name).write_bytes(compress(patch));nd=digest(b/'luma3d-riscv')
 m['delta']=dict(file=name,old_sha256=digest(BASE/'luma3d-riscv')['sha256'],new_sha256=nd['sha256'],new_bytes=nd['bytes'],new_crc32=nd['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
 with tempfile.TemporaryDirectory(prefix='showcase-delta-') as temp:
  rebuilt=Path('/tmp/'+Path(temp).name+'.elf')
  try:
   result=subprocess.run([o/'helper-host','patch',o/name,rebuilt,str(len(patch)),m['delta']['patch_crc32'],BASE/'luma3d-riscv'],capture_output=True);(o/'delta_reconstruction.log').write_bytes(result.stdout+result.stderr);result.check_returncode();assert digest(rebuilt)==nd
  finally:
   if rebuilt.exists():rebuilt.unlink()
 prefix=b/'captures/arrival';oracle=json.loads(prefix.with_suffix('.reference.json').read_text());overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();image=prefix.with_suffix('.rgb565').read_bytes();assert len(image)==192000 and hashlib.sha256(image).hexdigest()==oracle['image_sha256']
 def packed(name,data):
  (o/name).write_bytes(compress(data));ref=dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
  subprocess.run([o/'helper-host','verify',o/name,'unused',str(len(data)),ref['crc32']],check=True,capture_output=True);return ref
 end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1);hud=memory[20<<20:end];assert 0<len(hud)<=240000 and not len(hud)%800
 m['first']=dict(oracle=oracle,pixels=packed(a.tag+'-pixels.lz4',image),hud=dict(**packed(a.tag+'-hud.lz4',hud),bank=20))
 for suffix in ['png','reference.json','overlay.json']:shutil.copy2(prefix.with_suffix('.'+suffix),o/('first.'+suffix))
 m['transfer_files']=[m['helper'],m['delta']['file'],m['first']['pixels']['file'],m['first']['hud']['file']]
 m['files']={f.name:digest(f) for f in sorted(o.iterdir()) if f.is_file()};m['transport_bytes']=sum(m['files'][n]['bytes'] for n in m['transfer_files'])
 (o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(o/'manifest.json'),elf=m['game'],transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
