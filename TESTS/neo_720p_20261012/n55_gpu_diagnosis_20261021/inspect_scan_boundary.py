#!/usr/bin/env python3
"""Isolated routed R1 scanout/queue/arbiter functional simulation with official primitives.
No SDF. DDR endpoint accepts queue words, returns patterned bursts after 16 cycles.
Raster counters are placed at vblank for first-line testing; not a full frame test.
CPU requesters held idle; bus bridge, DDR PHY, physical delays and metastability not modeled.
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
            if name.startswith(('u_gpu/','u_scan_queue/','u_soc/g_ddr.u_ddr/u_gpu_arb/')):
                raise ValueError('Unsupported primitive inside GPU/debug '+name+' '+kind)
            continue # Unrelated hard/IO blocks may have other libraries.
        if set(pins)-set(directions[kind]):raise ValueError('Unknown primitive pins '+name+' '+kind+' '+str(set(pins)-set(directions[kind])))
        ins=set();outs=set()
        for pin,expression in pins.items():
            (outs if directions[kind][pin]=='output' else ins).update(atoms(expression))
        cells[name]=dict(kind=kind,inputs=ins,outputs=outs,text=match[0])
        for net in outs:drivers[net].add(name)
    cpu_gate=cells['u_soc/g_ddr.u_ddr/u_gpu_arb/n823_s1']
    if cpu_gate['kind']!='LUT4' or set(cpu_gate['inputs'])!={
        'u_soc/g_ddr.u_ddr/w_wr_data_0_3','u_soc/g_ddr.u_ddr/issue_4',
        'u_soc/g_ddr.u_ddr/push_4','u_soc/g_ddr.u_ddr/push_7'}:
        raise ValueError('CPU idle boundary gate changed')
    if not re.search(r'defparam\s+\\u_soc/g_ddr\.u_ddr/u_gpu_arb/n823_s1\s+\.INIT=16\'hFE00;', raw):
        raise ValueError('CPU request truth table changed')
    assignments={'gpu_clk':'clock_model','vid_hclk':'hclk','pixel_clk':'pclk',
        'vid_hrstn':'resetn','bus_hwrite':'hwrite','bus_hwdata[31:0]':'hwdata',
        'bus_htrans[1]':'htrans','bus_haddr[14:0]':'haddr','ddr_init':'resetn',
        'm_rd_data_valid':'response_valid','blit_rd_data[255:0]':'response_data',
        r'\u_soc/g_ddr.u_ddr/full ':'~ui_ready',
        r'\u_soc/g_ddr.u_ddr/m_wr_data_rdy ':"1'b1",
        # Decoded CPU request terms are all idle. n823_s1 INIT=FE00 proves
        # c_en stays zero for either push_7 (ready) value; no arbiter state is forced.
        r'\u_soc/g_ddr.u_ddr/w_wr_data_0_3 ':"1'b0",
        r'\u_soc/g_ddr.u_ddr/issue_4 ':"1'b0",
        r'\u_soc/g_ddr.u_ddr/push_4 ':"1'b0",
        r'\u_soc/g_ddr.u_ddr/push_7 ':"1'b1",
        r'\u_soc/g_ddr.u_ddr/w_cmd [0]':"1'b1",
        r'\u_soc/g_ddr.u_ddr/w_addr [27:3]':"25'b0",
        r'\u_soc/g_ddr.u_ddr/ip_wr_data [127:64]':"64'b0",
        r'\u_soc/g_ddr.u_ddr/w_wr_data_mask [31:0]':"32'b0",
        'v1_pending':"1'b0",'legacy_valid':"1'b0",'n66_8':"1'b0",'v1_tx_write':"1'b0",
        'legacy_addr[27:3]':"25'b0",'v1_tx_addr[27:0]':"28'b0",'gpu_debug_state[99]':"1'b0",
        'legacy_data[255:0]':"256'b0",'v1_tx_data[255:0]':"256'b0",
        'legacy_mask[31:0]':"32'b0",'v1_tx_mask[31:0]':"32'b0",
        'GND':"1'b0",'VCC':"1'b1"}
    boundary=set().union(*(atoms(net) for net in assignments))
    selected={name for name in cells if name.startswith(('u_gpu/','u_scan_queue/','u_soc/g_ddr.u_ddr/u_gpu_arb/'))}
    crossings={}
    for name in selected:
        for net in cells[name]['inputs']-boundary:
            found=drivers.get(net,set())
            if found and not found<=selected:
                crossings.setdefault(net,dict(drivers=sorted(found),loads=[]))['loads'].append(name)
    print(json.dumps(crossings,indent=2))
if __name__=='__main__':main()
