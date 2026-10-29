#!/usr/bin/env python3
"""Run authored room witnesses through real inputs without changing campaign.json."""
import argparse,importlib.util,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--exit-world',type=int,required=True);p.add_argument('--preview',action='store_true');p.add_argument('--preview-only',action='store_true',help='Rebuild the view only; does not rerun or claim a new input validation');args=p.parse_args();manifest=args.manifest.resolve();data=json.loads(manifest.read_text());out=root/'build'/('validate_'+manifest.parent.name);out.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('assets',root/'tools/build_assets.py');assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
worlds=assets.read_worlds();base=data['base_index'];assert len(worlds)==base or len(worlds)>=base+len(data['worlds'])
for offset,name in enumerate(data['worlds']):
 w=json.loads((root/'content'/name).read_text());w['rows']=w['terrain']['rows'];assert len(w['entities'])<=64;assets.unique_ids([e['id'] for e in w['entities']],w['id'])
 if len(worlds)<base+len(data['worlds']):worlds.append(w)
 else:assert worlds[base+offset]['id']==w['id']
assets.unique_ids([w['id'] for w in worlds],'candidate worlds');assets.OUT=out
art_names=list(assets.ART)+sorted({e.get('art',e['kind']) for w in worlds for e in w['entities']}-set(assets.ART));assets.compile_worlds(worlds,art_names)
subprocess.run(['python3',str(root/'tools/build_witness.py'),'--source',str(manifest.parent/'solutions.json'),'--out',str(out/'puzzle_witness.h')],check=True)
command=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(root/'include'),'-I'+str(out),str(root/'src/game.c'),str(root/'src/missions.c'),str(root/'src/light.c'),str(root/'src/save.c'),str(out/'world.c'),str(root/'tests/play_candidate.c'),'-lm','-o',str(out/'play')]
if not args.preview_only:
 subprocess.run(command,check=True);result=subprocess.run([str(out/'play'),str(data['base_index']),str(data['final_world']),str(args.exit_world)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/'runtime.log').write_text(result.stdout);print(result.stdout,end='')
 if result.returncode:raise SystemExit(result.returncode)
if args.preview or args.preview_only:
 preview=out/'indexed';assets.read_worlds=lambda:worlds;sys.argv=['build_assets.py','--indexed','--out',str(preview)];assets.main()
 sources=['src/game.c','src/missions.c','src/light.c','src/save.c','src/video.c','src/main.c','src/host_input.c','audio/luma_audio.c']
 flags=subprocess.check_output(['pkg-config','--cflags','--libs','sdl2'],text=True).split()
 command=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DLUMA_HOST','-I'+str(root/'include'),'-I'+str(preview),'-I'+str(root/'audio'),'-I'+str(root.parents[1]/'linux/drivers'),'-I'+str(root.parents[1]/'linux/userspace')]+[str(root/s) for s in sources]+[str(preview/'world.c'),'-lm',*flags,'-o',str(preview/'luma')]
 subprocess.run(command,check=True);print('Candidate preview:',preview/'luma','--assets',preview/'luma.pak','--world',data['base_index'],'--no-save')
