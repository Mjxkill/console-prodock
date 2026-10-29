#!/usr/bin/env python3
"""Freeze MO1 dependencies, exact patches/oracles and proof links. Local only."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
PRIOR=R/'games/luma3d/tests/hardware/polish_20261027_pp2_prepared_r2'
RESULT=R/'games/luma3d/tests/hardware/polish_20261027_pp2_result/result.json'
BASE=R/'games/luma3d/build/arcade_polish_20261026_r6'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta
sys.path.insert(0,str(C));from prodock_motion import digest,WINDOWS,EXACT_KEYS,parse_result,compare

def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--probe',type=Path,required=True);p.add_argument('--rv32',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
 assert re.fullmatch(r'mo[0-9]+',a.tag);b=a.build.resolve();q=a.probe.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 for source,name in [(b/'manifest.json','game_manifest.json'),(BASE/'manifest.json','baseline_manifest.json'),(q/'result.json','probe_validation.json'),(a.rv32/'result.json','probe_rv32_validation.json'),(RESULT,'prior_result.json'),(C/'provenance/kernel_memory.json','kernel_memory.json'),(C/'provenance/root_memory_review_01.json','root_memory_review_01.json'),(C/'tests/ui/strict_r4/result.json','ui_strict.json'),(C/'tests/ui/asan_r4/result.json','ui_asan.json')]:shutil.copy2(source,o/name)
 for directory in (b,BASE):
  m=json.loads((directory/'manifest.json').read_text());assert digest(directory/'luma3d-riscv')==m['riscv']
  for name,r in m['files'].items():assert digest(directory/'source'/name)['sha256']==r['sha256']
 pv=json.loads((q/'result.json').read_text());assert pv['passed'] and pv['game_manifest_sha256']==digest(b/'manifest.json')['sha256']
 for name,r in pv['files'].items():assert digest(q/name)==r
 prior=json.loads((PRIOR/'manifest.json').read_text());assert digest(PRIOR/'manifest.json')['sha256']=='989eba8d12faa0965cd8b9c322fe1e970595923580d91fffc4efdbead626b2a0'
 for name in ['prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','runtime_inspect.c','prodock-uapi.h','helper-host','pp2-helper']:
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,o/(a.tag+'-helper' if name=='pp2-helper' else name))
 for name in ['prodock_motion.py','trial_guards.py','prepare_motion_trial.py','test_motion_trial.py','PLAN_MATERIEL_MO1.txt']:shutil.copy2(C/name,o/name)
 for name in ['motion_probe.c','baseline_mini_ui.c']:shutil.copy2(q/name,o/name)
 m=dict(candidate=True,hardware_tested=False,tag=a.tag,helper=a.tag+'-helper',baseline=json.loads((BASE/'manifest.json').read_text())['riscv'],expected_identity=dict(pid=2472,start_ticks=21513398),windows=WINDOWS,wall=dict(kind=4,seconds=20),deadlines=dict(fixture=180,window=600,wall=120),probes={})
 def patch_file(name,old,new):
  raw=delta(old.read_bytes(),new.read_bytes());assert len(raw)<16<<20;(o/name).write_bytes(compress(raw));nd=digest(new)
  d=dict(file=name,old_sha256=digest(old)['sha256'],new_sha256=nd['sha256'],new_bytes=nd['bytes'],new_crc32=nd['crc32'],patch_bytes=len(raw),patch_crc32=f'{zlib.crc32(raw):08x}')
  with tempfile.TemporaryDirectory(prefix='motion-delta-') as tmp:
   rebuilt=Path('/tmp/'+Path(tmp).name+'.elf')
   try:
    run=subprocess.run([o/'helper-host','patch',o/name,rebuilt,str(len(raw)),d['patch_crc32'],old],capture_output=True);(o/(name+'.reconstruct.log')).write_bytes(run.stdout+run.stderr);run.check_returncode();assert digest(rebuilt)==nd
   finally:
    if rebuilt.exists():rebuilt.unlink()
  return d
 for variant in ('baseline','candidate'):
  m['probes'][variant]=dict(program=a.tag+'-'+variant,binary=digest(q/(variant+'-riscv')),delta=patch_file(a.tag+'-'+variant+'.lz4',BASE/'luma3d-riscv' if variant=='baseline' else q/'baseline-riscv',q/(variant+'-riscv')))
 def packed(name,data):
  (o/name).write_bytes(compress(data));r=dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
  subprocess.run([o/'helper-host','verify',o/name,'unused',str(len(data)),r['crc32']],check=True,capture_output=True);return r
 m['fixtures']=[];m['references']=[]
 for kind in (4,6):
  name=f'candidate_{kind}_800';prefix=q/name;oracle=json.loads(prefix.with_suffix('.reference.json').read_text());memory=prefix.with_suffix('.memory').read_bytes()
  for suffix in ('png','reference.json','overlay.json','commands'):shutil.copy2(prefix.with_suffix('.'+suffix),o/(name+'.'+suffix))
  assert prefix.with_suffix('.memory').read_bytes()==(q/f'baseline_{kind}_800.memory').read_bytes()
  pixels=packed(a.tag+f'-{kind}-pixels.lz4',prefix.with_suffix('.rgb565').read_bytes()) if kind==4 else None
  if pixels:assert pixels['sha256']==oracle['image_sha256'];m['references'].append(pixels)
  region=dict(**packed(a.tag+f'-{kind}-ui.lz4',memory[22<<20:(22<<20)+384000]),offset=22<<20);m['references'].append(region)
  m['fixtures'].append(dict(kind=kind,oracle=oracle,pixels=pixels,region=region))
 fixed=dict(passed=False,hardware=False,windows=WINDOWS,records=[])
 for i,w in enumerate(WINDOWS):
  cmd=[str(q/(w['variant']+'-host')),'--host','--kind',str(w['kind']),'--frames',str(w['frames'])]
  run=subprocess.run(cmd,capture_output=True,timeout=180);(o/f'window{i}.log').write_bytes(run.stdout+run.stderr);run.check_returncode()
  fixed['records'].append(dict(**w,elf_sha256=pv['files'][w['variant']+'-host']['sha256'],measurement=parse_result(run.stdout,w['kind'],frames=w['frames'],hardware=0)))
 fixed['comparison']=compare(fixed['records']);fixed['passed']=True;(o/'fixed_windows.json').write_text(json.dumps(fixed,indent=2)+'\n')
 m['expected_windows']=[{k:r['measurement']['result'][k] for k in EXACT_KEYS} for r in fixed['records']]
 m['transfer_files']=[m['helper'],*[m['probes'][v]['delta']['file'] for v in ('baseline','candidate')],*[r['file'] for r in m['references']]]
 m['files']={p.name:digest(p) for p in sorted(o.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][n]['bytes'] for n in m['transfer_files'])
 (o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(o/'manifest.json'),probes=m['probes'],transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
