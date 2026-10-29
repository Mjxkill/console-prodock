#!/usr/bin/env python3
"""Build only a labelled diagnostic against r4; never edits its frozen inputs."""
import argparse,difflib,hashlib,json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
BUILD=REPO/'games/luma3d/build/amber_paths_20261026_r4'
ROUTE=REPO/'games/luma3d/candidates/adventure_amber_paths_r1/tests/test_paths.c'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log,**kw):
 r=subprocess.run(list(map(str,cmd)),capture_output=True,**kw);log.write_bytes(r.stdout+r.stderr);r.check_returncode();return r
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 assert sha(BUILD/'manifest.json')=='fbb46f60e1927efcf58c230689b71d2d9f242279d5e6b2f0bd887f752ec50bee'
 m=json.loads((BUILD/'manifest.json').read_text());s=BUILD/'source';g=s/'games/luma3d'
 for name,r in m['files'].items():assert sha(s/name)==r['sha256'],name
 baseline=ROUTE.read_text();capture_start=baseline.index('static void capture(');capture_end=baseline.index('\n/* Every route',capture_start)
 core=baseline[:capture_start]+baseline[capture_end:]
 core=core.replace('l3_game_step(', 'op1_step(').replace('capture(', 'op1_capture(').replace('int main(void)', 'static int op1_route_main(void)')
 assert core.count('op1_capture(g,name);')==1
 core=core.replace('op1_capture(g,name);','op1_capture(g,name);op1_reload(g);paused=*g;')
 assert core.count('assert(g.activities.won==31&&l3_activities_valid(&g));')==1
 core=core.replace('assert(g.activities.won==31&&l3_activities_valid(&g));','assert(g.activities.won==31&&l3_activities_valid(&g));op1_finish(&g);')
 (out/'route_core.inc').write_text(core);(out/'route_original.c').write_text(baseline)
 (out/'route_hooks.patch').write_text(''.join(difflib.unified_diff(baseline.splitlines(True),core.splitlines(True),fromfile='original',tofile='diagnostic_hooks')))
 for name in ('route_probe.c','runtime_inspect.c','build_probe.py'):shutil.copy2(HERE/name,out/name)
 shutil.copy2(s/'linux/drivers/prodock-uapi.h',out/'prodock-uapi.h')
 inc=[out,g/'include',g/'world',g/'minigames',s/'fw_console',s/'linux/drivers']
 sources=[out/'route_probe.c',*[f for f in sorted((g/'src').glob('*.c')) if f.name!='main.c'],g/'world/data.c',g/'minigames/l3_minigames.c',s/'fw_console/gpu_v1.c',s/'fw_console/gpu_geometry.c']
 flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffp-contract=off','-ffunction-sections','-fdata-sections']
 commands=[]
 for target,cc,extra in [('host','cc',[]),('riscv',REPO/'linux/build/userbin/riscv32-prodock-linux-gcc',['-static'])]:
  cmd=[cc,*flags,*extra,*['-I'+str(x) for x in inc],*sources,'-Wl,--gc-sections','-lm','-o',out/('probe-'+target)];commands.append(list(map(str,cmd)));run(cmd,out/('compile_probe_'+target+'.log'))
  cmd=[cc,*flags,*extra,'-I'+str(out),out/'runtime_inspect.c','-o',out/('helper-'+target)];commands.append(list(map(str,cmd)));run(cmd,out/('compile_helper_'+target+'.log'))
 fixtures=out/'fixtures';fixtures.mkdir();run([out/'probe-host','--host','--fixtures',fixtures],out/'fixtures.log')
 # Actual frozen codec reload at each activity, not just fixture creation.
 save=Path('/tmp/'+out.name+'-replay.save')
 try:run([out/'probe-host','--host','--replay',save],out/'replay_host.log');shutil.copy2(save,out/'replay_host.save')
 finally:
  if save.exists():save.unlink()
 for fixture in sorted(fixtures.glob('*.save')):
  if fixture.stem=='completed':continue
  run([out/'probe-host','--host','--scene',fixture],out/(fixture.stem+'_host.log'))
  meta=json.loads(fixture.with_suffix('.json').read_text());meta['commands_last']=meta['commands'];meta['commands']=fixture.with_suffix('.commands').stat().st_size//32;meta['captured_frames']=3
  fixture.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
  run(['python3',REPO/'games/luma3d/candidates/terrain_surface_r1/render_preview.py',fixture.with_suffix('')],out/(fixture.stem+'_oracle.log'))
 record=dict(passed=True,hardware=False,build_manifest_sha256=sha(BUILD/'manifest.json'),commands=commands,source_files={str(x.relative_to(REPO)):sha(x) for x in sources if x.is_relative_to(REPO)},route_original_sha256=sha(ROUTE),scope='Fixed three-frame fixtures and legal-input accelerated replay; no real-time FPS claim')
 record['files']={str(x.relative_to(out)):{'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(out.rglob('*')) if x.is_file()}
 (out/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(out,flush=True)
if __name__=='__main__':main()
