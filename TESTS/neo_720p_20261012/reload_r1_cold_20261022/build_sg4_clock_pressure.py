#!/usr/bin/env python3
"""Allocation-only SG4 test with the eight-clock model; never program it.

The old model uses counter loads rather than USB/DDR controllers, and its
bus/GPU surrogate frequencies differ from the console. Only clock-resource
allocation is examined here; this is not functional or timing qualification.
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

base=HERE.parent/'hdmi_clock_pressure_sites_20261017'
parent=base/'pressure_sg8'
out=HERE/'clock_pressure_sg4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=next(x for x in json.loads((base/'result.json').read_text())['cases'] if x['name']=='pressure_sg8')
assert record['complete']
for n,h in record['inputs'].items():assert sha(parent/n)==h
contract=before_build('neo',candidate=True)
out.mkdir(exist_ok=False);record_build(out,contract)
for n in record['inputs']:
    if n!='build.tcl':shutil.copy2(parent/n,out/n)
shutil.copy2(parent/'impl/gwsynthesis/probe.vg',out/'probe.vg')
text=(out/'probe.cst').read_text()
assert text.count('INS_LOC "u_video_fast" SG[8];')==1
(out/'probe.cst').write_text(text.replace('INS_LOC "u_video_fast" SG[8];','INS_LOC "u_video_fast" SG[4];',1))
lines=[l for l in (parent/'build.tcl').read_text().splitlines() if l.startswith(('set_device ','set_option '))]
lines+=['add_file {'+str(out/n)+'}' for n in ['probe.vg','probe.cst','probe.sdc']]+['run pnr']
(out/'build.tcl').write_text('\n'.join(lines)+'\n')
result=dict(parent=str(parent),scope=__doc__,hardware_access=False,
    source_sha256={n:sha(out/n) for n in ['probe.vg','probe.v','probe.cst','probe.sdc','build.tcl']})
with (out/'build.log').open('w') as log:
    done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),stdout=log,stderr=log,timeout=600)
log=(out/'build.log').read_text()
result.update(returncode=done.returncode,complete=done.returncode==0 and
              'Bitstream generation completed' in log and not re.search(r'^ERROR',log,re.M))
if result['complete']:
    report=out/'impl/pnr/probe.rpt.txt'
    table=re.search(r'6\. Global Clock Signals.*?7\.',report.read_text(),re.S)[0]
    primary=sorted(re.findall(r'^\s*([^|\n]+?)\s*\|\s*PRIMARY\s*\|',table,re.M))
    expected=sorted(['clk_d','gpu_test','sclk','clk48','fclk960','phy_clk','bus_test','pixel_clk'])
    result.update(primary_nets=primary,expected_primary=expected,all_eight_primary=primary==expected,
                  resource_report_sha256=sha(report))
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
