#!/usr/bin/env python3
"""Exercise the actual synthesized mask cone with official Gowin primitives.

Functional simulation only, without SDF. State/visibility inputs are driven
at the cone boundary; the full RTL test covers their producers.
"""
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
from neo.pixel_mask import audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    net = a.build/'impl/gwsynthesis/console_neo.vg'
    if not audit(net)['passed']:
        raise ValueError('Mask mapping audit must pass first')
    text = module(net.read_text(), 'gpu_v1')
    cells, drivers = {}, {}
    parameters = {}
    for hit in re.finditer(r'^defparam (\S+)\.[^.;]+\s*=[^;]+;', text, re.M):
        parameters.setdefault(hit[1], []).append(hit[0])
    for m in re.finditer(r'^[ \t]*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);', text, re.S | re.M):
        kind, name, ports = m.groups()
        pins = {k: re.sub(r'\s+', '', v).removeprefix('\\')
                for k, v in re.findall(r'\.(\w+)\(([^()]*)\)', ports)}
        if kind.startswith(('LUT', 'DFF')) or kind in ('BUF', 'INV'):
            cells[name] = dict(kind=kind, pins=pins, text=m[0]+'\n'+'\n'.join(parameters.get(name, [])))
            drivers[pins.get('F', pins.get('Q', pins.get('O')))] = name
    selected = {n for n, c in cells.items() if c['kind'].startswith('DFF') and 'pixel_written' in n}
    stack = [cells[n]['pins']['D'] for n in selected]
    roots = set()
    allowed = r'(?:pixel_written|lane)\[\d+\]|state\[(?:13|26|55)\]|color_load|pixel_visible|gpu_debug_state_48|GND|VCC'
    while stack:
        wire = stack.pop()
        if re.fullmatch(allowed, wire):
            roots.add(wire)
            continue
        if wire not in drivers:
            raise ValueError('Unknown mask cone input: '+wire)
        name = drivers[wire]
        if name in selected:
            continue
        cell = cells[name]
        if not cell['kind'].startswith('LUT') and cell['kind'] not in ('INV', 'BUF'):
            raise ValueError('Unexpected sequential mask dependency: '+name)
        selected.add(name)
        stack.extend(v for k, v in cell['pins'].items() if k.startswith('I'))
    nets = {v for n in selected for v in cells[n]['pins'].values()}
    known = {'gpu_clk', 'gpu_debug_state_48', 'color_load', 'pixel_visible', 'GND', 'VCC'}
    scalar = sorted(n for n in nets if n not in known and '[' not in n)
    mapped = '''module mapped_mask(input gpu_clk,gpu_debug_state_48,color_load,pixel_visible,
input [57:0] state,input [3:0] lane,output [15:0] pixel_written);
wire [15:0] pixel_written_next;
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
reg clk=0, resetn=0, color_load=0, visible=0;
reg [57:0] state=0;
reg [3:0] lane=0;
wire [15:0] actual;
reg [15:0] wanted=0;
integer checks=0,rounds,r,s,c,l;
always #5 clk=~clk;
mapped_mask dut(.gpu_clk(clk),.gpu_debug_state_48(resetn),
 .color_load(color_load),.pixel_visible(visible),.state(state),.lane(lane),.pixel_written(actual));
task tick;
begin
 @(posedge clk);
 if(!resetn || state[13])wanted=0;
 else if(!color_load && visible && (state[26] || state[55]))wanted[lane]=1;
 @(negedge clk);
 if(actual !== wanted)$fatal(1,"Mask cone differs at %0d: actual=%h expected=%h",checks,actual,wanted);
 checks++;
end
endtask
initial begin
 tick;
 for(rounds=0;rounds<3;rounds++)for(r=0;r<2;r++)for(s=0;s<8;s++)
 for(c=0;c<4;c++)for(l=0;l<16;l++)begin
  resetn=r;state=0;state[13]=s&1;state[26]=(s>>1)&1;state[55]=(s>>2)&1;
  color_load=c&1;visible=(c>>1)&1;lane=l;
  tick;
 end
 // Reset/CHUNK must dominate unknown private data.
 resetn=0;state='x;lane='x;color_load=1'bx;visible=1'bx;tick;
 resetn=1;state=0;state[13]=1;tick;
 $display("PASS: mapped pixel mask %0d checks",checks);$finish;
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
    hit = re.search(r'PASS: mapped pixel mask (\d+) checks', log)
    result = dict(passed=run.returncode == 0 and bool(hit), checks=int(hit[1]) if hit else 0,
                  scope=__doc__, primitive_types=sorted(kinds), cone_cells=len(selected),
                  roots=sorted(roots), netlist_sha256=sha(net), primitives_sha256=sha(PRIMITIVES),
                  script_sha256=sha(Path(__file__)))
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log.strip())
    if not result['passed']:
        raise SystemExit('Mapped mask test failed')


if __name__ == '__main__':
    main()
