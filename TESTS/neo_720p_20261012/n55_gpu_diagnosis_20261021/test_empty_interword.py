#!/usr/bin/env python3
"""Replay the passed post-PnR GPU bench with EMPTY required before every word.

Only stimulus changes: 12 additional hclk periods before each FIFO write and an
assertion that the reader-side FIFO EMPTY is true. The 80 configuration cases,
official primitives, routed GPU/debug cells and absence of DDR stay identical.
"""
import hashlib,json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
base=HERE/'n55_full_routed_r2'
out=HERE/'n55_full_routed_empty_interword_r1'
proof=json.loads((base/'result.json').read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
if not proof['passed']:raise ValueError('Prerequisite routed test did not pass')
for name,wanted in proof['sha256'].items():
    if sha(Path(name))!=wanted:raise ValueError('Changed routed evidence: '+name)
bench=(base/'tb.sv').read_text()
marker='task write_reg(input [14:0] address,input [31:0] value);'
if bench.count(marker)!=1:raise ValueError('Unknown AHB bench')
bench=bench.replace(marker,marker+r'''
 if(address==15'h1010)begin
   repeat(12)@(negedge hclk);
   if(dut.gpu_debug_state_142[38]!==0 ||
      dut.\u_accel/u_commands/rd_bin !==dut.\u_accel/u_commands/wr_bin_r )
     $fatal(1,"FIFO RAM and registered head must be empty before spaced word");
 end
''').replace('PASS routed full GPU:','PASS routed EMPTY-per-word GPU:')
out.mkdir(exist_ok=False)
(out/'tb.sv').write_text(bench)
compile_cmd=list(proof['compile_command'])
compile_cmd[compile_cmd.index('-o')+1]=str(out/'sim.vvp')
compile_cmd[compile_cmd.index(str(base/'tb.sv'))]=str(out/'tb.sv')
sim_cmd=[proof['simulation_command'][0],str(out/'sim.vvp')]
result=dict(passed=False,scope=__doc__,compile_command=compile_cmd,simulation_command=sim_cmd,
    source_netlist_sha256=proof['source_netlist_sha256'],
    sha256={str(f):sha(f) for f in (Path(__file__),base/'result.json',out/'tb.sv')})
try:
    for cmd,logfile,timeout in ((compile_cmd,'compile.log',180),(sim_cmd,'simulation.log',600)):
        with (out/logfile).open('w') as log:subprocess.run(cmd,stdout=log,stderr=log,check=True,timeout=timeout)
    result['passed']='PASS routed EMPTY-per-word GPU: 80 configurations' in (out/'simulation.log').read_text()
finally:(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print((out/'simulation.log').read_text())
if not result['passed']:raise SystemExit('EMPTY-per-word GPU test failed')
