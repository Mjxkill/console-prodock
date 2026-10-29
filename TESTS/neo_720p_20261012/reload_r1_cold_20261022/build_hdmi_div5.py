#!/usr/bin/env python3
"""HDMI-only alternative: DHCE fast clock and local CLKDIV /5 pixel clock.

Uses the vendor CLKDIV ratio recommended by UG304 OSER10; no board access.
Same PLL VCO, output pixel frequency, encoder, reset pipeline, raster and pins.
The pixel clock now derives from FCLK instead of a separate PLL output.
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
out=HERE/'hdmi_bars_dhce_div5'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((parent/'result.json').read_text())
assert record['complete']
for n,h in record['source_sha256'].items():assert sha(parent/n)==h
contract=before_build('neo',candidate=True)
out.mkdir(exist_ok=False);record_build(out,contract)
for n in record['source_sha256']:
    if n!='build.tcl':shutil.copy2(parent/n,out/n)
rtl=(out/'probe.v').read_text()
old="DCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CE(1'b1));"
assert rtl.count(old)==1 and rtl.count('.clkout2(pixel_clk)')==1
rtl=rtl.replace('.clkout2(pixel_clk)','.clkout2()')
rtl=rtl.replace(".enclk2(1'b1)",".enclk2(1'b0)")
rtl=rtl.replace(old,"""DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));
CLKDIV u_video_div(.CLKOUT(pixel_clk),.HCLKIN(clk5x),.RESETN(pixel_lock),.CALIB(1'b0));
defparam u_video_div.DIV_MODE = "5";""")
(out/'probe.v').write_text(rtl)
sdc=(out/'probe.sdc').read_text()
old='create_generated_clock -name vid_pclk -source [get_ports {clk}] -multiply_by 119 -divide_by 80 [get_pins {u_video_pll/PLL_inst/CLKOUT2}]'
new='create_generated_clock -name vid_pclk -source [get_pins {u_video_pll/PLL_inst/CLKOUT0}] -divide_by 5 [get_pins {u_video_div/CLKOUT}]'
assert sdc.count(old)==1
(out/'probe.sdc').write_text(sdc.replace(old,new,1))
(out/'build.tcl').write_text((parent/'build.tcl').read_text().replace(str(parent),str(out)))
result=dict(parent=str(parent),scope=__doc__,hardware_access=False,
    source_sha256={n:sha(out/n) for n in record['source_sha256']})
with (out/'build.log').open('w') as log:
    done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
                        stdout=log,stderr=log,timeout=600)
log=(out/'build.log').read_text()
result.update(returncode=done.returncode,complete=done.returncode==0 and
              'Bitstream generation completed' in log and not re.search(r'^ERROR',log,re.M))
for n in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
    if (out/n).exists():result[n+'_sha256']=sha(out/n)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
