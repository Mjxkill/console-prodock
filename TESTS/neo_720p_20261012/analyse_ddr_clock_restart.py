#!/usr/bin/env python3
"""Inspect reset/clock branch delays; this is NOT a loading or STA waiver.

Assumes the official functional CLKDIV /4 model's >= one fast period before
its first output rising edge. Analog macro recovery and metastability are
not modeled. Report both same-corner and deliberately mixed-corner bounds.
Only the direct DDR reset and its FIFO reset-combination branch are covered.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

build, out = map(Path, sys.argv[1:3])
vo = build/'impl/pnr/console_neo.vo'
sdf = build/'impl/pnr/console_neo.sdf'
prefix = 'u_soc/g_ddr.u_ddr/u_ip/gw3_top/'
phy = prefix+'u_ddr_phy_top/'
root = phy+'ddr_rsti_reg_2_s0'
divider = phy+'fclkdiv'
inv = phy+'n809_6_s0'
comb = phy+'u_ddr_phy_wds/u_ddr_phy_reset_gen/if_wrreset_Z_s'
def canonical(net):
    return ''.join(net.replace('\\','').split())
cells = {}
netlist = vo.read_text()
for kind,name,body in re.findall(r'^(\w+)\s+(\\\S+|\w+)\s*\((.*?)\);',netlist,re.M|re.S):
    cells[name.lstrip('\\')] = (kind, {pin:canonical(net) for pin,net in re.findall(r'\.(\w+)\(([^()]*)\)',body)})
def parameter(name, key):
    matches = re.findall(r'^defparam \\'+re.escape(name)+r'\s*\.'+key+r'\s*=\s*([^;]+);',netlist,re.M)
    if len(matches)!=1:raise ValueError('Missing/duplicate parameter '+name+'.'+key)
    return matches[0]
assert parameter(inv,'INIT')=="2'h1"
assert parameter(comb,'INIT')=="4'hE"
assert parameter(divider,'DIV_MODE')=='"4"'
assert cells[divider][1]['CALIB']=='GND'
assert json.loads((build/'source/tang/boards/neo/ddr_variant.json').read_text())['variant']=='neo-ddr6-400-fifo-registers'
assert 'gowin_reg_ddr_rst_' not in netlist, 'Replicated DDR reset needs a separate path reconstruction'
assert cells[root][1]['Q']==prefix+'ddr_rst'
assert cells[inv][1]['I0']==cells[root][1]['Q']
assert cells[divider][1]['RESETN']==cells[inv][1]['F']
assert cells[comb][1]['I0']==cells[root][1]['Q']
assert cells[divider][1]['CLKOUT']=='gpu_clk'
text = sdf.read_text().replace('\\','')
arcs = {}
sources = {root+'/Q',inv+'/F',comb+'/F',divider+'/CLKOUT'}
for source,target,values in re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([-\d.:]+)\)\)',text):
    if source in sources:
        arcs[source,target]=list(map(float,values.split(':')))
blocks = {}
for block in text.split('\n  (CELL\n')[1:]:
    name = re.search(r'\(INSTANCE (\S+)\)',block)
    if name and (name[1] in (inv,comb) or name[1].startswith(prefix)):
        blocks[name[1]]=block
def logic(name):
    return list(map(float,re.search(r'\(IOPATH I0 F \(([-\d.:]+)\)\)',blocks[name])[1].split(':')))
clock_release = [sum(values[i] for values in (arcs[root+'/Q',inv+'/I0'],logic(inv),arcs[inv+'/F',divider+'/RESETN'])) for i in range(3)]
comb_delay = [arcs[root+'/Q',comb+'/I0'][i]+logic(comb)[i] for i in range(3)]
paths=[]
for name,(kind,pins) in cells.items():
    if not name.startswith(prefix) or kind!='DFFCE' or pins.get('CLK')!='gpu_clk':continue
    clear=pins.get('CLEAR')
    if clear==cells[root][1]['Q']:
        data=arcs[root+'/Q',name+'/CLEAR']
    elif clear==cells[comb][1]['F']:
        data=[comb_delay[i]+arcs[comb+'/F',name+'/CLEAR'][i] for i in range(3)]
    else:continue
    recovery=list(map(float,re.search(r'\(RECOVERY \(negedge CLEAR\) \(posedge CLK\) \(([-\d.:]+)\)\)',blocks[name])[1].split(':')))
    clock=[clock_release[i]+2.5+arcs[divider+'/CLKOUT',name+'/CLK'][i] for i in range(3)]
    same=[round(clock[i]-data[i]-recovery[i]-.035,3) for i in range(3)]
    mixed=round(min(clock)-max(data)-max(recovery)-.035,3)
    paths.append(dict(cell=name,reset_delay_ns=data,first_clock_lower_bound_ns=clock,same_corner_margin_ns=same,mixed_corner_margin_ns=mixed))
if not paths:raise ValueError('No eligible reset paths')
result=dict(scope=__doc__,build=str(build),sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (vo,sdf)},
            count=len(paths),clock_release_path_ns=clock_release,
            minimum_same_corner_ns=[min(p['same_corner_margin_ns'][i] for p in paths) for i in range(3)],
            minimum_mixed_corner_ns=min(p['mixed_corner_margin_ns'] for p in paths),
            worst_same_corner=sorted(paths,key=lambda p:min(p['same_corner_margin_ns']))[:5],
            worst_mixed_corner=sorted(paths,key=lambda p:p['mixed_corner_margin_ns'])[:5])
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if not k.startswith('worst')},indent=2))
