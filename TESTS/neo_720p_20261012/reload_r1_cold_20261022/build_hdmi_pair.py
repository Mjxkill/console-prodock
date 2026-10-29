#!/usr/bin/env python3
"""Build two isolated real-720p bars with DCE or DHCE. No board access."""
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

contract=before_build('neo',candidate=True)
parent=ROOT/'tang/impl/console_neo_n56r1/source/tang/boards/neo'
analyser=Path('/home/michael/logic_analyser_wifi/tang/impl/linux_l31r8_local_20261012/workspace/tang/rtl/video')
for n in ('video_pll.v','hdmi_out.v','svo_tmds.v'):
    if (parent/'vendor'/n).read_bytes()!=(analyser/n).read_bytes():
        raise ValueError('Shared video import differs from frozen L31r8: '+n)
rtl='''module probe(input wire clk, output wire led_n,
output wire tmds_clk_p,tmds_clk_n,output wire [2:0] tmds_d_p,tmds_d_n);
wire pixel_clk,clk5x_raw,clk5x,pixel_lock;
video_pll u_video_pll(.lock(pixel_lock),.clkout0(clk5x_raw),.clkout2(pixel_clk),
 .clkout1(),.clkout3(),.clkout4(),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b1),.enclk3(1'b0),.enclk4(1'b0));
@BUFFER@
reg [2:0] pixel_up=0;
always @(posedge pixel_clk or negedge pixel_lock)
 if(!pixel_lock)pixel_up<=0;else pixel_up<={pixel_up[1:0],1'b1};
wire de,hs,vs,frame;wire [10:0] x;wire [9:0] y;
wire rst=!pixel_up[2];
video_720p timing(.pclk(pixel_clk),.rst(rst),.de(de),.hs(hs),.vs(vs),.x(x),.y(y),.frame(frame));
wire [2:0] band=x<160 ? 7:x<320 ? 6:x<480 ? 5:x<640 ? 4:x<800 ? 3:x<960 ? 2:x<1120 ? 1:0;
wire border=x<8 || x>=1272 || y<8 || y>=712;
wire [7:0] r={8{border || band[2]}},g={8{border || band[1]}},b={8{border || band[0]}};
hdmi_out u_hdmi(.pclk(pixel_clk),.clk5x(clk5x),.rst(rst),.de(de),.hs(hs),.vs(vs),.r(r),.g(g),.b(b),
 .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_d_p(tmds_d_p),.tmds_d_n(tmds_d_n));
assign led_n=!pixel_up[2];
endmodule
'''
cst='IO_LOC "clk" V22; IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE;\n'
cst+='IO_LOC "led_n" V13; IO_PORT "led_n" IO_TYPE=LVCMOS33 DRIVE=4;\n'
cst+='\n'.join(l for l in (parent/'neo.cst').read_text().splitlines() if
                 '"tmds_' in l or '"u_video_pll/' in l or '"pixel_clk"' in l)+'\n'
sdc='\n'.join(l for l in (parent/'neo.sdc').read_text().splitlines() if
                 l.startswith('create_clock -name clk50 ') or
                 l.startswith('create_generated_clock -name vid_'))+'\n'
sdc+='set_clock_latency -source 0 [get_clocks {vid_pclk vid_clk5x}]\n'
sdc+='\n'.join('report_timing -'+kind+' -max_paths 200 -max_common_paths 2' for kind in
                 ['setup','hold','recovery','removal'])+'\n'
for variant,buffer in [('dhce',"DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));"),
                       ('dce',"DCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CE(1'b1));")]:
    out=HERE/('hdmi_bars_'+variant);out.mkdir(exist_ok=False);record_build(out,contract)
    (out/'probe.v').write_text(rtl.replace('@BUFFER@',buffer))
    (out/'probe.cst').write_text(cst)
    (out/'probe.sdc').write_text(sdc)
    for name in ('video_pll.v','hdmi_out.v','svo_tmds.v'):
        shutil.copy2(parent/'vendor'/name,out/name)
    shutil.copy2(analyser/'video_720p.v',out/'video_720p.v')
    files=['probe.v','probe.cst','probe.sdc','video_pll.v','hdmi_out.v','svo_tmds.v','video_720p.v']
    commands=['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
    commands+=['add_file {'+str(out/n)+'}' for n in files]
    commands+=['set_option -top_module probe','set_option -output_base_name probe',
               'set_option -use_cpu_as_gpio 1','set_option -gen_text_timing_rpt 1',
               'set_option -place_option 3','set_option -route_option 2','run all']
    (out/'build.tcl').write_text('\n'.join(commands)+'\n')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    result=dict(hardware_access=False,scope=__doc__,variant=variant,
                source_sha256={n:sha(out/n) for n in files+['build.tcl']})
    print('Building '+variant,flush=True)
    with (out/'build.log').open('w') as log:
        done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
                            stdout=log,stderr=log,timeout=600)
    log=(out/'build.log').read_text()
    result.update(returncode=done.returncode,complete=done.returncode==0 and
                  'Bitstream generation completed' in log and not re.search(r'^ERROR',log,re.M))
    for n in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
        if (out/n).exists():result[n+'_sha256']=sha(out/n)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
