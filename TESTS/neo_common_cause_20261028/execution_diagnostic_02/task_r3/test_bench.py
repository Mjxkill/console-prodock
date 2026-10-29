#!/usr/bin/env python3
"""Compile exact DUT copies and challenge the proposed bench with faults."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent

def run(argv, timeout=12):
    proc=subprocess.run(argv,cwd=HERE,capture_output=True,text=True,timeout=timeout)
    return proc.returncode,proc.stdout+proc.stderr

def main():
    with tempfile.TemporaryDirectory(prefix='ddr-cross-client-') as temporary:
        binary=str(Path(temporary)/'obj/Vbench')
        rc,log=run(['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
                    '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(Path(temporary)/'obj'),
                    'bench.sv','native_memory.sv','ddr_gpu_arb.v','ddr_ui_adapt.v'],timeout=40)
        if rc: print(log);return 1
        results=[]
        for seed,fault in [(1,0),(8,0),(1,1),(1,2),(1,3)]:
            rc,log=run([binary,f'+seed={seed}',f'+fault={fault}'])
            print(f'CASE seed={seed} fault={fault} returncode={rc}\n{log}')
            if fault==0:
                # Coverage values must be measured at the public interfaces.
                match=re.search(r'PASS cpu=(\d+) scan=(\d+) blit=(\d+) rotations=(\d+) outstanding=(\d+)',log)
                ok=rc==0 and match is not None
                if match:
                    a,b,c,d,e=map(int,match.groups())
                    ok=ok and a>=16 and b>=8 and c>=8 and d==16 and e>=3
            else:
                # A simulation crash is not proof of sensitivity: the bench
                # must identify data/routing mismatch or bounded missing reply.
                ok=rc!=0 and bool(re.search(r'CHECK_FAIL (DATA|ROUTE|TIMEOUT)',log))
            results.append(dict(seed=seed,fault=fault,passed=ok))
        print(json.dumps(dict(passed=all(r['passed'] for r in results),cases=results)))
        return int(not all(r['passed'] for r in results))

if __name__=='__main__':raise SystemExit(main())
