#!/usr/bin/env python3
"""Check ordered scanout requests, backpressure and reset with a stopped clock."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference-root',type=Path,help='Compare every cycle with a frozen queue implementation')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=['TESTS/rtl/neo_scan_queue_tb.sv','tang/boards/neo/neo_scan_queue.v',
             'TESTS/rtl/ddr_gpu_arb_tb.sv','tang/rtl/board/ddr_gpu_arb.v']
    result={'passed':False,'sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'cases':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='neo-scan-queue-') as tmp:
            if a.reference_root:
                reference=(a.reference_root/'tang/boards/neo/neo_scan_queue.v').resolve()
                result['sha256'][str(reference)]=hashlib.sha256(reference.read_bytes()).hexdigest()
                ref_path=Path(tmp)/'reference.v'
                ref_path.write_text(reference.read_text().replace('module neo_scan_queue (','module neo_scan_queue_reference (',1))
                bench=Path(tmp)/'compare.sv'
                bench.write_text((ROOT/sources[0]).read_text().replace('    neo_scan_queue dut(.*);', '''    neo_scan_queue dut(.*);
    wire ref_in_ready,ref_out_valid;
    wire [28:0] ref_out_addr;
    neo_scan_queue_reference reference_queue(.clk(clk),.resetn(resetn),
        .in_valid(in_valid),.in_addr(in_addr),.in_ready(ref_in_ready),
        .out_valid(ref_out_valid),.out_addr(ref_out_addr),.out_ready(out_ready));
    always @(posedge clk)begin
        if({in_ready,out_valid}!=={ref_in_ready,ref_out_valid})$fatal(1,"Queue handshake cycle changed");
        if(out_valid && out_addr!==ref_out_addr)$fatal(1,"Queue payload cycle changed");
    end''',1))
                queue_sources=[str(bench),sources[1],str(ref_path)]
            else:queue_sources=sources
            with (out/'build.log').open('w') as log:
                subprocess.run(['verilator','--binary','--timing','-Wno-fatal','-j','2',
                                '--top-module','neo_scan_queue_tb','--Mdir',tmp,*queue_sources],
                               cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
            for seed in (138,20261014,7351):
                run=subprocess.run([str(Path(tmp)/'Vneo_scan_queue_tb'),f'+seed={seed}'],
                                   capture_output=True,text=True,timeout=30)
                (out/f'seed{seed}.log').write_text(run.stdout+run.stderr)
                passed=run.returncode==0 and 'PASS accepted=' in run.stdout
                result['cases'].append({'seed':seed,'passed':passed})
                if not passed:raise RuntimeError(run.stdout+run.stderr)
                print(run.stdout.splitlines()[0],flush=True)
            for queue in (0,1):
                obj=str(Path(tmp)/f'arb{queue}')
                with (out/f'arb{queue}_build.log').open('w') as log:
                    subprocess.run(['verilator','--binary','--timing','-Wno-fatal','-j','2',
                                    '--top-module','ddr_gpu_arb_tb',f'-GNEO_SCAN_QUEUE={queue}',
                                    '--Mdir',obj,*sources[1:]],cwd=ROOT,stdout=log,
                                   stderr=subprocess.STDOUT,check=True,timeout=180)
                run=subprocess.run([str(Path(obj)/'Vddr_gpu_arb_tb')],
                                   capture_output=True,text=True,timeout=30)
                (out/f'arb{queue}.log').write_text(run.stdout+run.stderr)
                passed=run.returncode==0 and 'PASS: 3 DDR clients' in run.stdout
                result['cases'].append({'arbiter_request_queue':bool(queue),'passed':passed})
                if not passed:raise RuntimeError(run.stdout+run.stderr)
                print(run.stdout.splitlines()[0],flush=True)
        result['passed']=True
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
