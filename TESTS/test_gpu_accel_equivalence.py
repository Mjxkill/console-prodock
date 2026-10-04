#!/usr/bin/env python3
"""Compare accelerator AHB responses and every valid DDR request with a frozen integration.

The two integrations share command inputs and DDR acceptance/replies. Idle
payload buses are deliberately unspecified; VALID and all valid transactions,
AHB readiness, read data and the ownership invariant are checked every cycle.
Pixel/guard vectors are checked independently by gpu_accel_tb.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-root', type=Path, required=True)
    p.add_argument('--reference-video', action='store_true',
                   help='also freeze all video children, rather than only the integration')
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--commands', type=int, required=True)
    p.add_argument('--bad', type=int, default=0)
    p.add_argument('--raster-bad', type=int, default=-1)
    p.add_argument('--v1-bad', type=int, default=-1)
    p.add_argument('--v1-pass', type=int, default=-1)
    p.add_argument('--rgbinit', type=int, default=0)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    path = ROOT/'tang/rtl/video/gpu_accel.v'
    reference = a.reference_root/'tang/rtl/video/gpu_accel.v'
    current, old = path.read_text(), reference.read_text()
    declaration = 'module gpu_accel #('
    (out/'current.v').write_text(current.replace(declaration, 'module gpu_accel_current #(', 1))
    video_names=['blitter','gpu_raster','gpu_v1','gpu_texture_cache','gpu_copy565',
                 'gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram']
    reference_sources=[]
    reference_inputs=[]
    if a.reference_video:
        originals={name:(a.reference_root/f'tang/rtl/video/{name}.v') for name in video_names}
        modules=[module for source in originals.values()
                 for module in re.findall(r'^module\s+(\w+)',source.read_text(),re.M)]
        pattern=re.compile(r'\b('+('|'.join(re.escape(n) for n in modules))+r')\b')
        rename=lambda source:pattern.sub(lambda match:match[0]+'_reference',source)
        old=rename(old)
        for name,source in originals.items():
            target=out/f'{name}_reference.v'
            target.write_text(rename(source.read_text()))
            reference_sources.append(target);reference_inputs.append(source)
    (out/'reference.v').write_text(old.replace(declaration, 'module gpu_accel_reference #(', 1))
    header = current[:current.index('    reg [1:0] mrst')]
    inputs = ['hclk', 'hresetn', 'hsel', 'hwrite', 'haddr', 'hwdata', 'htrans',
              'mem_clk', 'ready', 'rd_data', 'rd_valid']
    outputs = dict(hrdata=32, hready=1, valid=1, write=1, addr=29, wr_data=256, wr_mask=32)
    body = ''.join(f'    wire [{width-1}:0] ref_{name};\n' for name, width in outputs.items())
    for typ, prefix in [('current', ''), ('reference', 'ref_')]:
        ports = [f'.{name}({name})' for name in inputs]
        ports += [f'.{name}({prefix}{name})' for name in outputs]
        body += f'    gpu_accel_{typ} #(.FONT_FILE(FONT_FILE)) u_{typ} ('+', '.join(ports)+');\n'
    body += '''
    integer ahb_cycles=0,ddr_cycles=0,transactions=0;
    reg [255:0] previous_raster_command;
    always @(posedge mem_clk) previous_raster_command<=u_current.ext_command;
    always @(posedge hclk) if(hresetn)begin
        ahb_cycles<=ahb_cycles+1;
        if({hready,hrdata} !== {ref_hready,ref_hrdata})
            $fatal(1,"AHB integration mismatch at %0d",ahb_cycles);
    end
    always @(posedge mem_clk) if(u_current.mrst[1])begin
        ddr_cycles<=ddr_cycles+1;
        if(!$onehot(u_current.u_raster.state))
            $fatal(1,"Raster state is not one-hot");
        if(!$onehot0({u_current.u_blitter.rectangle_opcode,u_current.u_blitter.line_opcode,
                      u_current.u_blitter.circle_opcode,u_current.u_blitter.triangle_opcode,
                      u_current.u_blitter.affine_setup_opcode,u_current.u_blitter.extended_opcode}))
            $fatal(1,"Blitter command classes overlap");
        if(u_current.u_raster.start && u_current.ext_command !== previous_raster_command)
            $fatal(1,"Raster command changed without a predecode cycle");
        if(valid !== ref_valid)$fatal(1,"DDR request cycle mismatch at %0d",ddr_cycles);
        if(valid)begin
            if({write,addr} !== {ref_write,ref_addr})
                $fatal(1,"DDR request mismatch at %0d",ddr_cycles);
            if(write && {wr_data,wr_mask} !== {ref_wr_data,ref_wr_mask})
                $fatal(1,"DDR write payload mismatch at %0d",ddr_cycles);
            if(ready)transactions<=transactions+1;
        end
        if(!$onehot0({u_current.legacy_valid,u_current.raster_valid,u_current.v1_valid}))
            $fatal(1,"Concurrent graphics engines at %0d",ddr_cycles);
    end
    final $display("ACCEL EQUIVALENCE: AHB=%0d DDR=%0d transactions=%0d",ahb_cycles,ddr_cycles,transactions);
endmodule
`default_nettype wire
'''
    (out/'wrapper.sv').write_text(header+body)
    bench = ROOT/'TESTS/rtl/gpu_accel_tb.sv'
    (out/'bench.sv').write_text(bench.read_text().replace('dut.', 'dut.u_current.'))
    sources = [out/'bench.sv']
    sources += [ROOT/f'tang/rtl/video/{s}.v' for s in video_names]
    sources += reference_sources
    sources += [ROOT/f'tang/rtl/board/{s}.v' for s in ['ddr_dcfifo','cdc_word','ddr_gpu_arb']]
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','-j','4','--timing','-Wno-fatal',
                        '--top-module','gpu_accel_tb','--Mdir',str(out/'obj')]
                       +[str(s) for s in sources]
                       +[str(out/s) for s in ['current.v','reference.v','wrapper.sv']],
                       stdout=log,stderr=log,check=True)
    for name in ['commands.hex','expected.hex','font8x16.hex']+(['initial.hex'] if a.rgbinit==3 else []):
        shutil.copyfile(a.vectors/name,out/name)
    with (out/'simulation.log').open('w') as log:
        subprocess.run([str(out/'obj/Vgpu_accel_tb'),f'+ncmd={a.commands}',f'+bad={a.bad}',
                        f'+raster_bad={a.raster_bad}',f'+v1_bad={a.v1_bad}',
                        f'+v1_pass={a.v1_pass}',f'+rgbinit={a.rgbinit}'],
                       cwd=out,stdout=log,stderr=log,check=True)
    log = (out/'simulation.log').read_text()
    match = re.search(r'ACCEL EQUIVALENCE: AHB=(\d+) DDR=(\d+) transactions=(\d+)',log)
    if not match:raise RuntimeError('Missing cycle comparison result')
    files=[path,reference,bench,*sources,*reference_inputs,out/'commands.hex',out/'expected.hex']
    result=dict(pass_cycle_equivalence=True,ahb_cycles=int(match[1]),ddr_cycles=int(match[2]),
                transactions=int(match[3]),commands=a.commands,reference_video=a.reference_video,
                sha256={str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in files})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(log,end='')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'}))


if __name__ == '__main__':main()
