#!/usr/bin/env python3
"""Simulate the frozen complete N55 GPU command path with official primitives.

Includes mapped AHB registers, dual-clock FIFO, blitter, ownership, geometry,
pixels, CSR CDC and debug snapshot. The AHB master is a bench; the DDR endpoint
is ready/no-response, and EVERY GPU request is forbidden for these commands.
No DDR, CPU, video_bus_stage, SDF, routing or metastability model.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(ROOT/'tools')]
from probe_config import cases
from gowin_toolchain import PRIMITIVES


def instances(text):
    result={}
    for m in re.finditer(r'^[ \t]*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S):
        kind,name,ports=m.groups()
        if kind=='module':continue
        pins={pin:re.sub(r'\s+','',net) for pin,net in re.findall(r'\.(\\\S+|\w+)\s*\(([^()]*)\)',ports)}
        result[name]=dict(kind=kind,pins=pins,text=m[0])
    return result


def ports(text,direction):
    return set(re.findall(r'^'+direction+r' (?:\[[^]]+\]\s*)?(\\\S+|\w+)\s*;',text,re.M))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    net=a.build/'console_neo.vg'
    if not net.exists():net=a.build/'impl/gwsynthesis/console_neo.vg'
    raw=net.read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',raw,re.M|re.S)}
    top=modules['console_neo'];top_cells=instances(top)
    selected=['u_accel','u_gpu_debug']
    for name in selected:
        if top_cells[name]['kind'] not in ('gpu_accel','neo_gpu_debug'):raise ValueError(name)
    closure=set(top_cells[n]['kind'] for n in selected)
    while True:
        more={c['kind'] for name in closure for c in instances(modules[name]).values() if c['kind'] in modules}
        if more<=closure:break
        closure|=more
    # Both modules share exact optimized decode/reset cones. Keep their full
    # original top-level connections instead of substituting decode equations.
    external_inputs=set();driven=set()
    for name in selected:
        cell=top_cells[name]
        external_inputs|={net for pin,net in cell['pins'].items() if pin in ports(modules[cell['kind']],'input')}
        driven|={net for pin,net in cell['pins'].items() if pin in ports(modules[cell['kind']],'output')}
    assignments={'gpu_clk':'clk','vid_hclk':'hclk','vid_hrstn':'resetn','bus_hwrite':'hwrite',
        'bus_hwdata[31:0]':'hwdata','bus_htrans[1]':'htrans','bus_haddr[14:0]':'haddr',
        'b_grant':"1'b1",'m_rd_data_valid':"1'b0",'blit_rd_data[255:0]':"256'bx",
        # These are DDR response-tag outputs. No RD_VALID is supplied. Keeping
        # them unknown detects accidental use rather than assigning a fake tag.
        'n2024_1':"1'bx",'n2023_2':"1'bx",'n8_3':"1'bx"}
    bound=set(assignments)
    bound|={f'bus_haddr[{i}]' for i in range(15)}
    bound|={f'bus_hwdata[{i}]' for i in range(32)}
    missing=external_inputs-driven-bound
    if missing:raise ValueError('Unmodeled mapped boundary inputs: '+str(sorted(missing)))
    wrapper='''module mapped_gpu(input clk,hclk,resetn,hwrite,htrans,
input [14:0] haddr,input [31:0] hwdata,
output [31:0] gpu_read,debug_read,output gpu_ready,debug_ready,
output request_any);
'''
    wrapper+='\n'.join(re.findall(r'^wire [^;]+;',top,re.M))+'\n'
    wrapper+='assign GND=0;assign VCC=1;\n'
    wrapper+='\n'.join(f'assign {net} = {value};' for net,value in assignments.items())+'\n'
    wrapper+='\n'.join(top_cells[n]['text'] for n in selected)+'\n'
    wrapper+='''assign gpu_read=blit_hrdata;assign debug_read=debug_hrdata;
assign gpu_ready=blit_hready;assign debug_ready=!read_wait;
assign request_any=legacy_valid || v1_pending || u_accel.u_v1.fetch_valid ||
    u_accel.u_v1.u_pixels.native_valid || u_accel.u_v1.u_pixels.copy_valid ||
    u_accel.u_v1.u_pixels.cache_valid;
endmodule
'''
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    mapped=out/'mapped.v';mapped.write_text('\n\n'.join(modules[n] for n in sorted(closure))+'\n'+wrapper)
    bench='''`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg hclk=0,clk=0,resetn=0,hwrite=0,htrans=0;
reg [14:0] haddr=0;reg [31:0] hwdata=0;
wire [31:0] gpu_read,debug_read;wire gpu_ready,debug_ready,request_any;
always #6.25 hclk=~hclk;
initial begin #0.371;forever #6.667 clk=~clk;end
mapped_gpu dut(.*);
task write_reg(input [14:0] address,input [31:0] value);
 @(negedge hclk);htrans=1;hwrite=1;haddr=address;
 @(negedge hclk);htrans=0;hwdata=value;
 if(gpu_ready!==1)$fatal(1,"Unexpected configuration backpressure");
 @(negedge hclk);hwdata=0;hwrite=0;
endtask
task read_reg(input [14:0] address,output [31:0] value);
 @(negedge hclk);htrans=1;hwrite=0;haddr=address;
 @(negedge hclk);htrans=0;
 if((address[14:12]==1 ? gpu_ready:debug_ready)!==0)$fatal(1,"Expected read wait");
 @(negedge hclk);
 if((address[14:12]==1 ? gpu_ready:debug_ready)!==1)$fatal(1,"Read did not finish");
 value=address[14:12]==1 ? gpu_read:debug_read;
endtask
integer checks=0;reg [31:0] value;
always @(negedge clk)if(resetn && request_any!==0)$fatal(1,"Unexpected GPU memory request: %b",request_any);
initial begin
 repeat(12)@(negedge hclk);resetn=1;repeat(30)@(negedge hclk);
 read_reg('h1000,value);if(value!==32'h424c5432)$fatal(1,"Wrong GPU ID %h",value);
 read_reg('h5000,value);if(value!==32'h4e474442)$fatal(1,"Wrong debug ID %h",value);
'''
    rejected=geom=0
    for index,case in enumerate(cases(),1):
        rejected+=not case['accepted'];geom+=not case['accepted'] and case['words'][0]>>24>=31
        bench+=f' // {case["name"]}\n'
        bench+=''.join(f" write_reg('h1010,32'h{word:08x});\n" for word in case['words'])
        bench+=' repeat(60)@(negedge hclk);\n'
        for addr,want,label in [(0x1008,index,'fence'),(0x1034,int(rejected),'rejected'),(0x104c,int(geom),'geometry')]:
            bench+=f" read_reg('h{addr:x},value);if(value!==32'd{want})$fatal(1,\"Case {case['name']} {label}: %h expected{want}\",value);\n"
        bench+=' checks++;\n'
        if index%10==0:bench+=' $display("Mapped full GPU checks=%0d",checks);$fflush();\n'
    bench+=''' write_reg('h5004,1);repeat(30)@(negedge hclk);
 read_reg('h5004,value);if(value!==6)$fatal(1,"Mapped snapshot failed %h",value);
 read_reg('h5008,value);if(value!==640)$fatal(1,"Mapped host words %h",value);
 read_reg('h5010,value);if(value!==640)$fatal(1,"Mapped received words %h",value);
 read_reg('h5020,value);if(value!==80)$fatal(1,"Mapped snapshot done %h",value);
 $display("PASS mapped full GPU: 80 configurations, AHB/FIFO/blitter/geometry/pixels/CSR/debug snapshot, zero DMA");$finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
'''
    (out/'tb.sv').write_text(bench)
    base=Path('/tmp/console-usb-sim-tools/extracted/usr')
    compile_cmd=[str(base/'bin/iverilog'),'-B',str(base/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),str(out/'tb.sv'),str(mapped),str(PRIMITIVES)]
    sim_cmd=[str(base/'bin/vvp'),str(out/'sim.vvp')]
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    result=dict(passed=False,scope=__doc__,netlist_sha256=sha(net),modules=sorted(closure),
        boundary_assignments=assignments,cases=cases(),
        sha256={str(f):sha(f) for f in (Path(__file__),net,mapped,out/'tb.sv',PRIMITIVES)},
        compile_command=compile_cmd,simulation_command=sim_cmd)
    try:
        for command,logname,seconds in [(compile_cmd,'compile.log',180),(sim_cmd,'simulation.log',600)]:
            with (out/logname).open('w') as log:
                subprocess.run(command,stdout=log,stderr=log,check=True,timeout=seconds)
        result['passed']='PASS mapped full GPU: 80 configurations' in (out/'simulation.log').read_text()
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print((out/'simulation.log').read_text())
    if not result['passed']:raise SystemExit('Full mapped GPU failed')


if __name__=='__main__':main()
