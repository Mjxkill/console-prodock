#!/usr/bin/env python3
"""Freeze the already validated optical game and its separate input fixture."""
import argparse,hashlib,json,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];repo=root.parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
base=root/'tests/local/reflections_20261024';proof=json.loads((base/'source_manifest.json').read_text());result=json.loads((base/'result.json').read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for name,entry in result['evidence'].items():assert sha(base/name)==entry['sha256'],name
regions=[f'world_{i:02d}.lz4' for i in [2,22,26,27,35]]
with tarfile.open(base/'indexed_runtime.tar.gz') as archive:
 for name in ['luma-riscv','luma.lz4',*regions,'world.c','assets.h','music.h']:
  member='games/luma_adventure/build/indexed/'+name;blob=archive.extractfile(member).read();assert hashlib.sha256(blob).hexdigest()==proof['files'][member]
  (out/('generated_'+name if name in ['world.c','assets.h','music.h'] else name)).write_bytes(blob)
for name in ['sources.tar.gz','source_manifest.json','result.json']:
 shutil.copyfile(base/name,out/('local_'+name))
shutil.copyfile(root/'tests/hardware/trial_20261024_r5/uart-receiver',out/'uart-receiver')
shutil.copyfile(root/'tools/prodock_scene_trial.py',out/'prodock_scene_trial.py')
shutil.copyfile(root/'build/optics_probe/luma-probe',out/'luma-probe')
shutil.copyfile(root/'tests/prodock_optics_probe.c',out/'prodock_optics_probe.c')
shutil.copyfile(Path(__file__),out/'freeze_optics_trial.py')
inputs={}
for name in ['src/game.c','src/missions.c','src/light.c','src/save.c','src/video.c','include/luma.h','include/video.h','tests/play_input.h','tests/play_dungeon.h','build/indexed/world.c','build/indexed/assets.h']:
 f=root/name;key=str(f.relative_to(repo));assert sha(f)==proof['files'][key],name;inputs[key]=sha(f)
for name in ['puzzle_witness.h','witness_26.json','witness_35.json','first_pc.log','final_pc.log','probe-pc']:
 shutil.copyfile(root/'build/optics_probe'/name,out/name)
for case,tail in [('first','gallery=0 loading_scenes=1 status=0'),('final','gallery=2 loading_scenes=1 status=0')]:
 log=(out/(case+'_pc.log')).read_text();assert 'LUMA_PROBE_PASS case='+case in log and tail in log
runtime=['luma-riscv','luma.lz4',*regions,'luma-probe','uart-receiver','prodock_scene_trial.py']
manifest={'schema':2,'candidate':'R9: exact reflections_20261024 game plus separate functional input probe','base_local_result_sha256':sha(base/'result.json'),'base_local_source_manifest_sha256':sha(base/'source_manifest.json'),'intended_boards':['prodock','neo'],'hardware_validation':'pending','regions':regions,
 'scenarios':[{'name':name,'world':world,'coverage':coverage} for name,world,coverage in [('control_room',22,'R5 room22 control: direct start, automatic motion/archery; no puzzle solution'),('optics_first',26,'First optical room: direct start, automatic motion/archery with initial optical network; no puzzle solution'),('optics_final',35,'Last optical room: direct start, automatic motion/archery with initial optical network; no puzzle solution')]],
 'probes':[{'name':'first_inputs','case':'first','coverage':'Separate executable, real mirror input and first room exit to room27. Direct-start fixture; render every fourth simulation step and every interaction. Not a cadence benchmark.'},{'name':'final_inputs','case':'final','coverage':'Separate executable, last-room mirror/crate solution then real return to chapter3 and gallery both ways. Direct start and previous chapter prerequisites seeded. No full campaign or normal cadence claim.'}],
 'runtime':{name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in runtime},'probe_shared_inputs':inputs,'probe_evidence':{name:sha(out/name) for name in ['prodock_optics_probe.c','puzzle_witness.h','witness_26.json','witness_35.json','first_pc.log','final_pc.log','probe-pc']}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(out);print('UART payload bytes:',sum((out/n).stat().st_size for n in runtime if n not in ['uart-receiver','prodock_scene_trial.py']))
