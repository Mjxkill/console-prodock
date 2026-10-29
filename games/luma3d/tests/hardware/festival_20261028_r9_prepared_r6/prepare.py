#!/usr/bin/env python3
"""Local-only freeze and exact ELF delta reconstruction. No hardware imports."""
import argparse,hashlib,importlib.util,json,shutil,subprocess,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
PRIOR=ROOT/'games/luma3d/tests/hardware/mesh_cache_20261027_mc1_prepared_r2'
BASE=ROOT/'games/luma3d/build/maze_events_20261027_r4'
GAME=ROOT/'games/luma3d/build/festival_20261027_r9'
PROOFS=ROOT/'games/luma3d/candidates/table_games_20261027_r1/tests/frontend_integration_r1'
def digest(path):
 b=path.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 from festival_trial import DEPS,ANCHOR,BASE_SHA,SAVE_SHA,RELEASE,FPGA_SHA,PORT,LOCK,SSH_HOST,LOCAL_HOSTNAME,MIN_TMP_KIB,schedule,check_helper_proof
 ap=argparse.ArgumentParser();ap.add_argument('--reuse-proof',type=Path,required=True);args=ap.parse_args()
 assert (args.reuse_proof/'result.json').is_file() and (args.reuse_proof/'helper_verified.bin').is_file(),'Completed root helper proof required'
 assert not (HERE/'manifest.json').exists(),'Already frozen; use a new prepared directory'
 reference=ROOT/'tang/boards/prodock/reference.json'
 assert json.loads(reference.read_text())['bitstream_sha256']==FPGA_SHA,'Controller FPGA identity differs from external protected reference'
 shutil.copy2(reference,HERE/'fpga_reference.json')
 old_manifest=json.loads((PRIOR/'manifest.json').read_text())
 for name in (*[n for n in DEPS if n!='guarded_transport.py'],'build_delta.py','runtime_inspect.c','prodock-uapi.h','helper-host','mc1-helper','test_helper.c'):
  assert digest(PRIOR/name)==old_manifest['files'][name],name
  shutil.copy2(PRIOR/name,HERE/('mc1-helper' if name=='mc1-helper' else name))
 from patch_readback import apply
 benchmark=HERE/'prodock_valley_benchmark.py';benchmark.write_text(apply(benchmark.read_text()))
 guard=ROOT/'games/luma3d/candidates/festival_transport_guard_20261027_r1'
 shutil.copy2(guard/'guarded_transport.py',HERE/'guarded_transport.py')
 shutil.copy2(guard/'receiver_exact_r2/result.json',HERE/'receiver_exact.json')
 shutil.copy2(guard/'receiver_exact_r2/initrd.cpio.gz',HERE/'receiver-test-initrd.cpio.gz')
 subprocess.run(['python3','-B',str(HERE/'test_transport_guard.py')],check=True)
 shutil.copy2(PRIOR/'manifest.json',HERE/'transport_source_manifest.json')
 for path in (BASE,GAME):
  m=json.loads((path/'manifest.json').read_text());assert digest(path/'luma3d-riscv')==m['riscv']
  for name,rec in m['files'].items():assert digest(path/'source'/name)['sha256']==rec['sha256']
 assert digest(BASE/'luma3d-riscv')['sha256']==BASE_SHA
 for src,dst in [(BASE/'manifest.json','baseline_manifest.json'),(GAME/'manifest.json','game_manifest.json'),(ROOT/'games/luma3d/tests/hardware/mesh_cache_20261027_mc1_result/result.json','prior_result.json'),(ROOT/'games/luma3d/candidates/maze_background_gpu_r1/hardware_protocol_r1/plan.json','anchor_protocol.json')]:shutil.copy2(src,HERE/dst)
 for name in ('logic_r9','logic_r9_sanitize','temporal_r9','temporal_r9_sanitize','cli_r9'):shutil.copy2(PROOFS/name/'result.json',HERE/(name+'.json'))
 spec=importlib.util.spec_from_file_location('frozen_delta',HERE/'build_delta.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 raw=mod.delta((BASE/'luma3d-riscv').read_bytes(),(GAME/'luma3d-riscv').read_bytes());packed=mod.compress(raw);(HERE/'festival-r9f.delta.lz4').write_bytes(packed)
 game=digest(GAME/'luma3d-riscv');d=dict(file='festival-r9f.delta.lz4',old_sha256=BASE_SHA,new_sha256=game['sha256'],new_bytes=game['bytes'],new_crc32=game['crc32'],patch_bytes=len(raw),patch_crc32=f'{zlib.crc32(raw):08x}')
 with tempfile.TemporaryDirectory(prefix='festival-r9-') as tmp:
  output=Path('/tmp/'+Path(tmp).name+'.elf');cmd=[str(HERE/'helper-host'),'patch',str(HERE/d['file']),str(output),str(len(raw)),d['patch_crc32'],str(BASE/'luma3d-riscv')]
  try:
   q=subprocess.run(cmd,capture_output=True);(HERE/'reconstruction.log').write_bytes(q.stdout+q.stderr);q.check_returncode();assert digest(output)==game
  finally:
   if output.exists():output.unlink()
 (HERE/'reconstruction.json').write_text(json.dumps(dict(passed=True,hardware=False,game=game,delta=d,transport=digest(HERE/d['file']),helper_sha256=digest(HERE/'helper-host')['sha256']),indent=2)+'\n')
 shutil.copy2(args.reuse_proof/'result.json',HERE/'helper_reuse_result.json')
 shutil.copy2(args.reuse_proof/'helper_verified.bin',HERE/'helper_reuse_verified.bin')
 m=dict(schema=1,controller_revision=6,previous_manifest_sha256='2f2837b1e88dcbcb245dee9e1441e5f1ac557d29ada7597b2e763d087eb1869d',candidate=True,hardware_tested=False,hardware_ready=False,board='prodock',host=SSH_HOST,local_hostname=LOCAL_HOSTNAME,port=PORT,lock=LOCK,tag='festivalr9f',program='luma3d-f9f',helper='mc1-helper',expected_identity=ANCHOR,baseline=digest(BASE/'luma3d-riscv'),game=game,game_manifest_sha256=digest(GAME/'manifest.json')['sha256'],save_sha256=SAVE_SHA,kernel=RELEASE,fpga_sha256=FPGA_SHA,delta=d,transfer_files=[d['file']],windows=schedule(),normal_exit='restore_gm1',review_required=True,forbidden_writes=['FPGA','JTAG','kernel','SD','flash','save'])
 m['storage_guard']={'mount':'/tmp','minimum_available_kib':MIN_TMP_KIB,'check':'before_each_transfer_and_reconstruction'}
 m['transport_bytes']=sum((HERE/n).stat().st_size for n in m['transfer_files'])
 excluded={'manifest.json','local_tests.json','launch_recovery_tests.json','transport_integration_tests.json','capacity_tests.json','deadline_tests.json','helper_reuse_tests.json','external_anchor_tests.json'}
 m['files']={p.name:digest(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in excluded}
 m['helper_reuse']={'path':'/tmp/mc1-helper','method':'root_full_readback_then_runtime_size_crc','proof':'helper_reuse_result.json','readback':'helper_reuse_verified.bin'}
 check_helper_proof(HERE,m)
 (HERE/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest_sha256=digest(HERE/'manifest.json')['sha256'],transport_bytes=m['transport_bytes'],game=game)))
if __name__=='__main__':main()
