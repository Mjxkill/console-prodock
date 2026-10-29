#!/usr/bin/env python3
"""Compare mapped 50-ms sequencer with RTL using official Gowin primitives."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from gowin_toolchain import PRIMITIVES
from check_neo_fifo_mapped import module

BUILD = ROOT / 'tang/impl/console_neo_n56r15_reset50ms'
OUT = HERE / 'mapped_50ms_r2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    net = BUILD / 'reset_ip/neo_reset_trial.vg'
    assert sha(net) == json.loads((BUILD / 'reset_ip/result.json').read_text())['vg_sha256']
    text = net.read_text()
    names = re.findall(r'^module (\w+)', text, re.M)
    assert set(names) == {'neo_reset_trial', 'neo_reset_trial_rx'}
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(r'\b' + name + r'\b', name + '_mapped', text)
    # Only the constant global reset inserted for a standalone top is removed.
    # The integrated design already has its single GSR, tied high as here.
    text, n = re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);', '', text)
    assert n == 1
    (OUT / 'mapped.v').write_text(text)
    primitive_text = PRIMITIVES.read_text()
    available = set(re.findall(r'^module (\w+)', primitive_text, re.M))
    needed = (set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(', text, re.M)) & available) | {'GSR'}
    while True:
        deps = set()
        for name in needed:
            deps |= set(re.findall(r'^\s*(\w+)\s+\w+\s*\(', module(primitive_text, name), re.M)) & available
        expanded = needed | deps
        if expanded == needed:
            break
        needed = expanded
    primitives = '`timescale 1ns/1ps\n' + '\n'.join(
        re.findall(r'^primitive .*?^endprimitive', primitive_text, re.M | re.S)) + '\n'
    primitives += '\n'.join(module(primitive_text, n) for n in sorted(needed))
    (OUT / 'primitives.v').write_text(primitives)
    tb = (HERE / 'reset_trial_tb.sv').read_text()
    marker = '    task byte_tx(input [7:0] b);'
    assert tb.count(marker) == 1
    tb = tb.replace(marker, '''    GSR GSR(.GSRI(1'b1));
    wire mrelease,mmode,mhold,mdone,ma,mr;
    wire [3:0] mepoch;
    neo_reset_trial_mapped mapped(.clk_ref(clk),.ahb_clk(ahb),.rtc_clk(rtc),.serial_rx(rx),
        .ddr_ready(ready),.pll_ready(locked),.cpu_reset_n(cpu_sync[1]),
        .release_request(mrelease),.delay_mode(mmode),.command_epoch(mepoch),
        .holding(mhold),.delay_done(mdone),.ahb_tick(ma),.rtc_tick(mr));
    always @(negedge clk) begin
        #1;
        if({release_request,mode,epoch,holding,done,ahb_tick,rtc_tick} !==
           {mrelease,mmode,mepoch,mhold,mdone,ma,mr})
            $fatal(1,"Mapped sequencer mismatch at %0t",$time);
    end
''' + marker)
    (OUT / 'tb.sv').write_text(tb)
    compiler = Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    library = compiler.parent.parent / 'lib/x86_64-linux-gnu/ivl'
    inputs = [OUT / 'tb.sv', HERE / 'neo_reset_trial.v', HERE / 'neo_reset_trial_rx.v', OUT / 'mapped.v', OUT / 'primitives.v']
    result = dict(passed=False, functional_only=True, timing=False, metastability=False,
        netlist_sha256=sha(net), primitive_library_sha256=sha(PRIMITIVES),
        inputs={str(p): sha(p) for p in inputs}, primitive_types=sorted(needed),
        global_reset='One constant-high GSR in the bench, as in the parent design')
    try:
        with (OUT / 'compile.log').open('x') as log:
            subprocess.run([str(compiler), '-B', str(library), '-g2012', '-s', 'reset_trial_tb',
                '-o', str(OUT / 'sim.vvp'), *map(str, inputs)], stdout=log, stderr=log, check=True, timeout=30)
        with (OUT / 'simulation.log').open('x') as log:
            subprocess.run([str(compiler.parent / 'vvp'), str(OUT / 'sim.vvp')],
                stdout=log, stderr=log, check=True, timeout=600)
        assert 'PASS reset trial: real 50 ms' in (OUT / 'simulation.log').read_text()
        result['passed'] = True
    finally:
        result['logs'] = {p.name: sha(p) for p in OUT.glob('*.log')}
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
