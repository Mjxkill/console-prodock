#!/usr/bin/env python3
"""Exercise the synthesized startup sequencer using official functional models.

No SDF or metastability model; routed recovery/removal must also pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from check_neo_fifo_mapped import module
from gowin_toolchain import PRIMITIVES


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    net=a.build/'impl/gwsynthesis/console_neo.vg'
    tb=ROOT/'TESTS/rtl/neo_ddr_startup_tb.sv'
    result=dict(passed=False,scope=__doc__,cases=[],sources={
        str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (net,tb,PRIMITIVES)})
    try:
        text=module(net.read_text(),'neo_ddr_startup')
        inputs=set(re.findall(r'^input (?:\[[^]]+\] )?(\w+);',text,re.M))
        outputs=set(re.findall(r'^output (?:\[[^]]+\] )?(\w+);',text,re.M))
        if inputs!={'clk_d','vid_hclk','ddr_init','ae350_rst_sync','soc_dbg'}:
            raise ValueError('Unknown mapped startup inputs: '+str(inputs))
        cpu=outputs-{'ddr_controller_resetn'}
        if len(cpu)!=1 or not next(iter(cpu)).startswith('soc_dbg'):
            raise ValueError('Unknown mapped startup outputs')
        body=text.replace('module neo_ddr_startup (','module mapped_ddr_startup (',1)
        body+='''
module neo_ddr_startup(input ref_clk,resetn,cpu_clk,pll_locked,calib_complete,
                       output ip_resetn,cpu_resetn);
    mapped_ddr_startup dut(.clk_d(ref_clk),.vid_hclk(cpu_clk),
      .ddr_init(calib_complete),.ae350_rst_sync(~resetn),.soc_dbg(pll_locked),
      .ddr_controller_resetn(ip_resetn),.'''+next(iter(cpu))+'''(cpu_resetn));
endmodule
'''
        library=PRIMITIVES.read_text()
        names=set(re.findall(r'^module (\w+)',library,re.M))
        needed=(set(re.findall(r'^\s*(\w+)\s+\S+\s*\(',body,re.M)) & names)|{'GSR'}
        while True:
            deps=set()
            for name in needed:deps.update(re.findall(r'^\s*(\w+)\s+\w+\s*\(',module(library,name),re.M))
            expanded=needed|(deps&names)
            if expanded==needed:break
            needed=expanded
        prim='`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',library,re.M|re.S))
        prim+='\n'+'\n'.join(module(library,n) for n in sorted(needed))
        result['primitive_types']=sorted(needed)
        compiler=Path(shutil.which('iverilog') or '/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
        ivlib=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
        with tempfile.TemporaryDirectory() as temporary:
            work=Path(temporary)
            (work/'mapped.v').write_text(body);(work/'primitives.v').write_text(prim)
            flags=['-B',str(ivlib)] if ivlib.is_dir() else []
            with (a.out/'compile.log').open('w') as log:
                subprocess.run([str(compiler),*flags,'-g2012','-DMAPPED','-s','neo_ddr_startup_tb',
                    '-o',str(work/'sim'),str(tb),str(work/'mapped.v'),str(work/'primitives.v')],
                    stdout=log,stderr=log,check=True,timeout=60)
            for half in ('6.25','6.243','6.257','11.731'):
                r=subprocess.run([str(compiler.parent/'vvp'),str(work/'sim'),'+CPU_HALF='+half],
                                 capture_output=True,text=True,timeout=20)
                log=r.stdout+r.stderr;(a.out/('case_'+half+'.log')).write_text(log)
                passed=r.returncode==0 and 'PASS DDR startup' in log
                result['cases'].append(dict(cpu_half_ns=half,passed=passed))
                if not passed:raise RuntimeError('Mapped startup simulation failed: '+log)
        result['passed']=True
    finally:
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
