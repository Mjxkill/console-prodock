#!/usr/bin/env python3
"""Characterize the official CLKDIV functional model, not routed reset safety."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from check_neo_fifo_mapped import module
from gowin_toolchain import PRIMITIVES

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
library = PRIMITIVES.read_text()
primitive = out / 'primitives.v'
primitive.write_text('`timescale 1ns/1ps\n' + '\n'.join(module(library, name) for name in ('GSR', 'CLKDIV')))
bench = out / 'tb.sv'
bench.write_text('''`timescale 1ns/1ps
module tb;
 reg fast=0, resetn=0, gsrn=0;
 wire ui;
 GSR GSR(.GSRI(gsrn));
 CLKDIV #(.DIV_MODE("4")) dut(.HCLKIN(fast),.RESETN(resetn),.CALIB(1'b0),.CLKOUT(ui));
 always #1.25 fast=~fast;
 realtime released, delay_ns;
 integer phase;
 initial begin
   #10; gsrn=1;
   for(phase=1;phase<2500;phase=phase+25) begin
     @(negedge fast); resetn=0;
     repeat(5) @(negedge fast);
     if(ui!==0) $fatal(1,"Clock not held low during reset");
     #(phase/1000.0); resetn=1; released=$realtime;
     @(posedge ui); delay_ns=$realtime-released;
     if(delay_ns<2.499 || delay_ns>5.001) $fatal(1,"Unexpected CLKDIV release latency %f",delay_ns);
     $display("PHASE %0d FIRST_EDGE_NS %0.3f",phase,delay_ns);
     repeat(3) @(posedge ui);
   end
   $display("PASS CLKDIV functional release phase sweep");
   $finish;
 end
 initial begin #100000; $fatal(1,"Timeout"); end
endmodule
''')
compiler = Path(shutil.which('iverilog') or '/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
ivlib = compiler.parent.parent / 'lib/x86_64-linux-gnu/ivl'
flags = ['-B', str(ivlib)] if ivlib.is_dir() else []
result = dict(passed=False, scope=__doc__, primitive_sha256=hashlib.sha256(PRIMITIVES.read_bytes()).hexdigest())
try:
    r = subprocess.run([str(compiler), *flags, '-g2012', '-s', 'tb', '-o', str(out/'sim'), str(bench), str(primitive)], capture_output=True, text=True, timeout=30)
    (out/'compile.log').write_text(r.stdout+r.stderr)
    r.check_returncode()
    r = subprocess.run([str(compiler.parent/'vvp'), str(out/'sim')], capture_output=True, text=True, timeout=20)
    (out/'run.log').write_text(r.stdout+r.stderr)
    r.check_returncode()
    delays = [float(line.split()[-1]) for line in r.stdout.splitlines() if line.startswith('PHASE ')]
    result.update(passed=len(delays)==100 and 'PASS CLKDIV' in r.stdout, phases=len(delays), min_first_edge_ns=min(delays), max_first_edge_ns=max(delays))
finally:
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
if not result['passed']:
    raise SystemExit(1)
