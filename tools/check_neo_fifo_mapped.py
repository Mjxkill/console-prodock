#!/usr/bin/env python3
"""Compare both frozen AHB DDR FIFO netlists, RTL, and an independent queue.

Official Gowin functional models; no SDF or metastability model. Not a
substitute for timing analysis and the repeated-read hardware experiment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from gowin_toolchain import PRIMITIVES

ROOT=Path(__file__).resolve().parents[1]


def module(text,name):
    found=re.findall(r'^module '+re.escape(name)+r'\b.*?^endmodule[^\n]*',text,re.M|re.S)
    if len(found)!=1: raise ValueError('Missing/ambiguous module '+name)
    return found[0]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,scope=__doc__,sources={},cases=[])
    def read(path):
        raw=path.read_bytes();result['sources'][str(path)]=hashlib.sha256(raw).hexdigest()
        return raw.decode()
    mapped=[]
    for prefix,build in [('baseline',a.baseline),('candidate',a.candidate)]:
        text=read(build/'impl/gwsynthesis/console_neo.vg')
        bridge=module(text,'ahb_ddr_cdc')
        for old,new in [('u_requests','request'),('u_responses','response')]:
            kind=re.findall(r'^\s*(\S+)\s+'+old+r'\s*\(',bridge,re.M)
            if len(kind)!=1: raise ValueError('Unknown bridge instance '+old)
            body=module(text,kind[0])
            body=re.sub(r'^module '+re.escape(kind[0])+r'\b','module '+prefix+'_'+new,body,count=1)
            mapped.append(body)
    (out/'mapped.v').write_text('\n'.join(mapped)+'\n')
    primitive_text=read(PRIMITIVES)
    names=set(re.findall(r'^module (\w+)',primitive_text,re.M))
    needed=set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(', '\n'.join(mapped),re.M)) & names
    needed.add('GSR')
    while True:
        dependencies=set()
        for name in needed:
            dependencies.update(re.findall(r'^\s*(\w+)\s+\w+\s*\(',module(primitive_text,name),re.M))
        expanded=needed | (dependencies & names)
        if expanded==needed: break
        needed=expanded
    prim='`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',primitive_text,re.M|re.S))+'\n'
    prim+='\n'.join(module(primitive_text,n) for n in sorted(needed))
    (out/'primitives.v').write_text(prim)
    for name,source in [('rtl.v','tang/rtl/board/ddr_dcfifo.v'),('tb.sv','TESTS/rtl/neo_fifo_mapped_tb.sv')]:
        (out/name).write_text(read(ROOT/source))
    compiler=Path(shutil.which('iverilog') or '/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog').resolve(strict=True)
    library=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    flags=['-B',str(library)] if library.is_dir() else []
    try:
        with (out/'compile.log').open('w') as log:
            subprocess.run([str(compiler),*flags,'-g2012','-s','tb','-o',str(out/'sim.vvp')]+
                [str(out/n) for n in ('tb.sv','rtl.v','mapped.v','primitives.v')],
                stdout=log,stderr=log,check=True,timeout=60)
        # Include the Neo DDR-400 CPU path (50/100 MHz), drifting edges,
        # and the peripheral-bus ratio (80/100 MHz) as extra stress coverage.
        cases=[(10,6.667,3.127),(10.02,6.658,.237),(4,4.016064,.213),
               (10,5,0),(10,5,3.127),(10.02,4.995,.237),
               (9.98,5.005,4.137),(6.25,5,0),(6.25,5,2.713)]
        for i,(hp,up,phase) in enumerate(cases):
            run=subprocess.run([str(compiler.parent/'vvp'),str(out/'sim.vvp'),
                                f'+hp={hp}',f'+up={up}',f'+phase={phase}'],
                               capture_output=True,text=True,timeout=180)
            log=run.stdout+run.stderr;(out/f'case{i}.log').write_text(log)
            passed=run.returncode==0 and 'PASS hp=' in log
            result['cases'].append(dict(hclk_mhz=500/hp,ui_clk_mhz=500/up,phase_ns=phase,passed=passed))
            print(log.strip(),flush=True)
            if not passed: raise RuntimeError('Mapped FIFO comparison failed')
        result['passed']=True
    finally:
        result['primitive_types']=sorted(needed)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    # Do not retain copies of the vendor library or netlist extracts in the
    # evidence directory. Hashes, bench and complete output remain available.
    for name in ('mapped.v','primitives.v','sim.vvp'): (out/name).unlink()


if __name__=='__main__': main()
