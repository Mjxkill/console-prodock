#!/usr/bin/env python3
"""Cycle equivalence of the indexed line reader in the full 800x480 bench.

Reference must have the coverage output (perspective/composition r7 or later).
Both readers see identical DDR and descriptor inputs; only the current reader
drives the arbiter. Undefined block payloads outside block_valid are ignored.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from gpu_equivalence_helpers import arbiter_equivalence

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT/'tang/rtl/video/gpu_line_reader.v'
    reference = a.reference_root/'tang/rtl/video/gpu_line_reader.v'
    current, old = source.read_text(), reference.read_text()
    assert 'output wire [31:0] block_coverage' in old
    (out/'reference.v').write_text(old.replace('module gpu_line_reader #(', 'module gpu_line_reader_reference #(', 1))
    header = current[:current.index('    localparam BLOCKS=')].replace('module gpu_line_reader #(', 'module gpu_line_reader_equiv #(', 1)
    inputs = ['clk', 'resetn', 'start', 'layers', 'config_bank', 'sprites',
              'clear_maxima', 'base', 'line_y', 'config_data', 'fetch_ready',
              'fetch_data', 'fetch_data_valid', 'sprite_head_index',
              'sprite_metadata', 'sprite_row_data']
    outputs = dict(busy=1, done=1, config_address=8, fetch_valid=1, fetch_addr=29,
                   block_valid=1, block_index=5, block_data=256, block_coverage=32,
                   max_cycles=32, invalid_layers=32, sprite_head_layer=4,
                   sprite_index=6, sprite_row_address=11, max_sprites=32,
                   max_sprite_pixels=32)
    body = ''.join(f'    wire [{width-1}:0] ref_{name};\n' for name, width in outputs.items())
    for typ, prefix in [('gpu_line_reader', ''), ('gpu_line_reader_reference', 'ref_')]:
        ports = [f'.{name}({name})' for name in inputs]
        ports += [f'.{name}({prefix}{name})' for name in outputs]
        body += f'    {typ} #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_{typ} ('+', '.join(ports)+');\n'
    controls = [n for n in outputs if n not in ['block_data', 'block_coverage', 'block_index']]
    # Preserve the bench's diagnostic view through the comparison wrapper.
    body += '    wire [31:0] elapsed=u_gpu_line_reader.elapsed;\n'
    body += '''    integer compared_cycles=0;
    always @(posedge clk) if(resetn)begin
        compared_cycles<=compared_cycles+1;
'''
    for name in controls:
        body += f'        if ({name} !== ref_{name}) $fatal(1,"Reader {name} mismatch at %0d: current=%h reference=%h",compared_cycles,{name},ref_{name});\n'
    body += '''        if(block_valid && {block_index,block_data,block_coverage} !==
            {ref_block_index,ref_block_data,ref_block_coverage})
            $fatal(1,"Reader block mismatch at %0d",compared_cycles);
    end
    final $display("READER EQUIVALENCE: %0d cycles compared",compared_cycles);
endmodule
`default_nettype wire
'''
    (out/'wrapper.sv').write_text(header+body)
    scanout = (ROOT/'tang/rtl/video/gpu_scanout.v').read_text()
    assert 'gpu_line_reader #(' in scanout
    (out/'scanout.v').write_text(scanout.replace('gpu_line_reader #(', 'gpu_line_reader_equiv #(', 1))
    sources = ['TESTS/rtl/gpu_layers_tb.sv', 'tang/rtl/video/gpu_line_reader.v',
               'tang/rtl/video/gpu_tile_row.v', 'tang/rtl/video/gpu_sprite_cache.v',
               'tang/rtl/video/gpu_rgb_reader.v', 'tang/rtl/board/ddr_gpu_arb.v',
               'tang/rtl/board/cdc_word.v']
    arb_sources, arb_inputs = arbiter_equivalence(ROOT, a.reference_root, out, ROOT/'TESTS/rtl/gpu_layers_tb.sv')
    sources.remove('TESTS/rtl/gpu_layers_tb.sv')
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator', '--binary', '-j', '4', '--timing', '-Wno-fatal',
                        '--top-module', 'gpu_layers_tb', '-GW=800', '-GH=480',
                        '-GVT=533', '-GSPRITES=1', '-GTILES=5', '-GOVERLAY=1',
                        '--Mdir', str(out/'obj')]+[str(ROOT/s) for s in sources]
                       + [str(s) for s in arb_sources]
                       + [str(out/s) for s in ['wrapper.sv', 'reference.v', 'scanout.v']],
                       stdout=log, stderr=log, check=True)
    with (out/'simulation.log').open('w') as log:
        subprocess.run([str(out/'obj/Vgpu_layers_tb')], cwd=out,
                       stdout=log, stderr=log, check=True)
    log = (out/'simulation.log').read_text()
    cycles = int(re.search(r'READER EQUIVALENCE: (\d+) cycles compared', log)[1])
    result = dict(pass_cycle_equivalence=True, cycles=cycles,
                  sha256={str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in [source, reference, *arb_inputs]})
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log, end='')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
