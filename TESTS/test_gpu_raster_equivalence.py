#!/usr/bin/env python3
"""Compare every raster output cycle with a frozen RTL reference.

Reuses the DDR concurrency/stall bench and previously generated pixel vectors.
Both raster instances receive the same command, acceptance and return signals;
only the current instance drives the shared DDR model. An early/late/different
request, completion or counter is therefore detected before it can diverge.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from gpu_equivalence_helpers import arbiter_equivalence

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--commands', type=int, required=True)
    p.add_argument('--raster-bad', type=int, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    raster = ROOT/'tang/rtl/video/gpu_raster.v'
    reference = a.reference_root/'tang/rtl/video/gpu_raster.v'
    current = raster.read_text()
    old = reference.read_text()
    assert 'module gpu_raster #(' in old
    (out/'reference.v').write_text(old.replace('module gpu_raster #(', 'module gpu_raster_reference #(', 1))
    header = current[:current.index('    localparam IDLE=')].replace('module gpu_raster #(', 'module gpu_raster_equiv #(', 1)
    inputs = ['clk', 'rst', 'start', 'command', 'ready', 'rd_data', 'rd_valid']
    outputs = dict(busy=1, done=1, rejected=32, fragments=32, passed=32,
                   valid=1, write=1, addr=29, wr_data=256, wr_mask=32)
    body = ''.join(f'    wire [{width-1}:0] ref_{name};\n' for name, width in outputs.items())
    for typ, prefix in [('gpu_raster', ''), ('gpu_raster_reference', 'ref_')]:
        ports = [f'.{name}({name})' for name in inputs]
        ports += [f'.{name}({prefix}{name})' for name in outputs]
        body += f'    {typ} #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_{typ} ('+', '.join(ports)+');\n'
    names = ','.join(outputs)
    reference_names = ','.join('ref_'+name for name in outputs)
    body += '''    integer compared_cycles=0;
    always @(posedge clk) if(!rst)begin
        compared_cycles<=compared_cycles+1;
'''
    body += f'        if ({{{names}}} !== {{{reference_names}}}) $fatal(1,"Raster cycle mismatch at %0d",compared_cycles);\n'
    body += '''    end
    final $display("RASTER EQUIVALENCE: %0d cycles compared",compared_cycles);
endmodule
`default_nettype wire
'''
    (out/'wrapper.sv').write_text(header+body)
    accel = (ROOT/'tang/rtl/video/gpu_accel.v').read_text()
    assert 'gpu_raster u_raster (' in accel
    (out/'accel.v').write_text(accel.replace('gpu_raster u_raster (', 'gpu_raster_equiv u_raster (', 1))
    sources = ['TESTS/rtl/gpu_accel_tb.sv', 'tang/rtl/video/blitter.v',
               'tang/rtl/video/gpu_raster.v','tang/rtl/video/gpu_v1.v','tang/rtl/video/gpu_texture_cache.v','tang/rtl/video/gpu_copy565.v', 'tang/rtl/video/gpu_perspective.v',
               'tang/rtl/video/gpu_triangle.v', 'tang/rtl/video/gpu_blit_dma.v',
               'tang/rtl/video/font_ram.v', 'tang/rtl/board/ddr_dcfifo.v',
               'tang/rtl/board/cdc_word.v', 'tang/rtl/board/ddr_gpu_arb.v']
    arb_sources, arb_inputs = arbiter_equivalence(ROOT, a.reference_root, out, ROOT/'TESTS/rtl/gpu_accel_tb.sv')
    sources.remove('TESTS/rtl/gpu_accel_tb.sv')
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator', '--binary', '-j', '4', '--timing', '-Wno-fatal',
                        '--top-module', 'gpu_accel_tb', '--Mdir', str(out/'obj')]
                       + [str(ROOT/s) for s in sources]
                       + [str(s) for s in arb_sources]
                       + [str(out/s) for s in ['wrapper.sv', 'reference.v', 'accel.v']],
                       stdout=log, stderr=log, check=True)
    for name in ['commands.hex', 'expected.hex', 'font8x16.hex']:
        shutil.copyfile(a.vectors/name, out/name)
    with (out/'simulation.log').open('w') as log:
        subprocess.run([str(out/'obj/Vgpu_accel_tb'), f'+ncmd={a.commands}',
                        f'+raster_bad={a.raster_bad}', '+rgbinit=1'], cwd=out,
                       stdout=log, stderr=log, check=True)
    log = (out/'simulation.log').read_text()
    cycles = int(re.search(r'RASTER EQUIVALENCE: (\d+) cycles compared', log)[1])
    hashes = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in
              [raster, reference, *arb_inputs, *[out/n for n in ['commands.hex', 'expected.hex']]]}
    result = dict(pass_cycle_equivalence=True, cycles=cycles, commands=a.commands, sha256=hashes)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log, end='')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
