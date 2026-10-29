#!/usr/bin/env python3
"""Functional RTL/mapped observer tests; no hardware or PNR."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=ROOT/'tang/impl/console_neo_n56r15_reset50ms'
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import PRIMITIVES

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mapped',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    files=[HERE/'capture_tb.sv',PARENT/'source/tang/boards/neo/neo_gpu_debug.v']
    flags=[];helper_netlists={}
    if a.mapped:
        helper_paths=[a.mapped/name/(name+'.vg') for name in ('neo_capture_local','neo_capture_bus')]
        helper_netlists={str(p.resolve()):sha(p) for p in helper_paths}
        text='\n'.join(p.read_text() for p in helper_paths)
        text,n=re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);','',text);assert n==2
        (a.out/'mapped.v').write_text(text);files.append(a.out/'mapped.v');flags=['-DMAPPED']
        prim=PRIMITIVES.read_text();mods={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',prim,re.M|re.S)}
        needed={'GSR'}|set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',text,re.M))&mods.keys()
        while True:
            calls=set().union(*(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',mods[n],re.M)) for n in needed))
            expanded=needed|(calls&mods.keys())
            if expanded==needed:break
            needed=expanded
        (a.out/'primitives.v').write_text('`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',prim,re.M|re.S))+'\n'+'\n'.join(mods[n] for n in sorted(needed)))
        files.append(a.out/'primitives.v')
    else:files.extend(HERE/n for n in ('neo_capture_local.v','neo_capture_bus.v'))
    compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    r=dict(passed=False,hardware=False,mapped=bool(a.mapped),helper_netlists=helper_netlists,inputs={str(f):sha(f) for f in [Path(__file__),*files]},
        scope='Functional clocks, capture faults, AHB reuse, mailbox/reset; no SDF or metastability claim')
    try:
        for name,cmd in [('compile',[str(compiler),'-B',str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb',*flags,'-o',str(a.out/'sim.vvp'),*map(str,files)]),('simulation',[str(compiler.parent/'vvp'),str(a.out/'sim.vvp')])]:
            with (a.out/(name+'.log')).open('x') as log:subprocess.run(cmd,stdout=log,stderr=log,check=True,timeout=120)
        m=re.search(r'PASS local capture checks=(\d+)',(a.out/'simulation.log').read_text());assert m
        r.update(passed=True,checks=int(m[1]))
    except Exception as e:r['error']=repr(e)
    finally:
        r['logs']={f.name:sha(f) for f in a.out.glob('*.log')}
        (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
    if not r['passed']:raise SystemExit(1)
if __name__=='__main__':main()
