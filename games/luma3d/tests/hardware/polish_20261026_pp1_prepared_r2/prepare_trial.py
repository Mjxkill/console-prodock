#!/usr/bin/env python3
"""Freeze reviewable PP software trial. No board or network access."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
PRIOR=R/'games/luma3d/tests/hardware/showcase_20261026_sc1_prepared_r1'
BASE=R/'games/luma3d/build/showcase_20261026_r3'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args();assert re.fullmatch(r'pp[0-9]+',a.tag)
 b=a.build.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);manifests={}
 for key,d in [('game',b),('baseline',BASE)]:
  m=json.loads((d/'manifest.json').read_text());assert digest(d/'luma3d-riscv')==m['riscv']
  for name,r in m['files'].items():assert digest(d/'source'/name)['sha256']==r['sha256']
  manifests[key]=m;shutil.copy2(d/'manifest.json',o/(key+'_manifest.json'))
 assert manifests['baseline']['riscv']['sha256']=='b88685f36fe18d8fbdab53652a0683d8ff666c1aae8e3f8b245154fabec88ff6'
 for name in ['local_validation.json','rv32_validation.json','probe_rv32_validation.json','probe_validation.json','common_regression_status.json']:shutil.copy2(b/name,o/name)
 prior=json.loads((PRIOR/'manifest.json').read_text());assert digest(PRIOR/'manifest.json')['sha256']=='2021915b269e5a6f8853eaeff7351b90dfc5d49a4471701b46879d76485b7885'
 for name in ['prodock_showcase.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','runtime_inspect.c','prodock-uapi.h']:
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,o/name)
 # Only extend the read-only owned graphics range for the new sprite atlas.
 helper=(o/'runtime_inspect.c').read_text();old='offset+bytes<=(31u<<20)';assert helper.count(old)==1
 (o/'runtime_inspect.c').write_text(helper.replace(old,'offset+bytes<=(32u<<20)'))
 for target,cc,extra in [('helper-host','cc',[]),(a.tag+'-helper',str(R/'linux/build/userbin/riscv32-prodock-linux-gcc'),['-static'])]:
  cmd=[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*extra,'-I'+str(o),o/'runtime_inspect.c','-o',o/target]
  run=subprocess.run(cmd,capture_output=True);(o/(target+'.compile.log')).write_bytes(run.stdout+run.stderr);run.check_returncode()
 for name in ['prodock_polish.py','prepare_trial.py','test_trial.py','PLAN_MATERIEL.txt']:shutil.copy2(C/name,o/name)
 shutil.copy2(b/'probe/polish_probe.c',o/'polish_probe.c')
 m=dict(candidate=True,hardware_tested=False,tag=a.tag,program='luma3d-'+a.tag,probe=a.tag+'-probe',helper=a.tag+'-helper',game=manifests['game']['riscv'],baseline=manifests['baseline']['riscv'],probe_binary=digest(b/'probe/luma3d-riscv'),deadline_seconds=3700,tour_args='--showcase-once',live_args='--showcase')
 def patch_file(name,old,new):
  raw=delta(old.read_bytes(),new.read_bytes());assert len(raw)<16<<20
  (o/name).write_bytes(compress(raw));nd=digest(new);r=dict(file=name,old_sha256=digest(old)['sha256'],new_sha256=nd['sha256'],new_bytes=nd['bytes'],new_crc32=nd['crc32'],patch_bytes=len(raw),patch_crc32=f'{zlib.crc32(raw):08x}')
  with tempfile.TemporaryDirectory(prefix='polish-delta-') as tmp:
   rebuilt=Path('/tmp/'+Path(tmp).name+'.elf')
   try:
    run=subprocess.run([o/'helper-host','patch',o/name,rebuilt,str(len(raw)),r['patch_crc32'],old],capture_output=True);(o/(name+'.reconstruct.log')).write_bytes(run.stdout+run.stderr);run.check_returncode();assert digest(rebuilt)==nd
   finally:
    if rebuilt.exists():rebuilt.unlink()
  return r
 m['delta']=patch_file(a.tag+'-delta.lz4',BASE/'luma3d-riscv',b/'luma3d-riscv')
 m['probe_delta']=patch_file(a.tag+'-probe-delta.lz4',b/'luma3d-riscv',b/'probe/luma3d-riscv')
 def packed(name,data):
  (o/name).write_bytes(compress(data));r=dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
  subprocess.run([o/'helper-host','verify',o/name,'unused',str(len(data)),r['crc32']],check=True,capture_output=True);return r
 def source(name):
  prefix=b/'captures'/name;oracle=json.loads(prefix.with_suffix('.reference.json').read_text());overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();image=prefix.with_suffix('.rgb565').read_bytes()
  assert len(image)==192000 and hashlib.sha256(image).hexdigest()==oracle['image_sha256']
  for suffix in ['png','reference.json','overlay.json']:shutil.copy2(prefix.with_suffix('.'+suffix),o/(name+'.'+suffix))
  return oracle,overlay,memory,image
 oracle,overlay,memory,image=source('arrival');end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1);hud=memory[20<<20:end]
 m['first']=dict(oracle=oracle,pixels=packed(a.tag+'-first-pixels.lz4',image),hud=dict(**packed(a.tag+'-first-hud.lz4',hud),bank=20))
 points={r['name']:r for r in json.loads((b/'captures/result.json').read_text())['records']};m['fixtures']=[];m['references']=[m['first']['pixels'],m['first']['hud']]
 for active,name in enumerate(['entry_0','entry_1','entry_2','entry_3','entry_4','crystal','boss','checkpoint'],1):
  oracle,overlay,memory,image=source(name);prefix=a.tag+'-'+name
  pixels=packed(prefix+'-pixels.lz4',image) if active in (5,6,8) else None
  regions=[dict(**packed(prefix+'-ui.lz4',memory[22<<20:(22<<20)+384000]),offset=22<<20)]
  if active==7:regions.append(dict(**packed(prefix+'-art.lz4',memory[28<<20:32<<20]),offset=28<<20))
  m['fixtures'].append(dict(name=name,advance=points[name]['advance'],active=active,oracle=oracle,pixels=pixels,regions=regions))
  if pixels:m['references'].append(pixels)
  m['references'].extend(regions)
 m['transfer_files']=[m['helper'],m['delta']['file'],m['probe_delta']['file'],*[r['file'] for r in m['references']]]
 m['files']={p.name:digest(p) for p in sorted(o.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][n]['bytes'] for n in m['transfer_files'])
 (o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(o/'manifest.json'),elf=m['game'],transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
