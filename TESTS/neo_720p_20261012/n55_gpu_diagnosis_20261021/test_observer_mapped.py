#!/usr/bin/env python3
"""Exercise real Neo geometry/pixel configuration netlists with Gowin primitives.

Checks valid/invalid commands, rejection ownership and every memory request
output. This is functional simulation without SDF, not a timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'tools/neo'), str(ROOT/'tools')]
from gowin_toolchain import PRIMITIVES
from probe_gpu_debug import target_cases, control_cases


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    netlist = a.build.resolve()/'impl/gwsynthesis/console_neo.vg'
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    modules = {}
    for match in re.finditer(r'^module (\w+)\b.*?^endmodule', netlist.read_text(),
                             re.M | re.S):
        name = match[1]
        if re.fullmatch(r'gpu_(?:geometry|v1|copy565|texture_cache|geom_div(?:_\d+)?|'
                        r'perspective(?:_\d+)?|triangle(?:_floor_div(?:_\d+)?)?)', name):
            if name in modules:
                raise ValueError('Duplicate mapped module '+name)
            modules[name] = match[0]
    if not {'gpu_geometry', 'gpu_v1', 'gpu_copy565'} <= modules.keys():
        raise ValueError('Missing mapped geometry/pixel modules')
    mapped = out/'mapped.v'
    mapped.write_text('\n\n'.join(modules.values())+'\n')
    pins = {
        'gpu_clk': 'clk', 'v1_select': "1'b1",
        'v1_rx_valid': "1'b0", 'v1_accepted': "1'b1",
        'ext_command': 'command[255:32]', 'gpu_debug_state_98': 'start',
        'v1_rx_data': "256'd0",
    }
    pins.update({f'gpu_debug_state_{104+i}': f'command[{24+i}]' for i in range(8)})
    pins.update({f'gpu_debug_state_{224+i}': f'command[{i}]' for i in range(24)})
    pins.update({f'gpu_debug_state_{i}': 'resetn' for i in (46, 48, 49, 50, 51, 52, 53)})
    inputs = set(re.findall(r'^input (?:\[[^]]+\] )?(\w+);', modules['gpu_geometry'], re.M))
    if inputs != set(pins):
        raise ValueError('Changed mapped inputs: '+str(inputs ^ set(pins)))
    pins.update({
        'v1_done': 'done', 'v1_rejected': 'rejected',
        '\\geometry_stat[0] ': 'geometry_rejected',
        'native_valid': 'requests[0]', 'fetch_valid': 'requests[1]',
        'copy_valid': 'requests[2]', 'cache_valid': 'requests[3]',
        'gpu_observe_packet_words':'observed_headers[31:0]',
        'gpu_observe_packet_words_81':'observed_headers[63:32]',
    })
    cases = target_cases() + control_cases()
    calls = []
    for case in cases:
        words = ''.join(f'{w:08x}' for w in reversed(case['words']))
        rejected = int(not case['accepted'])
        geom = int(rejected and case['words'][0] >> 24 >= 31)
        is_target = int(case['words'][0] >> 24 == 22)
        calls.append(f' check_config(256\'h{words},1\'b{rejected},1\'b{geom},1\'b{is_target});')
    tb = out/'tb.sv'
    tb.write_text('''`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0,resetn=0,start=0;
always #6.666 clk=~clk;
reg [255:0] command=0;
wire done;
wire [3:0] requests;
wire [31:0] rejected,geometry_rejected;
wire [63:0] observed_headers;
reg [31:0] expected_pixel_header=0;
gpu_geometry dut(
''' + ',\n'.join(f'.{pin}({value})' for pin, value in pins.items()) + ''');
integer checks=0,timeout,rounds;
reg [31:0] rejected_before,geometry_before;
always @(negedge clk)
 if(resetn && requests !== 4'b0)$fatal(1,"Configuration issued memory request: %b",requests);
task check_config(input [255:0] words,input bad,input geometry_bad,input is_target);
begin
 @(negedge clk);command=words;
 rejected_before=rejected;geometry_before=geometry_rejected;
 repeat(4)@(negedge clk);
 start=1;@(negedge clk);start=0;
 timeout=0;
 while(!done && timeout<100)begin
  // The accepted packet must remain private and held during busy.
  command={8{32'hfedcba98 ^ timeout}};
  @(negedge clk);timeout++;
 end
 if(done!==1'b1 || rejected!==rejected_before+bad ||
    geometry_rejected!==geometry_before+geometry_bad)
  $fatal(1,"Configuration mismatch case %0d done=%b rejects=%0d/%0d geom=%0d/%0d",
      checks,done,rejected,rejected_before+bad,geometry_rejected,geometry_before+geometry_bad);
 if(is_target && dut.shader_target_valid !== !bad)
  $fatal(1,"Wrong TARGET validity case %0d",checks);
 if(words[31:24]<31)expected_pixel_header=words[31:0];
 if(observed_headers!=={expected_pixel_header,words[31:0]})
  $fatal(1,"Mapped observation headers case %0d actual=%h expected=%h",checks,observed_headers,{expected_pixel_header,words[31:0]});
 checks++;
 repeat(5)@(negedge clk);
end
endtask
initial begin
 for(rounds=0;rounds<2;rounds++)begin
  resetn=0;start=0;expected_pixel_header=0;
  repeat(10)@(negedge clk);
  resetn=1;repeat(10)@(negedge clk);
  if(rejected!==0 || geometry_rejected!==0 || dut.shader_target_valid!==0)
   $fatal(1,"Reset did not clear counters and descriptor validity");
''' + '\n'.join(calls) + '''
 end
 $display("PASS mapped GPU configuration: %0d cases, 2 resets",checks);$finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
''')
    toolroot = Path('/tmp/console-usb-sim-tools/extracted/usr')
    compile_cmd = [str(toolroot/'bin/iverilog'), '-B',
                   str(toolroot/'lib/x86_64-linux-gnu/ivl'), '-g2012', '-s', 'tb',
                   '-o', str(out/'sim.vvp'), str(tb), str(mapped), str(PRIMITIVES)]
    sim_cmd = [str(toolroot/'bin/vvp'), str(out/'sim.vvp')]
    result = dict(passed=False, build=str(a.build.resolve()), cases=cases,
                  rounds=2, compile_command=compile_cmd, simulation_command=sim_cmd,
                  modules=list(modules), netlist_sha256=sha(netlist),
                  sha256={str(f): sha(f) for f in (tb, mapped, PRIMITIVES)},
                  scope='Functional mapped primitives, no SDF; no owner/CDC/physical timing proof')
    try:
        for cmd, filename in ((compile_cmd, 'compile.log'), (sim_cmd, 'simulation.log')):
            with (out/filename).open('w') as log:
                subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=180)
        expected = f'PASS mapped GPU configuration: {2*len(cases)} cases, 2 resets'
        result['passed'] = expected in (out/'simulation.log').read_text()
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    if not result['passed']:
        raise SystemExit('Mapped configuration did not pass; see '+str(out))
    print(expected)


if __name__ == '__main__':
    main()
