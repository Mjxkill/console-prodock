#!/usr/bin/env python3
"""Test SG4 using the identical HDMI-only synthesis netlist; no hardware.

This isolates another secondary DCE site from the failing SG0 route.
A positive timing report alone still does not qualify the physical HDMI output.
"""
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

parent=HERE/'hdmi_bars_dce'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((parent/'result.json').read_text())
assert record['complete']
for n,h in record['source_sha256'].items():assert sha(parent/n)==h
assert sha(parent/'impl/gwsynthesis/probe.vg')=='b0f208f76083346a9ea6030a8d8d0b74e8969e5c2457bdafbd4543ff5da3b8af'
contract=before_build('neo',candidate=True)
for index in [4]:
    out=HERE/f'hdmi_bars_dce_sg{index}'
    out.mkdir(exist_ok=False);record_build(out,contract)
    for n in record['source_sha256']:
        if n!='build.tcl':shutil.copy2(parent/n,out/n)
    shutil.copy2(parent/'impl/gwsynthesis/probe.vg',out/'probe.vg')
    text=(out/'probe.cst').read_text()
    assert 'u_video_fast' not in text
    (out/'probe.cst').write_text(text+f'INS_LOC "u_video_fast" SG[{index}];\n')
    lines=[l for l in (parent/'build.tcl').read_text().splitlines() if l.startswith(('set_device ','set_option '))]
    lines+=['add_file {'+str(out/n)+'}' for n in ['probe.vg','probe.cst','probe.sdc']]+['run pnr']
    (out/'build.tcl').write_text('\n'.join(lines)+'\n')
    result=dict(parent=str(parent),delta=f'Only INS_LOC u_video_fast SG[{index}]',hardware_access=False,
        source_sha256={n:sha(out/n) for n in ['probe.vg','probe.v','probe.cst','probe.sdc','build.tcl']})
    with (out/'build.log').open('w') as log:
        done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
                            stdout=log,stderr=log,timeout=600)
    text=(out/'build.log').read_text()
    result.update(returncode=done.returncode,complete=done.returncode==0 and
                  'Bitstream generation completed' in text and not re.search(r'^ERROR',text,re.M))
    for n in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
        if (out/n).exists():result[n+'_sha256']=sha(out/n)
    if result['complete']:
        report=(out/'impl/pnr/probe.tr').read_text();margins={}
        for i,k in enumerate(['Setup','Hold','Recovery','Removal'],1):
            table=re.search(r'^3\.1\.'+str(i)+' '+k+r' Paths Table.*?(?=^3\.|\Z)',report,re.M|re.S)[0]
            values=[float(x) for x in re.findall(r'^\s+\d+\s+(-?\d+\.\d+)\s+',table,re.M)]
            margins[k]=min(values) if values else None
        result['timing_minima_ns']=margins
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(site=f'SG[{index}]',complete=result['complete'],
        timing=result.get('timing_minima_ns'))),flush=True)
