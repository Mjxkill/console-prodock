#!/usr/bin/env python3
"""Freeze all MC1 inputs, deltas and published rectangles. Never access a board."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3];PRIOR=R/'games/luma3d/tests/hardware/gpu_motion_20261027_gm1_prepared_r2';BASE=R/'games/luma3d/build/maze_events_20261027_r4'
sys.path.insert(1,str(PRIOR));from build_delta import compress,delta
from prodock_mesh_cache import digest,WINDOWS,FIXTURES,EXACT,COPY_EXACT,PERFORMANCE
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--probe',type=Path,required=True);p.add_argument('--windows',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--rv32',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
assert re.fullmatch(r'mc[0-9]+',a.tag);b=a.build.resolve();q=a.probe.resolve();f=a.fixtures.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
for directory in (b,BASE):
 m=json.loads((directory/'manifest.json').read_text());assert digest(directory/'luma3d-riscv')==m['riscv']
 for name,r in m['files'].items():assert digest(directory/'source'/name)['sha256']==r['sha256']
pm=json.loads((q/'manifest.json').read_text());wp=json.loads((a.windows/'result.json').read_text());fp=json.loads((f/'result.json').read_text());rv=json.loads((a.rv32/'result.json').read_text())
assert wp['passed'] and fp['passed'] and rv['passed'] and wp['probe_manifest_sha256']==fp['probe_manifest_sha256']==rv['probe_manifest_sha256']==digest(q/'manifest.json')['sha256']
assert rv['fixtures_sha256']==digest(f/'result.json')['sha256'] and rv['windows_sha256']==digest(a.windows/'result.json')['sha256']
for rec in pm['records']:
 assert digest(q/(rec['variant']+'-'+rec['target']))['sha256']==rec['elf_sha256']
 for path,h in rec['sources'].items():assert digest(R/path)['sha256']==h
prior=json.loads((PRIOR/'manifest.json').read_text());assert digest(PRIOR/'manifest.json')['sha256']=='ed04a3f1b41e07f75d9f0c97770f473fb15748cab28d24fa58f98259e407d64a'
for name in ['prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py','prodock-uapi.h']:
 assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,o/name)
for name in ['prodock_mesh_cache.py','probe_metrics.py','trial_guards.py','prepare_trial.py','PLAN_MC1.md','runtime_inspect.c','test_helper.c','cache_probe.c','probe_mesh.h','build_probe.py','validate_probe.py','fixtures.py','validate_rv32.py','test_trial.py']:
 shutil.copy2((C if (C/name).exists() else PRIOR)/name,o/name)
for source,name in [(b/'manifest.json','game_manifest.json'),(BASE/'manifest.json','baseline_manifest.json'),(q/'manifest.json','probe_manifest.json'),(a.windows/'result.json','probe_validation.json'),(f/'result.json','fixtures_validation.json'),(a.rv32/'result.json','probe_rv32.json'),(R/'games/luma3d/tests/hardware/gpu_motion_20261027_gm1_result/result.json','prior_result.json'),(C.parent/'maze_publish_cache_r1/handoff_r3.json','game_handoff.json'),(C.parent/'arcade_motion_r1/provenance/root_memory_review_01.json','kernel_memory_review.json')]:shutil.copy2(source,o/name)
cc=R/'linux/build/userbin/riscv32-prodock-linux-gcc'
for output,compiler,extra in [('helper-host','cc',[]),(a.tag+'-helper',str(cc),['-static'])]:
 cmd=[compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(o),*extra,str(o/'runtime_inspect.c'),'-o',str(o/output)];r=subprocess.run(cmd,capture_output=True);(o/(output+'.compile.log')).write_bytes(r.stdout+r.stderr);r.check_returncode()
subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(o),o/'test_helper.c','-o',o/'test-helper'],check=True)
result=subprocess.run([o/'test-helper'],capture_output=True,check=True);(o/'helper_test.log').write_bytes(result.stdout+result.stderr)
m=dict(candidate=True,hardware_tested=False,tag=a.tag,helper=a.tag+'-helper',baseline=digest(BASE/'luma3d-riscv'),game=dict(binary=digest(b/'luma3d-riscv')),expected_identity=dict(pid=2925,start_ticks=26240721),programs={},probe_binaries={v:digest(q/(v+'-riscv')) for v in ('baseline','candidate')},windows=[dict(variant=v,kind=k,frames=360) for v,k in WINDOWS],deadlines=dict(fixture=240,window=600),fixtures=[],references=[])
m['performance_policy']=PERFORMANCE;m['normal_exit']='restore_gm1'
def patch_file(name,old,new):
 raw=delta(old.read_bytes(),new.read_bytes());assert len(raw)<16<<20;(o/name).write_bytes(compress(raw));nd=digest(new)
 d=dict(file=name,old_sha256=digest(old)['sha256'],new_sha256=nd['sha256'],new_bytes=nd['bytes'],new_crc32=nd['crc32'],patch_bytes=len(raw),patch_crc32=f'{zlib.crc32(raw):08x}')
 with tempfile.TemporaryDirectory(prefix='gm1-delta-') as tmp:
  rebuilt=Path('/tmp/'+Path(tmp).name+'.elf')
  try:
   result=subprocess.run([o/'helper-host','patch',o/name,rebuilt,str(len(raw)),d['patch_crc32'],old],capture_output=True);(o/(name+'.reconstruct.log')).write_bytes(result.stdout+result.stderr);result.check_returncode();assert digest(rebuilt)==nd
  finally:
   if rebuilt.exists():rebuilt.unlink()
 return d
old=BASE/'luma3d-riscv'
for key,new in [('baseline',q/'baseline-riscv'),('candidate',q/'candidate-riscv')]:
 m['programs'][key]=dict(program='luma3d-'+a.tag if key=='game' else a.tag+'-'+key,binary=digest(new),delta=patch_file(a.tag+'-'+key+'.lz4',old,new));old=new
def packed(name,data):
 (o/name).write_bytes(compress(data));r=dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
 subprocess.run([o/'helper-host','verify',o/name,'unused',str(len(data)),r['crc32']],check=True,capture_output=True);m['references'].append(r);return r
for i,(kind,frames,restart,back) in enumerate(FIXTURES):
 rec=next(x for x in fp['records'] if x['kind']==kind and x['frames']==frames and x['width']==800 and x['restart_at']==restart and x['back_at']==back);prefix=f/rec['name'];row=dict(kind=kind,frames=frames,restart_at=restart,back_at=back,oracle=rec['oracle'],rect=None)
 for ext in ('png','reference.json','overlay.json','commands'):shutil.copy2(prefix.with_suffix('.'+ext),o/(rec['name']+'.'+ext))
 row['ui']=[]
 for j,u in enumerate(rec['ui']):
  part=dict(**packed(a.tag+f'-ui{i}_{j}.lz4',prefix.with_suffix(u['extension']).read_bytes()),offset=u['offset']);assert part['sha256']==u['sha256'];row['ui'].append(part)
 if rec['rect']:
  row['rect']=packed(a.tag+f'-rect{i}.lz4',prefix.with_suffix('.rect').read_bytes());assert row['rect']['sha256']==rec['rect']['sha256'];row['rect'].update({k:rec['rect'][k] for k in ('offset','pitch','width','height')})
 m['fixtures'].append(row)
m['expected_windows']=[[{k:p[k] for k in EXACT} for p in next(r['result']['phases'] for r in wp['records'] if r['variant']==v and r['kind']==kind and r['width']==800)] for v,kind in WINDOWS]
m['expected_copies']=[[{k:p[k] for k in COPY_EXACT} for p in next(r['result']['copies'] for r in wp['records'] if r['variant']==v and r['kind']==kind and r['width']==800)] for v,kind in WINDOWS]
m['transfer_files']=[m['helper'],*[m['programs'][k]['delta']['file'] for k in ('baseline','candidate')],*[r['file'] for r in m['references']]]
cache=C.parent/'maze_publish_cache_r1'
for source,name in [(cache/'tests/render_equivalence_r2/result.json','render_equivalence.json'),(cache/'tests/results_r3/result.json','cache_unit.json'),(cache/'tests/review_counterexample_r1/result.json','cache_counterexample.json'),(cache/'review_code_r1/VERDICT.md','cache_review.md')]:shutil.copy2(source,o/name)
unit=json.loads((cache/'tests/results_r3/result.json').read_text())
for name,h in unit['inputs'].items():
 assert digest(cache/name)['sha256']==h
 shutil.copy2(cache/name,o/('cache_'+name.replace('/','_')))
m['files']={p.name:digest(p) for p in sorted(o.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][name]['bytes'] for name in m['transfer_files']);(o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(manifest=digest(o/'manifest.json'),transport_bytes=m['transport_bytes'],game=m['game']),indent=2))
