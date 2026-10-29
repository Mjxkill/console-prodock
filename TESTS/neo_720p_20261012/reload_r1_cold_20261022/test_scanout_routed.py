#!/usr/bin/env python3
"""Isolated routed R1 scanout/queue functional simulation with official primitives.
No SDF. DDR endpoint accepts queue words, returns patterned bursts after 16 cycles.
Raster counters are placed at vblank for first-line testing; not a full frame test.
CPU, bus bridge, DDR arbiter/PHY, physical delays and metastability not modeled.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import PRIMITIVES


def canonical(name):
    return name.removeprefix('\\')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    source=a.build/'impl/pnr/console_neo.vo'
    raw=source.read_text()
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    if re.search(r'^assign\b',raw,re.M):raise ValueError('Unhandled routed assign statement')
    wires=re.findall(r'^wire (?:\[(\d+):(\d+)\]\s*)?(\\\S+|\w+)\s*;',raw,re.M)
    widths={canonical(name):(int(hi),int(lo)) if hi else None for hi,lo,name in wires}
    def atoms(expression):
        expression=re.sub(r"\d+'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_]+",'',expression)
        result=set()
        for name,hi,lo in re.findall(r'(\\\S+|[A-Za-z_]\w*)(?:\s*\[(\d+)(?::(\d+))?\])?',expression):
            name=canonical(name)
            if name not in widths:raise ValueError('Undeclared net '+name)
            span=(int(hi),int(lo or hi)) if hi else widths[name]
            result.update([name] if span is None else [f'{name}[{i}]' for i in range(min(span),max(span)+1)])
        return result
    primitives={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',PRIMITIVES.read_text(),re.M|re.S)}
    directions={}
    for kind,body in primitives.items():
        body=re.sub(r'/\*.*?\*/|//[^\n]*','',body,flags=re.S)
        pins={}
        for direction,names in re.findall(r'\b(input|output|inout)\s+([^;]+);',body):
            names=re.sub(r'\[[^]]+\]','',names)
            names=re.sub(r'\b(reg|wire|signed|unsigned)\b','',names)
            pins.update({name.strip():direction for name in names.split(',')})
        directions[kind]=pins
    cells={};drivers=collections.defaultdict(set)
    for match in re.finditer(r'^(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);',raw,re.M|re.S):
        kind,name,body=match.groups()
        if kind=='module':continue
        name=canonical(name)
        pins={pin:value for pin,value in re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)}
        if kind not in directions:
            if name.startswith(('u_gpu/','u_scan_queue/')):
                raise ValueError('Unsupported primitive inside GPU/debug '+name+' '+kind)
            continue # Unrelated hard/IO blocks may have other libraries.
        if set(pins)-set(directions[kind]):raise ValueError('Unknown primitive pins '+name+' '+kind+' '+str(set(pins)-set(directions[kind])))
        ins=set();outs=set()
        for pin,expression in pins.items():
            (outs if directions[kind][pin]=='output' else ins).update(atoms(expression))
        cells[name]=dict(kind=kind,inputs=ins,outputs=outs,text=match[0])
        for net in outs:drivers[net].add(name)
    assignments={'gpu_clk':'clock_model','vid_hclk':'hclk','pixel_clk':'pclk',
        'vid_hrstn':'resetn','bus_hwrite':'hwrite','bus_hwdata[31:0]':'hwdata',
        'bus_htrans[1]':'htrans','bus_haddr[14:0]':'haddr','ddr_init':'resetn',
        'gpu_data_valid':'response_valid','blit_rd_data[255:0]':'response_data',
        'scan_count[1:0]':"2'b0",'GND':"1'b0",'VCC':"1'b1"}
    boundary=set().union(*(atoms(net) for net in assignments))
    selected={name for name in cells if name.startswith(('u_gpu/','u_scan_queue/'))}
    original=set(selected);pending=list(selected)
    while pending:
        name=pending.pop()
        for net in cells[name]['inputs']-boundary:
            found=drivers.get(net,set())
            if len(found)!=1:raise ValueError(f'Input {net} of {name}: drivers={found}')
            driver=next(iter(found))
            if driver not in selected:selected.add(driver);pending.append(driver)
    for name in selected:
        if cells[name]['outputs']&boundary:raise ValueError('Retained cell drives bench boundary '+name)
    params=collections.defaultdict(list)
    for m in re.finditer(r'^defparam\s+(\\\S+|\w+)\s*\.\w+\s*=\s*[^;]+;',raw,re.M):
        params[canonical(m[1])].append(m[0])
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    wrapper='''
`timescale 1ns/1ps
module mapped_gpu(input clock_model,hclk,pclk,resetn,hwrite,htrans,response_valid,
input [14:0] haddr,input [31:0] hwdata,input [255:0] response_data,
output request_valid_out,output [27:0] request_address,output ack,output pending,output mem_up);
'''
    wrapper+='\n'.join(re.findall(r'^wire [^;]+;',raw,re.M))+'\n'
    wrapper+='\n'.join(f'assign {net}={value};' for net,value in assignments.items())+'\n'
    wrapper+='\n'.join(cells[name]['text']+'\n'+'\n'.join(params[name]) for name in sorted(selected))+'\n'
    wrapper+=r'''assign request_valid_out=nonempty;assign request_address=gpu_addr;
assign ack=\u_gpu/acknowledge ;assign pending=\u_gpu/line_pending ;assign mem_up=\u_gpu/mrst [1];
endmodule
'''
    # The escaped identifiers above are copied directly from the routed nets.
    mapped=out/'routed.v';mapped.write_text(wrapper)
    bench=out/'tb.sv';bench.write_text((HERE/'scanout_routed_tb.sv').read_text())
    base=Path('/tmp/console-usb-sim-tools/extracted/usr')
    compile_cmd=[str(base/'bin/iverilog'),'-B',str(base/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),str(bench),str(mapped),str(PRIMITIVES)]
    sim_cmd=[str(base/'bin/vvp'),str(out/'sim.vvp')]
    result=dict(passed=False,scope=__doc__,source_netlist_sha256=sha(source),
        total_cells=len(selected),gpu_debug_cells=len(original),dependency_cells=sorted(selected-original),
        primitive_counts=dict(collections.Counter(cells[n]['kind'] for n in selected)),
        boundary_assignments=assignments,source_instances_and_defparams_unchanged=True,
        sha256={str(f):sha(f) for f in (Path(__file__),source,mapped,bench,PRIMITIVES)},
        compile_command=compile_cmd,simulation_command=sim_cmd)
    try:
        for command,logname,seconds in [(compile_cmd,'compile.log',180),(sim_cmd,'simulation.log',600)]:
            with (out/logname).open('w') as log:subprocess.run(command,stdout=log,stderr=log,check=True,timeout=seconds)
        result['passed']='PASS routed scanout first line' in (out/'simulation.log').read_text()
    finally:(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print((out/'simulation.log').read_text())
    if not result['passed']:raise SystemExit('Routed functional GPU test failed')


if __name__=='__main__':main()
