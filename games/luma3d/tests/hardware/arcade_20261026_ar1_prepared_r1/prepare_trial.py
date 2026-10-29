#!/usr/bin/env python3
"""Freeze arcade runtime, references, probe, and transport; no hardware access."""
import argparse,hashlib,json,re,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PRIOR=REPO/'games/luma3d/tests/hardware/paths_20261026_op2_prepared_r1'
BASE=REPO/'games/luma3d/build/amber_paths_20261026_r5';NEW=REPO/'games/luma3d/build/arcade_world_20261026_r2'
sys.path.insert(0,str(PRIOR));from build_delta import compress,delta
from prodock_valley_benchmark import fields
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def run(cmd,log=None):
 r=subprocess.run(list(map(str,cmd)),capture_output=True)
 if log:log.write_bytes(r.stdout+r.stderr)
 r.check_returncode();return r
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--probe-build',type=Path,required=True);p.add_argument('--probe-rv32',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args();assert re.fullmatch(r'ar[0-9]+',a.tag)
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);probe=a.probe_build.resolve();pm=json.loads((probe/'result.json').read_text());assert pm['passed'] and not pm['hardware']
 pv=json.loads(a.probe_rv32.read_text());assert pv['passed'] and not pv['hardware'] and pv['probe_manifest_sha256']==digest(probe/'result.json')['sha256'] and len(pv['records'])==7
 assert all(x['probe_sha256']==digest(probe/'probe-riscv')['sha256'] for x in pv['records'])
 for name,r in pm['files'].items():assert digest(probe/name)['sha256']==r['sha256'] and (probe/name).stat().st_size==r['bytes']
 expected={'baseline':'8f7500184ccf9977502243e5ddfbfb3b27f4b5b224dde46c606d8bdcf8f18981','game':'3ae9c784195280d9653c08117d56b48611c4a209f8c622bf68c2921a3b2a2659'};manifests={}
 for key,build in [('baseline',BASE),('game',NEW)]:
  j=json.loads((build/'manifest.json').read_text());assert digest(build/'luma3d-riscv')==j['riscv'] and j['riscv']['sha256']==expected[key]
  for name,r in j['files'].items():assert digest(build/'source'/name)['sha256']==r['sha256']
  manifests[key]=j;shutil.copy2(build/'manifest.json',out/(key+'_manifest.json'))
 native=json.loads((NEW/'rv32_validation.json').read_text());assert native['passed'] and len(native['records'])==16;shutil.copy2(NEW/'rv32_validation.json',out/'rv32_validation.json')
 v=json.loads((NEW/'local_validation.json').read_text());assert v['passed'] and not v['hardware_tested'] and v['elf']==manifests['game']['riscv']
 for name,expected_sha in v['proofs'].items():assert digest(REPO/name)['sha256']==expected_sha
 assert pm['build_manifest_sha256']==digest(NEW/'manifest.json')['sha256']
 prior=json.loads((PRIOR/'manifest.json').read_text())
 for name in ('prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py','check_linux.py','check_gpu_reloads.py'):
  assert digest(PRIOR/name)==prior['files'][name];shutil.copy2(PRIOR/name,out/name)
 for name in ('prodock_arcade.py','prepare_trial.py','test_trial.py','TRIAL_PLAN.txt','test_helper.c'):shutil.copy2(HERE/name,out/name)
 for name in ('runtime_inspect.c','prodock-uapi.h','route_probe.c','route_core.inc','route_original.c','route_hooks.patch','helper-host','build_probe.py'):
  shutil.copy2(probe/name,out/name)
 shutil.copy2(probe/'helper-riscv',out/(a.tag+'-helper'));shutil.copy2(probe/'result.json',out/'probe_validation.json');shutil.copy2(NEW/'local_validation.json',out/'local_validation.json')
 shutil.copy2(a.probe_rv32,out/'probe_rv32_validation.json');shutil.copy2(HERE/'validate_rv32.py',out/'validate_rv32.py')
 m=dict(candidate=True,hardware_tested=False,tag=a.tag,program='luma3d-'+a.tag,probe=a.tag+'-probe',helper=a.tag+'-helper',game=manifests['game']['riscv'],baseline=manifests['baseline']['riscv'],probe_binary=digest(probe/'probe-riscv'),validation=v,rv32_validation=native,probe_validation=pm,probe_rv32_validation=pv,
  acceptance=dict(max_arrival_slowdown=.10,max_witness_drift=.05),reference_files=[],fixture_files=[],fixtures=[],benchmarks=[],initial_guard='Fresh exact OP2 comm/cmdline/ELF CRC and monotonic startticks; no stale PID',host_replay=fields((probe/'replay_host.log').read_bytes(),'AR_COMPLETE'))
 def packed(name,data,category):
  (out/name).write_bytes(compress(data));r=dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
  run([out/'helper-host','verify',out/name,'unused',len(data),r['crc32']]);m[category].append(name);return r
 for key,old,new in [('delta',BASE/'luma3d-riscv',NEW/'luma3d-riscv'),('probe_delta',NEW/'luma3d-riscv',probe/'probe-riscv')]:
  patch=delta(old.read_bytes(),new.read_bytes());assert len(patch)<16<<20;name=a.tag+'-'+key+'.lz4';(out/name).write_bytes(compress(patch));nd=digest(new)
  m[key]=dict(file=name,old_sha256=digest(old)['sha256'],new_sha256=nd['sha256'],new_bytes=nd['bytes'],new_crc32=nd['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
  with tempfile.TemporaryDirectory(prefix='luma-paths-') as temp:
   rebuilt=Path('/tmp/'+Path(temp).name+'.elf')
   try:run([out/'helper-host','patch',out/name,rebuilt,len(patch),m[key]['patch_crc32'],old],out/(key+'_reconstruction.log'));assert digest(rebuilt)==nd
   finally:
    if rebuilt.exists():rebuilt.unlink()
 refs=out/'oracle';refs.mkdir()
 def image_ref(prefix,label,bank=20,pixels=True):
  oracle=json.loads(prefix.with_suffix('.reference.json').read_text());overlay=json.loads(prefix.with_suffix('.overlay.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();native=prefix.with_suffix('.rgb565').read_bytes()
  assert len(native)==192000 and hashlib.sha256(native).hexdigest()==oracle['image_sha256']
  end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1);data=memory[bank<<20:end];assert 0<len(data)<=(384000 if bank==22 else 240000) and not len(data)%800
  result=dict(oracle=oracle,pixels=packed(a.tag+'-'+label+'-pixels.lz4',native,'reference_files') if pixels else None,hud=dict(**packed(a.tag+'-'+label+'-hud.lz4',data,'reference_files'),bank=bank))
  for suffix in ('.reference.json','.overlay.json'):
   source=prefix.with_suffix(suffix);target=refs/(label+suffix)
   if source.resolve()!=target.resolve():shutil.copy2(source,target)
  return result
 for variant,build in [('op2',BASE),('new',NEW)]:
  prefix=refs/variant
  run([build/'luma3d-host','--host','--frames','1','--capture',prefix],out/(variant+'_capture.log'))
  run([sys.executable,REPO/'games/luma3d/candidates/terrain_surface_r1/render_preview.py',prefix],out/(variant+'_oracle.log'))
  ref=image_ref(prefix,variant);r=run([build/'luma3d-host','--host','--benchmark','--frames','30','--warmup','3'],out/(variant+'_benchmark.log'))
  m['benchmarks'].append(dict(variant=variant,pose=0,**ref,host_benchmark=fields(r.stdout,'LUMA3D_RESULT')))
 m['benchmarks'].append(m['benchmarks'][0])
 for name in pm['fixtures']:
  prefix=probe/'fixtures'/name;pixel=not name.startswith('activity_6')
  state=packed(a.tag+'-'+name+'-state.lz4',prefix.with_suffix('.save').read_bytes(),'fixture_files');hostlog=(probe/(name+'_host.log')).read_bytes()
  oracle=json.loads(prefix.with_suffix('.reference.json').read_text());memory=prefix.with_suffix('.memory').read_bytes();assert len(memory)==32<<20
  raw=prefix.with_suffix('.rgb565').read_bytes();assert len(raw)==192000 and hashlib.sha256(raw).hexdigest()==oracle['image_sha256']
  regions=[]
  spans=[(22<<20,384000),(23<<20,384000)]+([(28<<20,491520),(30<<20,65536)] if not pixel else [])
  for i,(offset,bytes_) in enumerate(spans):regions.append(dict(**packed(a.tag+'-'+name+'-mem'+str(i)+'.lz4',memory[offset:offset+bytes_],'reference_files'),offset=offset))
  for suffix in ('.reference.json','.overlay.json','.png'):shutil.copy2(prefix.with_suffix(suffix),refs/(name+suffix))
  m['fixtures'].append(dict(name=name,fixture_name=a.tag+'-'+name+'.save',state=state,oracle=oracle,pixels=packed(a.tag+'-'+name+'-pixels.lz4',raw,'reference_files') if pixel else None,regions=regions,host_scene=fields(hostlog,'AR_SCENE'),host_present=fields(hostlog,'AR_PRESENT')))
 # One unchanged user-ELF resume is checked against its own canonical V5,
 # not against the pre-load release-input flag of the fixture.
 active=next(x for x in m['fixtures'] if x['name']=='activity_6_boss')
 resume=out/'resume_expected.save';shutil.copy2(probe/'fixtures/activity_6_boss.save',resume)
 run([NEW/'luma3d-host','--host','--manual','--frames','1','--save',resume],out/'resume_host.log')
 m['resume_expected']=digest(resume)
 m['transfer_files']=[m['helper'],m['delta']['file'],m['probe_delta']['file'],*m['reference_files'],*m['fixture_files']]
 # Evidence from nested oracle files is listed separately; runtime files are
 # all flat, individually hashed, and exactly the transfer list above.
 m['oracle_files']={str(p.relative_to(out)):digest(p) for p in refs.iterdir() if p.is_file() and p.suffix in ('.json','.png')}
 m['files']={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()};m['transport_bytes']=sum(m['files'][name]['bytes'] for name in m['transfer_files'])
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(out/'manifest.json'),game=m['game'],probe=m['probe_binary'],transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
