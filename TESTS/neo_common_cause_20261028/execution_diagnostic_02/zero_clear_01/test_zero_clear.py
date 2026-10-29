#!/usr/bin/env python3
"""Prove flags0 CLEAR terminates without even nativeVALID, full R19 chain."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'clear_chain_01/deepseek_execution_02/isolation/tree'

def main():
    result={'hardware':False,'changed_rtl':False,'cases':[]}
    with tempfile.TemporaryDirectory(prefix='r19-zero-clear-') as t:
        task=Path(t)
        for path in SRC.iterdir():
            if path.suffix in {'.v','.sv','.hex'}:
                shutil.copyfile(path,task/path.name)
        bench=task/'bench.sv'
        original=bench.read_text()
        assert hashlib.sha256(bench.read_bytes()).hexdigest()=='730576cc4633cc824c03157b31da3cece0ea7130ce3e2af746c7899c6ac2c5ac'
        code=original.replace("words[9]  = 32'h00000001;", "words[9]  = 32'h00000000;")
        code=code.replace('accepted != 1 || received != 16 || stalls == 0', 'accepted != 0 || received != 16 || stalls != 0')
        code=code.replace('accepted != 1 || received != 16', 'accepted != 0 || received != 16')
        code=code.replace('    // Global bounded watchdog for the whole scenario.', '''    // Any native request is forbidden, including requests never accepted.
    always @(posedge mem_clk) if(resetn && valid)
        $fatal(1, "ZERO_CLEAR_NATIVE_REQUEST");
    // Global bounded watchdog for the whole scenario.''')
        assert code!=original
        bench.write_text(code)
        (HERE/'bench_used.sv').write_text(code)
        result['bench_sha256']=hashlib.sha256(bench.read_bytes()).hexdigest()
        result['rtl_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in task.glob('*.v')}
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
             '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(task/'obj'),
             'bench.sv','native_monitor.sv']+[p.name for p in sorted(task.glob('*.v'))]
        run=subprocess.run(cmd,cwd=task,capture_output=True,text=True,timeout=48)
        (HERE/'compile.log').write_text(run.stdout+run.stderr)
        assert run.returncode==0,'compile failed'
        for seed in (1,8):
            for fault in (0,1,2,3):
                run=subprocess.run([str(task/'obj/Vbench'),f'+seed={seed}',f'+fault={fault}'],cwd=task,capture_output=True,text=True,timeout=3)
                log=run.stdout+run.stderr;(HERE/f'seed{seed}_fault{fault}.log').write_text(log)
                ok=run.returncode==0 and 'BASELINE_PASS accepted=0 words=16 stalls=0' in log
                result['cases'].append(dict(seed=seed,fault=fault,passed=ok,returncode=run.returncode))
        result['passed']=all(x['passed'] for x in result['cases'])
        (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result));return int(not result['passed'])

if __name__=='__main__':raise SystemExit(main())
