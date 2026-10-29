#!/usr/bin/env python3
"""Measure Gowin max-delay semantics on a tiny isolated two-clock design.

No hardware action or console input change. Artificial source latency makes
it observable whether pin-based bounds include clock insertion/latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gowin_toolchain import IDE, environment

RTL = '''module probe(input wire clk, other, output wire led_n);
(* syn_preserve=1, syn_keep=1 *) reg toggle=0;
(* syn_preserve=1, syn_keep=1 *) reg stage1=0, stage2=0;
always @(posedge other) toggle <= !toggle;
always @(posedge clk) begin stage1<=toggle; stage2<=stage1; end
assign led_n=stage2;
endmodule
'''
CST = '''IO_LOC "clk" V22; IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
IO_LOC "other" D22; IO_PORT "other" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
IO_LOC "led_n" V13; IO_PORT "led_n" IO_TYPE=LVCMOS33 DRIVE=4;
'''


def hdmi_cases(out, mode='hdmi', columns=(177,174,170), selected_sites=None):
    """Inspect both serializer clock edges; these probes are never programmed."""
    repo = Path(__file__).resolve().parents[1]
    board = repo/'tang/boards/neo'
    rtl = '''module probe(input wire clk, reset_async,
        output wire tmds_clk_p,tmds_clk_n,
        output wire [2:0] tmds_d_p,tmds_d_n);
wire pixel_clk,clk5x_raw,clk5x,pixel_lock;
video_pll u_video_pll(.lock(pixel_lock),.clkout0(clk5x_raw),.clkout2(pixel_clk),
 .clkout1(),.clkout3(),.clkout4(),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b1),.enclk3(1'b0),.enclk4(1'b0));
DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));
reg [7:0] data=0;
always @(posedge pixel_clk) data<=data+1'b1;
hdmi_out u_hdmi(.pclk(pixel_clk),.clk5x(clk5x),.rst(reset_async || !pixel_lock),
 .de(1'b1),.hs(1'b0),.vs(1'b0),.r(data),.g(~data),.b(data),
 .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
 .tmds_d_p(tmds_d_p),.tmds_d_n(tmds_d_n));
endmodule
'''
    cst = 'IO_LOC "clk" V22; IO_PORT "clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE;\n'
    cst += 'IO_LOC "reset_async" D22; IO_PORT "reset_async" IO_TYPE=LVCMOS33 PULL_MODE=DOWN;\n'
    cst += '\n'.join(line for line in (board/'neo.cst').read_text().splitlines()
                      if any(key in line for key in ('"tmds_', '"u_hdmi/g_reset',
                                                       '"u_video_pll/', '"pixel_clk"')))+'\n'
    sdc = '\n'.join(line for line in (board/'neo.sdc').read_text().splitlines()
                     if line.startswith('create_clock -name clk50 ') or
                     line.startswith('create_generated_clock -name vid_') or
                     line.startswith('set_false_path -to [get_pins {u_hdmi/'))+'\n'
    reports = '\n'.join('report_timing -'+kind+' -max_paths 200 -max_common_paths 2'
                         for kind in ('setup','hold','recovery','removal'))+'\n'
    records = []
    cases=[('hdmi_original',''), ('hdmi_mcp2',
          'set_multicycle_path -setup -end 2 -from [get_pins {u_hdmi/g_reset*.reset_sync_fall_s1/Q}] '
          '-to [get_pins {u_hdmi/g_ser*.u_ser/RESET}]\n')]
    if mode=='hdmi-clock':cases=[('hdmi_clk5x_primary','')]
    if mode=='hdmi-clock-direct':cases=[('hdmi_direct_primary','')]
    if mode=='hdmi-clock-dce':cases=[('hdmi_dce_primary','')]
    if mode=='hdmi-dce-place':cases=[(f'hdmi_dce_c{col}','') for col in columns]
    if mode=='hdmi-shared-clock':cases=[(f'hdmi_usb_{choice}','') for choice in ('shared4','hdmi8','hdmi12','usb_local')]
    sites={'auto':None,'pg8':'PG[8]','pg9':'PG[9]','pbr3_0':'PBR3[0]','pbr3_4':'PBR3[4]'}
    if mode=='hdmi-dce-sites':cases=[(f'{name}_c{col}','') for name in (selected_sites or sites) for col in columns]
    if mode=='hdmi-clock-pressure':cases=[(name,'') for name in ('pressure_dhce','pressure_pg0','pressure_pg9')]
    if mode=='hdmi-source-latency':cases=[('latency'+str(value),
        f'set_clock_latency -source {value} [get_clocks {{vid_pclk vid_clk5x}}]\n') for value in (0,9)]
    if mode=='hdmi-mcp-clock':cases=[('hdmi_mcp2_clock',
        'set_multicycle_path -setup -end 2 -from [get_clocks {vid_pclk}] -to [get_clocks {vid_clk5x}]\n')]
    for name, extra in cases:
        target=out/name;target.mkdir()
        variant=rtl
        if mode=='hdmi-clock-direct':
            variant=variant.replace("DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));",'assign clk5x=clk5x_raw;')
        with_usb=mode in ('hdmi-shared-clock','hdmi-clock-pressure')
        if mode in ('hdmi-clock-dce','hdmi-dce-place','hdmi-shared-clock','hdmi-dce-sites','hdmi-clock-pressure','hdmi-source-latency') and name!='pressure_dhce':
            variant=variant.replace("DHCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CEN(1'b0));", "DCE u_video_fast(.CLKIN(clk5x_raw),.CLKOUT(clk5x),.CE(1'b1));")
        if with_usb:
            variant=variant.replace('output wire tmds_clk_p', 'output wire led_n,\n        output wire tmds_clk_p')
            variant=variant.replace('wire pixel_clk,', '''wire clk48,phy_clk;
Gowin_PLL_F u_pll_f(.clkout0(clk48),.clkin(clk),.reset(1'b0));
Gowin_PLL_B u_pll_b(.clkout1(phy_clk),.clkin(clk48),.reset(1'b0));
reg [7:0] blink=0;
always @(posedge phy_clk) blink<=blink+1'b1;
assign led_n=blink[7];
wire pixel_clk,''')
        if mode=='hdmi-clock-pressure':
            extra='''wire bus_test,gpu_fast,gpu_test,fclk960,usb_hclk,sclk;
video_pll u_bus_test(.clkout2(bus_test),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b0),.enclk1(1'b0),.enclk2(1'b1),.enclk3(1'b0),.enclk4(1'b0));
video_pll u_gpu_test(.clkout0(gpu_fast),.clkin(clk),.reset(1'b0),
 .icpsel(6'd0),.lpfres(3'd0),.lpfcap(2'd0),
 .enclk0(1'b1),.enclk1(1'b0),.enclk2(1'b0),.enclk3(1'b0),.enclk4(1'b0));
CLKDIV u_gpu_div(.HCLKIN(gpu_fast),.RESETN(1'b1),.CALIB(1'b0),.CLKOUT(gpu_test));
defparam u_gpu_div.DIV_MODE="4";
DHCE u_usb_fast(.CLKIN(fclk960),.CEN(1'b0),.CLKOUT(usb_hclk));
CLKDIV u_usb_div(.HCLKIN(usb_hclk),.RESETN(1'b1),.CALIB(1'b0),.CLKOUT(sclk));
defparam u_usb_div.DIV_MODE="8";
reg [3:0] a=0,b=0,c=0,d=0,e=0;
always @(posedge clk) a<=a+1'b1;
always @(posedge bus_test) b<=b+1'b1;
always @(posedge gpu_test) c<=c+1'b1;
always @(posedge fclk960) d<=d+1'b1;
always @(posedge sclk) e<=e+1'b1;
'''
            variant=variant.replace('wire pixel_clk,',extra+'\nwire pixel_clk,')
            variant=variant.replace('Gowin_PLL_B u_pll_b(.clkout1(phy_clk)',
                                    'Gowin_PLL_B u_pll_b(.clkout0(fclk960),.clkout1(phy_clk)')
            variant=variant.replace('assign led_n=blink[7];','assign led_n=blink[7]^a[3]^b[3]^c[3]^d[3]^e[3];')
        (target/'probe.v').write_text(variant)
        physical=cst
        if mode in ('hdmi-clock','hdmi-clock-direct'):physical+='CLOCK_LOC "clk5x_raw" BUFG[4] = CLK;\n'
        if mode in ('hdmi-clock-dce','hdmi-dce-place','hdmi-shared-clock'):physical+='CLOCK_LOC "clk5x" BUFG[4] = CLK;\n'
        if mode in ('hdmi-dce-place','hdmi-shared-clock','hdmi-dce-sites','hdmi-clock-pressure','hdmi-source-latency'):
            col=int(name.rsplit('c',1)[1]) if mode in ('hdmi-dce-place','hdmi-dce-sites') else 150
            if name in ('pressure_dhce','pressure_pg9'):col=181
            physical,count=re.subn(r'(reset_sync_fall_s1" R\d+C)181',lambda m:m[1]+str(col),physical)
            if count!=3:raise ValueError('Expected three explicit reset driver sites')
        if mode=='hdmi-dce-sites':
            site=sites[name.rsplit('_c',1)[0]]
            if site:physical+=f'INS_LOC "u_video_fast" {site};\n'
        if with_usb:
            physical+='''IO_LOC "led_n" V13; IO_PORT "led_n" IO_TYPE=LVCMOS33 DRIVE=4;
INS_LOC "u_pll_f/PLL_inst" PLL_R[2];
INS_LOC "u_pll_b/PLL_inst" PLL_R[1];
CLOCK_LOC "clk48" BUFG[4] = CLK;
CLOCK_LOC "phy_clk" BUFG[2] = CLK;
'''
            if name.endswith('hdmi8'):physical=physical.replace('"clk5x" BUFG[4]', '"clk5x" BUFG[8]')
            if name.endswith('hdmi12'):physical=physical.replace('"clk5x" BUFG[4]', '"clk5x" BUFG[12]')
            if name.endswith('usb_local'):physical=physical.replace('"clk48" BUFG[4] = CLK', '"clk48" LOCAL_CLOCK')
        if mode=='hdmi-clock-pressure':
            physical+='''INS_LOC "u_bus_test/PLL_inst" PLL_R[0];
INS_LOC "u_gpu_test/PLL_inst" PLL_L[0];
INS_LOC "u_gpu_div" LEFTSIDE[4];
INS_LOC "u_usb_div" RIGHTSIDE[4];
CLOCK_LOC "clk_d" BUFG[0] = CLK;
CLOCK_LOC "bus_test" BUFG[5] = CLK;
CLOCK_LOC "gpu_test" BUFG[6] = CLK;
CLOCK_LOC "fclk960" BUFG[3] = CLK;
CLOCK_LOC "sclk" BUFG[7] = CLK;
'''
            if name!='pressure_dhce':physical+=f'INS_LOC "u_video_fast" PG[{9 if name=="pressure_pg9" else 0}];\n'
        (target/'probe.cst').write_text(physical)
        (target/'probe.sdc').write_text(sdc+extra+reports)
        files=['probe.v','probe.cst','probe.sdc']
        for f in ('video_pll.v','hdmi_out.v','svo_tmds.v'):
            shutil.copy2(board/'vendor'/f,target/f);files.append(f)
        if with_usb:
            for f in ('gowin_pll_f.v','gowin_pll_b.v'):
                shutil.copy2(repo/'tang/rtl/usb'/f,target/f);files.append(f)
            clocks='\n'.join(line for line in (board/'neo.sdc').read_text().splitlines()
                             if line.startswith(('create_generated_clock -name CLK_48M ',
                                                 'create_generated_clock -name PHY_CLKOUT ')))
            (target/'probe.sdc').write_text(sdc+clocks+'\n'+reports)
        if mode=='hdmi-clock-pressure':
            clocks+='''
create_generated_clock -name fclk_960M -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 2 -multiply_by 40 [get_pins {u_pll_b/PLL_inst/CLKOUT0}]
create_clock -name bus_test_clock -period 13.446 [get_pins {u_bus_test/PLL_inst/CLKOUT2}]
create_clock -name gpu_test_clock -period 10.757 [get_pins {u_gpu_div/CLKOUT}]
create_clock -name sclk_clock -period 8.333 [get_pins {u_usb_div/CLKOUT}]
'''
            (target/'probe.sdc').write_text(sdc+clocks+'\n'+reports)
        script=['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
        script+=['add_file {'+str(target/f)+'}' for f in files]
        script+=['set_option -top_module probe','set_option -output_base_name probe',
                 'set_option -use_cpu_as_gpio 1','set_option -gen_text_timing_rpt 1',
                 'set_option -place_option 3','set_option -route_option 2','run all']
        (target/'build.tcl').write_text('\n'.join(script)+'\n')
        print('Starting '+name,flush=True)
        with (target/'build.log').open('w') as log:
            process=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=target,
                env=environment(),stdout=log,stderr=subprocess.STDOUT)
        log=(target/'build.log').read_text()
        complete=process.returncode==0 and 'Bitstream generation completed' in log and not re.search(r'^ERROR',log,re.M)
        records.append(dict(name=name,returncode=process.returncode,complete=complete,
            inputs={f:hashlib.sha256((target/f).read_bytes()).hexdigest() for f in files+['build.tcl']}))
        (out/'result.json').write_text(json.dumps(dict(ide=str(IDE),cases=records,
            scope='HDMI reset edge characterization only. No console constraint change or hardware action.'),indent=2)+'\n')
        print(name+': '+str(complete),flush=True)
        if not complete and mode not in ('hdmi-shared-clock','hdmi-dce-sites','hdmi-clock-pressure'):raise SystemExit('Failed diagnostic build: '+str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--columns', type=int, nargs='+',
                        help='Final reset FF columns for the HDMI DCE placement sweep')
    parser.add_argument('--dce-sites', nargs='+', choices=['auto','pg8','pg9','pbr3_0','pbr3_4'],
                        help='DCE sites to characterize with the requested reset columns')
    parser.add_argument('--suite', choices=['cdc','cdc-compensated','hdmi','hdmi-clock',
        'hdmi-clock-direct','hdmi-clock-dce','hdmi-dce-place','hdmi-mcp-clock','hdmi-shared-clock','hdmi-dce-sites','hdmi-clock-pressure','hdmi-source-latency'], default='cdc')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'driver.py')
    if args.suite.startswith('hdmi'):
        columns=args.columns or ([150] if args.suite=='hdmi-dce-sites' else [177,174,170])
        if any(not 1 <= c <= 181 for c in columns):parser.error('Invalid fabric column')
        hdmi_cases(out, mode=args.suite, columns=columns, selected_sites=args.dce_sites)
        return
    records = []
    cases = [('clocks9', 9, 'clocks', 'source', 8),
             ('pins9', 9, 'pins', 'source', 8), ('pins0', 0, 'pins', 'source', 8)]
    if args.suite == 'cdc-compensated':
        cases = [('source9_bound17',9,'clocks','source',17),
                 ('sink9_bound_minus1',9,'clocks','sink',-1)]
    for name, latency, endpoint, latency_clock, limit in cases:
        target = out / name
        target.mkdir()
        (target/'probe.v').write_text(RTL)
        (target/'probe.cst').write_text(CST)
        bound = (f'set_max_delay {limit} -from [get_clocks {{source}}] -to [get_clocks {{sink}}]'
                 if endpoint == 'clocks' else
                 'set_max_delay 8 -from [get_pins {toggle_s1/Q}] -to [get_pins {stage1_s1/D}]')
        sdc = ('create_clock -name source -period 20 [get_ports {other}]\n'
               'create_clock -name sink -period 20 [get_ports {clk}]\n'
               f'set_clock_latency -source {latency} [get_clocks {{{latency_clock}}}]\n'+bound+'\n'
               'set_false_path -hold -from [get_clocks {source}] -to [get_clocks {sink}]\n'
               'report_timing -setup -max_paths 30 -max_common_paths 1\n'
               'report_timing -hold -max_paths 30 -max_common_paths 1\n')
        (target/'probe.sdc').write_text(sdc)
        script = ['set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0']
        script += ['add_file {'+str(target/f)+'}' for f in ('probe.v','probe.cst','probe.sdc')]
        script += ['set_option -top_module probe', 'set_option -output_base_name probe',
                   'set_option -use_cpu_as_gpio 1', 'set_option -gen_text_timing_rpt 1',
                   'set_option -place_option 3', 'set_option -route_option 2', 'run all']
        (target/'build.tcl').write_text('\n'.join(script)+'\n')
        print('Starting '+name, flush=True)
        with (target/'build.log').open('w') as log:
            process = subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'], cwd=target,
                                     env=environment(), stdout=log, stderr=subprocess.STDOUT)
        text = (target/'build.log').read_text()
        record = dict(name=name, returncode=process.returncode, requested_bound=bound,
                      artificial_latency_ns=latency,
                      latency_clock=latency_clock,
                      inputs={f:hashlib.sha256((target/f).read_bytes()).hexdigest()
                              for f in ('probe.v','probe.cst','probe.sdc','build.tcl')})
        report = target/'impl/pnr/probe.tr'
        record['complete'] = (process.returncode == 0 and report.is_file() and
                              'Bitstream generation completed' in text and
                              not re.search(r'^ERROR',text,re.M))
        if report.is_file():
            tr = report.read_text()
            record['constraints'] = re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',tr,re.M)
            sections = tr.split('3.3.1 Setup Analysis Report')[-1].split('3.3.2 Hold Analysis Report')[0]
            record['paths'] = []
            for block in sections.split('Path Summary:')[1:]:
                fields = {k:v.strip() for k,v in re.findall(
                    r'^(Slack|From|To|Launch Clk|Latch Clk|Data Arrival Time|Data Required Time)\s*:\s*(.+)$',block,re.M)}
                if fields:record['paths'].append(fields)
        records.append(record)
        (out/'result.json').write_text(json.dumps(dict(ide=str(IDE),cases=records,
            scope='Constraint semantics only; not board/console qualification'),indent=2)+'\n')
        print(name+': '+str(record['complete'])+' '+str(record.get('paths',[])),flush=True)
        if not record['complete']:
            raise SystemExit('Failed diagnostic build: '+str(target))


if __name__ == '__main__':
    main()
