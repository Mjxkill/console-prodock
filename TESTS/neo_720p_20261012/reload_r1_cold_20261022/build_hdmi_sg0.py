#!/usr/bin/env python3
"""Reroute the identical minimal DCE netlist with its buffer forced to SG0."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment

parent=HERE/'hdmi_bars_dce';out=HERE/'hdmi_bars_dce_sg0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((parent/'result.json').read_text())
assert record['complete']
for n,h in record['source_sha256'].items():assert sha(parent/n)==h
contract=before_build('neo',candidate=True)
out.mkdir(exist_ok=False);record_build(out,contract)
for n in record['source_sha256']:
    if n!='build.tcl':shutil.copy2(parent/n,out/n)
shutil.copy2(parent/'impl/gwsynthesis/probe.vg',out/'probe.vg')
text=(out/'probe.cst').read_text()
assert 'u_video_fast' not in text
(out/'probe.cst').write_text(text+'INS_LOC "u_video_fast" SG[0];\n')
lines=[l for l in (parent/'build.tcl').read_text().splitlines() if l.startswith(('set_device ','set_option '))]
lines+=['add_file {'+str(out/n)+'}' for n in ['probe.vg','probe.cst','probe.sdc']]+['run pnr']
(out/'build.tcl').write_text('\n'.join(lines)+'\n')
result=dict(parent=str(parent),delta='Only INS_LOC u_video_fast SG[0]',hardware_access=False,
    source_sha256={n:sha(out/n) for n in ['probe.vg','probe.v','probe.cst','probe.sdc','build.tcl']})
with (out/'build.log').open('w') as log:
    done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
                        stdout=log,stderr=log,timeout=600)
text=(out/'build.log').read_text()
result.update(returncode=done.returncode,complete=done.returncode==0 and
              'Bitstream generation completed' in text and not re.search(r'^ERROR',text,re.M))
for n in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
    if (out/n).exists():result[n+'_sha256']=sha(out/n)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
