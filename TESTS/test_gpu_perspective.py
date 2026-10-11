#!/usr/bin/env python3
"""Exact signed rational coordinates versus Python integers, including reset."""
import argparse
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--reference-rtl', type=Path, help='compare every output cycle with frozen RTL')
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261003)
    limit = 1 << 48
    cases = [(u, v, q) for u in (-limit, -65537, -1, 0, 1, 65537, limit-1)
             for v in (-limit, -1, 0, limit-1)
             for q in (-limit, -65536, -1, 0, 1, 2, 257, 65536, limit-1)]
    for _ in range(2000):
        q = rng.randrange(1, limit)
        if rng.randrange(2):
            q = rng.randrange(1, 1 << 32)
            u, v = (rng.randrange(-255*q, 255*q) for _ in range(2))
        else:
            u, v = (rng.randrange(-limit, limit) for _ in range(2))
        cases.append((u, v, q))
    # Exact transitions between the 8-, 12- and 50-bit quotient paths, including
    # negative numerators with a nonzero remainder (floor, not truncation).
    for q in (1, 3, 65536, 1 << 30):
        for coordinate in (255, 256, 257, 4095, 4096, 4097):
            for epsilon in (-1, 0, 1):
                u = coordinate*q+epsilon
                cases.extend(((u, -u, q), (1, -u, q), (-u, 1, q)))
    vectors = []
    for u, v, q in cases:
        word = int(q > 0)
        for x in (u, v, q, u//q if q > 0 else 0, v//q if q > 0 else 0):
            word = (word << 49) | (x & ((1 << 49)-1))
        vectors.append(f'{word:062x}\n')
    (out/'vectors.hex').write_text(''.join(vectors))
    (out/'tb.sv').write_text('''`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,start=0;
always #6.666 clk=~clk;
reg signed [48:0] uq,vq,q;
wire done,valid;
wire signed [48:0] tu,tv;
gpu_perspective dut(.*);
reg [245:0] vectors[0:''' + str(len(cases)-1) + '''];
integer count,cycles,max_cycles=0,fast12_count=0;
initial begin
    $readmemh("vectors.hex",vectors);
    repeat(3)@(negedge clk);rst=0;
    for(integer i=0;i<''' + str(len(cases)) + ''';i++)begin
        @(negedge clk);{uq,vq,q}=vectors[i][244:98];start=1;
        @(negedge clk);start=0;cycles=0;
        while(!done && cycles<32)begin @(negedge clk);cycles++;end
        if(!done || valid!==vectors[i][245])$fatal(1,"Validity/timeout case=%0d",i);
        if(valid && {tu,tv}!==vectors[i][97:0])$fatal(1,"Quotient case=%0d U=%0d V=%0d Q=%0d got=%0d,%0d",i,uq,vq,q,tu,tv);
        if(valid && !dut.fast && dut.fast12)begin
            if(cycles!=9)$fatal(1,"12-bit path latency %0d",cycles);
            fast12_count++;
        end
        if(cycles>max_cycles)max_cycles=cycles;
        if(i%100==0)begin
            @(negedge clk);uq=49'sh0ffffffffffff;vq=-uq;q=1;start=1;
            @(negedge clk);start=0;
            repeat(3)@(negedge clk);rst=1;
            repeat(2)@(negedge clk);rst=0;
            repeat(30)begin @(negedge clk);if(done)$fatal(1,"Old result replayed after reset");end
        end
    end
    if(fast12_count==0)$fatal(1,"12-bit path not covered");
    $display("PASS: ''' + str(len(cases)) + ''' signed rational pairs, extrema, zero/negative Q, reset during division; max latency=%0d cycles, 12-bit cases=%0d",max_cycles,fast12_count);
    $finish;
end
endmodule
''')
    sources = [str(ROOT/'tang/rtl/video/gpu_perspective.v')]
    if args.reference_rtl:
        (out/'reference.v').write_text(args.reference_rtl.read_text().replace('module gpu_perspective (','module perspective_reference (',1))
        compare = '''wire ref_done,ref_valid;wire signed [48:0] ref_tu,ref_tv;
perspective_reference ref_dut(.clk(clk),.rst(rst),.start(start),.uq(uq),.vq(vq),.q(q),
 .done(ref_done),.valid(ref_valid),.tu(ref_tu),.tv(ref_tv));
always @(negedge clk)if(!rst && {done,valid,tu,tv}!=={ref_done,ref_valid,ref_tu,ref_tv})
 $fatal(1,"Perspective cycle equivalence mismatch");
'''
        bench = out/'tb.sv';bench.write_text(bench.read_text().replace('gpu_perspective dut(.*);','gpu_perspective dut(.*);\n'+compare))
        sources.append(str(out/'reference.v'))
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator', '--binary', '-j', '4', '--timing', '-Wno-fatal',
                        '--top-module', 'tb', '--Mdir', str(out/'obj'), str(out/'tb.sv'),
                        *sources], stdout=log, stderr=log, check=True)
    result = subprocess.run([str(out/'obj/Vtb')], cwd=out, capture_output=True, text=True)
    (out/'simulation.log').write_text(result.stdout + result.stderr)
    print(result.stdout, end='')
    result.check_returncode()


if __name__ == '__main__':
    main()
