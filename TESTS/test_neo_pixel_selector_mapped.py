#!/usr/bin/env python3
"""Check the synthesized perspective-selector cone with Gowin primitives, no SDF."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_neo_fifo_mapped import module
from gowin_toolchain import PRIMITIVES
from neo.pixel_selector import audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    net = a.build/'impl/gwsynthesis/console_neo.vg'
    if not audit(net)['passed']:
        raise ValueError('Selector mapping audit must pass first')
    text = module(net.read_text(), 'gpu_v1')
    cells, drivers, parameters = {}, {}, {}
    for hit in re.finditer(r'^defparam (\S+)\.[^.;]+\s*=[^;]+;', text, re.M):
        parameters.setdefault(hit[1], []).append(hit[0])
    for m in re.finditer(r'^[ \t]*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);', text, re.S | re.M):
        kind, name, ports = m.groups()
        pins = {k: re.sub(r'\s+', '', v).removeprefix('\\')
                for k, v in re.findall(r'\.(\w+)\(([^()]*)\)', ports)}
        if kind.startswith(('LUT', 'DFF')) or kind in ('BUF', 'INV'):
            cells[name] = dict(kind=kind, pins=pins, text=m[0]+'\n'+'\n'.join(parameters.get(name, [])))
            drivers[pins.get('F', pins.get('Q', pins.get('O')))] = name
    selected = {n for n, c in cells.items() if c['kind'].startswith('DFF') and 'per_select' in n}
    stack = [cells[n]['pins']['D'] for n in selected]
    roots = set()
    while stack:
        wire = stack.pop()
        if re.fullmatch(r'state\[(?:13|26|27|55)\]|per_select|gpu_debug_state_48|GND|VCC', wire):
            roots.add(wire)
            continue
        if wire not in drivers:
            raise ValueError('Unknown selector cone input: '+wire)
        name = drivers[wire]
        if name in selected:
            continue
        cell = cells[name]
        if not cell['kind'].startswith('LUT') and cell['kind'] not in ('INV', 'BUF'):
            raise ValueError('Unexpected sequential selector dependency: '+name)
        selected.add(name)
        stack.extend(v for k, v in cell['pins'].items() if k.startswith('I'))
    nets = {v for n in selected for v in cells[n]['pins'].values()}
    known = {'gpu_clk', 'gpu_debug_state_48', 'per_select', 'GND', 'VCC'}
    scalar = sorted(n for n in nets if n not in known and '[' not in n)
    mapped = '''module mapped_selector(input gpu_clk,gpu_debug_state_48,
input [57:0] state,output per_select);
wire GND=1'b0,VCC=1'b1;
''' + ''.join(f'wire {n};\n' for n in scalar)
    mapped += '\n'.join(cells[n]['text'] for n in sorted(selected))+'\nendmodule\n'
    out = a.out.resolve();out.mkdir(parents=True, exist_ok=False)
    (out/'mapped.v').write_text(mapped)
    vendor = PRIMITIVES.read_text()
    kinds = {cells[n]['kind'] for n in selected} | {'GSR'}
    available = set(re.findall(r'^module (\w+)', vendor, re.M))
    while True:
        dependencies = set()
        for kind in kinds:
            dependencies.update(re.findall(r'^\s*(\w+)\s+\w+\s*\(', module(vendor, kind), re.M))
        expanded = kinds | (dependencies & available)
        if expanded == kinds:
            break
        kinds = expanded
    (out/'primitives.v').write_text('`timescale 1ns/1ps\n'+
        '\n'.join(re.findall(r'^primitive .*?^endprimitive', vendor, re.M | re.S))+'\n'+
        '\n'.join(module(vendor, k) for k in sorted(kinds)))
    (out/'tb.sv').write_text('''`timescale 1ns/1ps
module tb;
GSR GSR(.GSRI(1'b1));
reg clk=0,resetn=0;
reg [57:0] state=0;
wire actual;
reg wanted=0;
integer checks=0,r,s,repeat_count,n;
always #6.666 clk=~clk;
mapped_selector dut(.gpu_clk(clk),.gpu_debug_state_48(resetn),.state(state),.per_select(actual));
task tick;
begin
 @(posedge clk);
 if(!resetn || state[13])wanted=0;
 else if(state[26] || state[27] || state[55])wanted=~wanted;
 @(negedge clk);
 if(actual !== wanted)$fatal(1,"Selector differs at %0d: actual=%b expected=%b",checks,actual,wanted);
 checks++;
end
endtask
initial begin
 tick;
 // Priority, held state, consecutive advances, all three advance states.
 for(repeat_count=0;repeat_count<7;repeat_count++)for(r=0;r<2;r++)for(s=0;s<16;s++)begin
  resetn=r;state=0;state[13]=s&1;state[26]=(s>>1)&1;state[27]=(s>>2)&1;state[55]=(s>>3)&1;
  tick;tick;tick;
 end
 // Every new chunk starts at divider 0, including singleton/odd chunks.
 resetn=1;
 for(n=1;n<=17;n++)begin
  state=0;state[13]=1;tick;
  state=0;state[55]=1;repeat(n)tick;
 end
 // Reset or CHUNK dominates unknown private state.
 resetn=0;state='x;tick;
 resetn=1;state=0;state[13]=1;state[26]=1'bx;tick;
 $display("PASS: mapped perspective selector %0d checks",checks);$finish;
end
endmodule
''')
    compiler = Path(shutil.which('iverilog') or '/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog').resolve(strict=True)
    library = compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    flags = ['-B', str(library)] if library.is_dir() else []
    with (out/'compile.log').open('w') as log:
        subprocess.run([str(compiler), *flags, '-g2012', '-s', 'tb', '-o', str(out/'sim.vvp')]
                       +[str(out/n) for n in ('tb.sv', 'mapped.v', 'primitives.v')],
                       stdout=log, stderr=log, check=True, timeout=60)
    run = subprocess.run([str(compiler.parent/'vvp'), str(out/'sim.vvp')],
                         capture_output=True, text=True, timeout=60)
    log = run.stdout+run.stderr
    (out/'simulation.log').write_text(log)
    hit = re.search(r'PASS: mapped perspective selector (\d+) checks', log)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(passed=run.returncode == 0 and bool(hit), checks=int(hit[1]) if hit else 0,
                  scope=__doc__, primitive_types=sorted(kinds), cone_cells=len(selected),
                  roots=sorted(roots), netlist_sha256=sha(net), primitives_sha256=sha(PRIMITIVES),
                  script_sha256=sha(Path(__file__)))
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log.strip())
    if not result['passed']:
        raise SystemExit('Mapped selector test failed')


if __name__ == '__main__':
    main()
