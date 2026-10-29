#!/usr/bin/env python3
"""Migrate a genuine frozen v4 save and verify old readers reject v5 safely."""
import argparse,hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline-world',type=Path,required=True);p.add_argument('--world',type=int,default=1);a=p.parse_args();out=root/'build'/f'save_upgrade_world{a.world}';out.mkdir(exist_ok=True)
world=a.baseline_world.resolve()
with tarfile.open(world.parent/'sources.tar.gz') as archive:
 previous_save=archive.extractfile('games/luma_adventure/src/save.c').read()
(out/'previous_save.c').write_bytes(previous_save)
base=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(root/'include')]+[str(root/f) for f in ['src/game.c','src/missions.c','src/light.c','tests/upgrade_save.c']]
for name,table,save in [('previous',world,out/'previous_save.c'),('current',root/'build/world.c',root/'src/save.c')]:subprocess.run(base+[str(table),str(save),'-lm','-o',str(out/name)],check=True)
fixture=out/'previous_v4.sav';migrated=out/'current_v5.sav';ids=subprocess.check_output([str(out/'previous'),'write',str(fixture),str(a.world)],text=True).splitlines()
assert int.from_bytes(fixture.read_bytes()[8:12],'little')==4
result=subprocess.check_output([str(out/'current'),'migrate',str(fixture),str(migrated)]+ids,text=True)
blob=migrated.read_bytes();assert int.from_bytes(blob[8:12],'little')==5
rejection=subprocess.check_output([str(out/'previous'),'reject',str(migrated)],text=True);assert migrated.read_bytes()==blob
(out/'result.json').write_text(json.dumps({'baseline_world':str(a.baseline_world),'baseline_save_sha256':hashlib.sha256(previous_save).hexdigest(),'fixture':'synthetic persisted inventory and completed missions; not a gameplay test','old_ids':ids,'result':result.strip(),'downgrade':rejection.strip(),'passed':True},indent=2)+'\n');print(result+rejection,end='')
