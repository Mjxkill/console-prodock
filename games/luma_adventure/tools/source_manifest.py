#!/usr/bin/env python3
"""Hash the isolated game's consumed sources/resources and external ABI inputs."""
import argparse,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];repo=root.parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--build-dir',type=Path,default=root/'build');args=p.parse_args();build=args.build_dir.resolve()
files=[root/'Makefile',root/'project.json',root/'README.txt']
for folder in ['src','include','tools']:
 files.extend(f for f in (root/folder).glob('*') if f.suffix in {'.c','.h','.py'})
files.extend((root/'tests').glob('*.c'));files.extend((root/'tests').glob('*.h'));files.extend((root/'tests').glob('*.py'))
files.extend((root/'content').rglob('*.py'));files.extend((root/'docs').glob('*.txt'))
campaign=json.loads((root/'content/campaign.json').read_text());files += [root/'content/campaign.json',root/'content/campaign_arcs.json',root/'content/dungeons/solutions.json']
world_files=[root/'content'/(w['file'] if isinstance(w,dict) else w) for w in campaign['worlds']];files.extend(world_files);files.extend(f.parent/'solutions.json' for f in world_files if (f.parent/'solutions.json').exists())
for manifest in ['art/atlas.json','art/terrain.json']:
 f=root/manifest;files.append(f);files.append(f.parent/json.loads(f.read_text())['image'])
files += [root/'audio/manifest.json',root/'audio/luma_audio.c',root/'audio/luma_audio.h',repo/'assets/luma/source/hero.png',repo/'assets/luma/source/enemies.png',repo/'linux/drivers/prodock-uapi.h',repo/'linux/drivers/prodock-validate.h',repo/'linux/userspace/neo-gamepad-input.h']
files += [build/'world.c',build/'assets.h',build/'music.h',build/'luma',build/'luma-riscv',build/'luma.pak',build/'luma.lz4']
files.extend(build/f'world_{i:02d}.lz4' for i in range(len(campaign['worlds'])))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
result={'schema':1,'build_dir':str(build.relative_to(repo)),'candidate':True,'intended_boards':['prodock','neo'],'hardware_qualification':{'prodock':'only separately frozen trial candidates; current workspace pending','neo':'pending'},'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'files':{str(f.relative_to(repo)):sha(f) for f in sorted(set(files))},'font':{'path':'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','sha256':sha(Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))}}
args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n');print(f'{len(result["files"])} inputs/runtime artifacts hashed into {args.out}')
