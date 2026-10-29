#!/usr/bin/env python3
"""Local diagnostic build; frozen runtime inputs are verified, never edited."""
import argparse,difflib,hashlib,json,os,shutil,subprocess
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
B=R/'games/luma3d/build/arcade_world_20261026_r2'
NAMES=('activity_5_flash','activity_5_input','activity_6','activity_6_boss','activity_7','activity_7_mid')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log):
 r=subprocess.run(list(map(str,cmd)),capture_output=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'});log.write_bytes(r.stdout+r.stderr);r.check_returncode();return r
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 assert sha(B/'manifest.json')=='7087948802f13b348c020c5c0087efd312a779ddacccfb5acf71011b5482546a'
 m=json.loads((B/'manifest.json').read_text());s=B/'source';g=s/'games/luma3d'
 for name,r in m['files'].items():assert sha(s/name)==r['sha256'],name
 route=B/'review_inputs/tests/test_paths.c';original=route.read_text()
 start=original.index('static const uint32_t ids[]');end=original.index('/* Every route')
 core=original[:start]+original[end:]
 core=core.replace('l3_game_step(', 'ar_step(').replace('l3_activity_step(', 'ar_activity_step(').replace('capture(', 'ar_capture(').replace('int main(void)', 'static int ar_route_main(void)')
 assert core.count('if(i==4)save_resume(g);')==1
 core=core.replace('if(i==4)save_resume(g);','if(i==4){save_resume(g);ar_reload(g);paused=*g;}')
 assert core.count('assert(g.activities.arcade.won==255&&l3_activities_valid(&g));')==1
 core=core.replace('assert(g.activities.arcade.won==255&&l3_activities_valid(&g));','assert(g.activities.arcade.won==255&&l3_activities_valid(&g));ar_finish(&g);')
 (o/'route_original.c').write_text(original);(o/'route_core.inc').write_text(core)
 (o/'route_hooks.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),core.splitlines(True),fromfile='frozen_route',tofile='diagnostic_hooks')))
 for name in ('route_probe.c','runtime_inspect.c','build_probe.py','test_helper.c','fixture_input.c'):shutil.copy2(C/name,o/name)
 shutil.copy2(s/'linux/drivers/prodock-uapi.h',o/'prodock-uapi.h')
 inc=[o,g/'include',g/'world',g/'minigames',s/'fw_console',s/'linux/drivers']
 sources=[o/'route_probe.c',*[x for x in sorted((g/'src').glob('*.c')) if x.name!='main.c'],*sorted((g/'minigames').glob('*.c')),g/'world/data.c',s/'fw_console/gpu_v1.c',s/'fw_console/gpu_geometry.c']
 flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffp-contract=off','-ffunction-sections','-fdata-sections'];commands=[]
 for target,cc,extra in [('host','cc',[]),('riscv',R/'linux/build/userbin/riscv32-prodock-linux-gcc',['-static'])]:
  cmd=[cc,*flags,*extra,*['-I'+str(x) for x in inc],*sources,'-Wl,--gc-sections','-lm','-o',o/('probe-'+target)];commands.append(list(map(str,cmd)));run(cmd,o/('compile_probe_'+target+'.log'))
  cmd=[cc,*flags,*extra,'-I'+str(o),o/'runtime_inspect.c','-o',o/('helper-'+target)];commands.append(list(map(str,cmd)));run(cmd,o/('compile_helper_'+target+'.log'))
 run(['cc',*flags,'-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(o),o/'test_helper.c','-o',o/'test-helper'],o/'compile_helper_tests.log')
 run([o/'test-helper'],o/'helper_tests.log')
 fixtures=o/'fixtures';fixtures.mkdir()
 run(['cc',*flags,*['-I'+str(x) for x in inc],o/'fixture_input.c',*sources[1:],'-Wl,--gc-sections','-lm','-o',o/'fixture-input'],o/'compile_fixture.log')
 for name in NAMES:
  prefix=fixtures/name
  if name=='activity_5_input':run([o/'fixture-input',B/'captures/activity_5.save',prefix.with_suffix('.save')],o/'fixture_input.log')
  else:shutil.copy2(B/'captures'/f'{name}.save',prefix.with_suffix('.save'))
  run([o/'probe-host','--host','--capture',prefix],o/(name+'_host.log'))
  meta=json.loads(prefix.with_suffix('.json').read_text());meta['commands_last']=meta['commands'];meta['commands']=prefix.with_suffix('.commands').stat().st_size//32;meta['captured_frames']=3;prefix.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
  preview=C.parent/'adventure_arcade_world_r1/tests/preview.py';assert sha(preview)==sha(B/'review_inputs/tests/preview.py')
  run(['python3',preview,prefix],o/(name+'_oracle.log'))
 save=Path('/tmp/'+o.name+'-replay.save')
 assert not save.exists()
 try:
  run([o/'probe-host','--host','--replay',save],o/'replay_host.log');shutil.copy2(save,o/'replay_host.save')
 finally:
  if save.exists():save.unlink()
 record=dict(passed=True,hardware=False,build_manifest_sha256=sha(B/'manifest.json'),commands=commands,source_files={str(x.relative_to(R)):sha(x) for x in sources},route_original_sha256=sha(route),fixtures=list(NAMES),helper_tests='ASan/UBSan; LeakSanitizer disabled because sandbox ptrace is unsupported',scope='Six fixed scenes; eight legal-input victories; eight actual mid-activity V5 reloads; accelerated sampled walking, every arcade command rendered; no human duration or FPS')
 record['files']={str(x.relative_to(o)):{'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(o.rglob('*')) if x.is_file()}
 (o/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(o,flush=True)
if __name__=='__main__':main()
