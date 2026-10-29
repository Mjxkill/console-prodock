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
    p.add_argument('--current-root', type=Path, default=ROOT)
    p.add_argument('--reference-video', action='store_true',
                   help='also freeze all video children, rather than only the integration')
    p.add_argument('--reference-self-ready', action='store_true',
                   help='compare old HREADY-masked HSEL with a pending address during each stall')
    p.add_argument('--sweep-registers', action='store_true',
                   help='read all 256 byte addresses after drawing, including holes and unaligned addresses')
    p.add_argument('--check-shader-phase', action='store_true',
                   help='compare retained shader read enable with the reference state decode on every DDR cycle')
    p.add_argument('--check-local-payloads', action='store_true',
                   help='compare prefetched clip operands at each consumption state with the retained reference operands')
    p.add_argument('--check-bounds-prefetch', action='store_true',
                   help='compare prefetched clipping coefficients on every multiplication cycle')
    p.add_argument('--check-command-prefetch', action='store_true',
                   help='compare captured command and mesh bounds on every non-idle geometry cycle')
    p.add_argument('--check-shader-inputs', action='store_true',
                   help='compare private texture coordinates and rounded alpha at consumption')
    p.add_argument('--short-command-stream', action='store_true',
                   help='For at most 16 commands only: FIFO saturation is not required; all memory checks remain')
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--commands', type=int, required=True)
    p.add_argument('--bad', type=int, default=0)
    p.add_argument('--raster-bad', type=int, default=-1)
    p.add_argument('--v1-bad', type=int, default=-1)
    p.add_argument('--v1-pass', type=int, default=-1)
    p.add_argument('--no-texture-expected', action='store_true',
                   help='Require zero cache hits/misses for a pixel test without texture commands; normal cache coverage stays enabled')
    p.add_argument('--rgbinit', type=int, default=0)
    a = p.parse_args()
    if a.short_command_stream and not 1 <= a.commands <= 16:
        p.error('--short-command-stream is restricted to 1..16 commands')
    if a.v1_bad >= 0 and a.v1_pass < 0:
        p.error('--v1-bad also requires --v1-pass: the shared bench checks both counters')
    if a.no_texture_expected and a.v1_bad < 0:
        p.error('--no-texture-expected requires explicit V1 counter checks')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    path = a.current_root/'tang/rtl/video/gpu_accel.v'
    reference = a.reference_root/'tang/rtl/video/gpu_accel.v'
    current, old = path.read_text(), reference.read_text()
    declaration = 'module gpu_accel #('
    (out/'current.v').write_text(current.replace(declaration, 'module gpu_accel_current #(', 1))
    video_names=['gpu_geometry','gpu_geom_div','blitter','gpu_raster','gpu_v1','gpu_texture_cache','gpu_copy565',
                 'gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram']
    reference_sources=[]
    reference_inputs=[]
    if a.reference_video:
        originals={name:(a.reference_root/f'tang/rtl/video/{name}.v') for name in video_names if (a.reference_root/f'tang/rtl/video/{name}.v').exists()}
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
        actual = {name: name for name in inputs}
        if a.reference_self_ready:
            # Présenter une nouvelle adresse tant que la précédente attend :
            # l'ancien top masque HSEL, le nouveau laisse le GPU ignorer
            # cette adresse grâce à son HREADY local. Aucun transfert ajouté.
            actual.update(hsel='hsel || !hready', haddr="hready ? haddr : 32'h10",
                          htrans="hready ? htrans : 2'b10", hwrite="hready ? hwrite : 1'b1")
            if typ == 'reference':
                actual['hsel'] = '(hsel || !hready) && ref_hready'
        ports = [f'.{name}({actual[name]})' for name in inputs]
        ports += [f'.{name}({prefix}{name})' for name in outputs]
        body += f'    gpu_accel_{typ} #(.FONT_FILE(FONT_FILE)) u_{typ} ('+', '.join(ports)+');\n'
    body += '''
    integer ahb_cycles=0,ddr_cycles=0,transactions=0,self_stalls=0;
    reg [255:0] previous_raster_command;
    always @(posedge mem_clk) previous_raster_command<=u_current.ext_command;
    always @(posedge hclk) if(hresetn)begin
        ahb_cycles<=ahb_cycles+1;
        if(!hready)self_stalls<=self_stalls+1;
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
        // v1_valid is the shared extended-engine transaction buffer, so it
        // may overlap the raster request that fills it. Compare the two
        // actual engine requests, and separately the two native DMA owners.
        if(!$onehot0({u_current.legacy_valid,u_current.raster_valid,u_current.v1_request}) ||
           !$onehot0({u_current.legacy_valid,u_current.v1_valid}))
            $fatal(1,"Concurrent graphics engines at %0d",ddr_cycles);
    end
    final $display("ACCEL EQUIVALENCE: AHB=%0d DDR=%0d transactions=%0d",ahb_cycles,ddr_cycles,transactions);
    final $display("ACCEL SELF STALLS: %0d",self_stalls);
endmodule
`default_nettype wire
'''
    if a.check_shader_phase:
        body=body.replace('        ddr_cycles<=ddr_cycles+1;', '''        ddr_cycles<=ddr_cycles+1;
        if(u_current.u_v1.shader_read_enable !==
           (u_reference.u_v1.state[1] || u_reference.u_v1.state[33] ||
            u_reference.u_v1.state[40] || u_reference.u_v1.state[42] || u_reference.u_v1.state[46]))
            $fatal(1,"Shader read phase changed at DDR cycle %0d",ddr_cycles);''',1)
    if a.check_bounds_prefetch:
        body=body.replace('        ddr_cycles<=ddr_cycles+1;', '''        ddr_cycles<=ddr_cycles+1;
        if(u_current.u_v1.state[63] &&
           {u_current.u_v1.bounds_ratio0,u_current.u_v1.bounds_ratio1} !==
           {u_reference.u_v1.bounds_ratio0,u_reference.u_v1.bounds_ratio1})
            $fatal(1,"Clipping coefficients differ on multiplication cycle");''',1)
    if a.check_command_prefetch:
        body=body.replace('        ddr_cycles<=ddr_cycles+1;', '''        ddr_cycles<=ddr_cycles+1;
        if(!u_current.u_v1.state[0] &&
           {u_current.u_v1.captured_command,u_current.u_v1.mesh_vertex_end,u_current.u_v1.mesh_face_end} !==
           {u_reference.u_v1.captured_command,u_reference.u_v1.mesh_vertex_end,u_reference.u_v1.mesh_face_end})
            $fatal(1,"Prefetched command changed during a busy geometry cycle");''',1)
    if a.check_shader_inputs:
        body=body.replace('        ddr_cycles<=ddr_cycles+1;', '''        ddr_cycles<=ddr_cycles+1;
        if(u_current.u_v1.u_pixels.state[53] &&
           {u_current.u_v1.u_pixels.tex_u,u_current.u_v1.u_pixels.tex_v} !==
           {u_reference.u_v1.u_pixels.tex_u,u_reference.u_v1.u_pixels.tex_v})
            $fatal(1,"Texture coordinates differ at consumption");
        if(u_current.u_v1.u_pixels.state[22] &&
           u_current.u_v1.u_pixels.rounded_alpha !== u_reference.u_v1.u_pixels.alpha_product[16:8])
            $fatal(1,"Rounded alpha differs at consumption");''',1)
    if a.check_local_payloads:
        # DDR data in disabled byte lanes is private. Keep the mask, request
        # cycles, addresses and every enabled byte exact; the independent
        # image/guard oracle still compares the full resulting memory.
        body=body.replace('''            if(write && {wr_data,wr_mask} !== {ref_wr_data,ref_wr_mask})
                $fatal(1,"DDR write payload mismatch at %0d",ddr_cycles);''','''            if(write)begin
                if(wr_mask !== ref_wr_mask)$fatal(1,"DDR write mask mismatch");
                for(integer b=0;b<32;b++)if(!wr_mask[b] && wr_data[b*8+:8] !== ref_wr_data[b*8+:8])
                    $fatal(1,"Enabled DDR byte %0d differs at cycle %0d",b,ddr_cycles);
            end''',1)
        body=body.replace('        ddr_cycles<=ddr_cycles+1;', '''        ddr_cycles<=ddr_cycles+1;
        if(u_current.u_v1.state[56] &&
           {u_current.u_v1.clip_z0,u_current.u_v1.clip_z1,u_current.u_v1.clip_side0,u_current.u_v1.clip_side1,
            u_current.u_v1.clip_distance_product0,u_current.u_v1.clip_distance_product1} !==
           {u_reference.u_v1.clip_z0,u_reference.u_v1.clip_z1,u_reference.u_v1.clip_side0,u_reference.u_v1.clip_side1,
            u_reference.u_v1.clip_distance_product0,u_reference.u_v1.clip_distance_product1})
            $fatal(1,"Clip distance operands differ at consumption");
        if(u_current.u_v1.state[22] &&
           {u_current.u_v1.edge_a,u_current.u_v1.edge_b} !==
           {u_reference.u_v1.edge_a,u_reference.u_v1.edge_b})
            $fatal(1,"Clip edge operands differ at consumption");''',1)
    (out/'wrapper.sv').write_text(header+body)
    bench = ROOT/'TESTS/rtl/gpu_accel_tb.sv'
    bench_text = bench.read_text().replace('dut.', 'dut.u_current.')
    if a.short_command_stream:
        old='if(stalls==0 || full_writes<100 || cpu_reads<100 || scan_reads<100)'
        if bench_text.count(old)!=1:raise RuntimeError('Unknown coverage assertion')
        bench_text=bench_text.replace(old,'if(full_writes<100 || cpu_reads<100 || scan_reads<100)',1)
    if a.sweep_registers:
        marker = '        $display("PASS: %0d commands'
        if bench_text.count(marker) != 1:
            raise RuntimeError('Register sweep insertion point missing or ambiguous')
        bench_text = bench_text.replace(marker,
            '        for(integer byte_address=0;byte_address<256;byte_address++) read_reg(byte_address,value);\n'
            '        $display("ACCEL REGISTER SWEEP: 256");\n' + marker)
    (out/'bench.sv').write_text(bench_text)
    sources = [out/'bench.sv']
    sources += [a.current_root/f'tang/rtl/video/{s}.v' for s in video_names]
    sources += reference_sources
    sources += [a.current_root/f'tang/rtl/board/{s}.v' for s in ['ddr_dcfifo','cdc_word','ddr_gpu_arb']]
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
                        f'+v1_pass={a.v1_pass}',f'+v1_texture={int(not a.no_texture_expected)}',f'+rgbinit={a.rgbinit}'],
                       cwd=out,stdout=log,stderr=log,check=True)
    log = (out/'simulation.log').read_text()
    match = re.search(r'ACCEL EQUIVALENCE: AHB=(\d+) DDR=(\d+) transactions=(\d+)',log)
    if not match:raise RuntimeError('Missing cycle comparison result')
    stalls = int(re.search(r'ACCEL SELF STALLS: (\d+)', log)[1])
    if a.reference_self_ready and not stalls:
        raise RuntimeError('Self-ready comparison did not exercise an HSEL stall')
    if a.sweep_registers and 'ACCEL REGISTER SWEEP: 256' not in log:
        raise RuntimeError('Register sweep did not complete')
    files=[path,reference,bench,*sources,*reference_inputs,out/'commands.hex',out/'expected.hex']
    result=dict(pass_cycle_equivalence=True,ahb_cycles=int(match[1]),ddr_cycles=int(match[2]),
                transactions=int(match[3]),commands=a.commands,reference_video=a.reference_video,
                reference_self_ready=a.reference_self_ready,self_stalls=stalls,
                shader_phase_checked=a.check_shader_phase,
                bounds_prefetch_checked=a.check_bounds_prefetch,
                shader_inputs_checked=a.check_shader_inputs,
                command_prefetch_checked=a.check_command_prefetch,
                local_payloads_checked=a.check_local_payloads,
                masked_write_bytes_compared=not a.check_local_payloads,
                fifo_saturation_required=not a.short_command_stream,
                texture_activity_expected=not a.no_texture_expected,
                register_addresses=256 if a.sweep_registers else 0,
                sha256={str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in files})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(log,end='')
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'}))


if __name__ == '__main__':main()
