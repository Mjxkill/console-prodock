#!/usr/bin/env python3
"""Paired diagnostics: exact GM1 versus the publication-cache candidate."""
import argparse,difflib,hashlib,json,subprocess
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
BUILDS={'baseline':R/'games/luma3d/build/maze_events_20261027_r4','candidate':R/'games/luma3d/build/maze_publish_cache_20261027_r3'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);records=[]
for variant,b in BUILDS.items():
 s=b/'source';g=s/'games/luma3d';m=json.loads((b/'manifest.json').read_text())
 for name,r in m['files'].items():assert sha(s/name)==r['sha256']
 original=(g/'src/maze_render.c').read_text();modified='#include "probe_mesh.h"\n'+original
 assert modified.count('unsigned start=b->offset;')==1
 modified=modified.replace('unsigned start=b->offset;','double probe_start=l3_probe_time();unsigned start=b->offset;')
 assert modified.count('b->nv=b->nf=0;return 1;')==1
 modified=modified.replace('b->nv=b->nf=0;return 1;','l3_probe_mesh_publish(start,b->offset-start,l3_probe_time()-probe_start);b->nv=b->nf=0;return 1;')
 mesh=o/(variant+'_maze_render.c');mesh.write_text(modified)
 (o/(variant+'_mesh.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True))))
 sources=[C/'cache_probe.c',mesh,*[q for q in sorted((g/'src').glob('*.c')) if q.name not in ('main.c','maze_render.c')],*sorted((g/'minigames').glob('*.c')),g/'world/data.c',s/'fw_console/gpu_v1.c',s/'fw_console/gpu_geometry.c']
 flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffp-contract=off','-ffunction-sections','-fdata-sections','-DL3_MOTION_CANDIDATE']+(['-DL3_CACHE_CANDIDATE'] if variant=='candidate' else [])
 for target,cc,extra in [('host','cc',[]),('riscv',str(R/'linux/build/userbin/riscv32-prodock-linux-gcc'),['-static'])]:
  elf=o/(variant+'-'+target);cmd=[cc,*flags,*extra,*['-I'+str(q) for q in [C,g/'include',g/'minigames',g/'world',s/'fw_console',s/'linux/drivers']],*map(str,sources),'-Wl,--gc-sections','-lm','-o',str(elf)]
  q=subprocess.run(cmd,capture_output=True);(o/(variant+'_'+target+'_compile.log')).write_bytes(q.stdout+q.stderr);q.check_returncode()
  records.append(dict(variant=variant,target=target,command=cmd,elf_sha256=sha(elf),source_manifest_sha256=sha(b/'manifest.json'),sources={str(q.relative_to(R)):sha(q) for q in sources}))
(o/'manifest.json').write_text(json.dumps(dict(candidate=True,hardware_tested=False,records=records,probe_sha256=sha(C/'cache_probe.c'),scope='Same GM1 scheduler/game; only publication cache differs. Diagnostic adds copy counters/exploration/restart/back fixtures. Full progress codec compared.'),indent=2)+'\n');print('CACHE_PROBES_BUILT')
