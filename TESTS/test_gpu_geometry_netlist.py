#!/usr/bin/env python3
"""Check the frozen synthesized geometry with official Gowin primitive models.

The pixel backend is a completion stub: every emitted raster command is checked
against an existing independent world reference. This tests mapped DSP/BSRAM
geometry, not pixel execution, physical delays or complete-chip equivalence.
Vendor models and extracted netlists stay in a temporary directory.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PRIMITIVES = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')


def module(text, name):
    return re.search(r'^module '+re.escape(name)+r'\b.*?^endmodule[^\n]*', text, re.M | re.S)[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--iverilog', type=Path, default=Path(shutil.which('iverilog') or '/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog'))
    a = p.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    stage = a.stage.resolve(); reference = a.reference.resolve()
    expected = json.loads((reference/'result.json').read_text())
    if expected['status']!='PASS' or not expected['world'] or expected['invalid_commands']:
        raise RuntimeError('Use a valid world reference; the pixel stub does not validate descriptors')
    netlist = stage/f'impl/gwsynthesis/console_{stage.name}.vg'
    text = netlist.read_text()
    mapped = '\n'.join(module(text, n) for n in ('gpu_geometry', 'gpu_geom_div', 'gpu_geom_div_0'))
    pixel = module(text, 'gpu_v1')
    declarations = re.findall(r'^(?:input|output) [^;]+;', pixel, re.M)
    outputs = [re.sub(r'^output\s*(?:\[[^]]+\])?\s*', '', d)[:-1].strip()
               for d in declarations if d.startswith('output ')]
    inputs = {re.sub(r'^input\s*(?:\[[^]]+\])?\s*', '', d)[:-1].strip()
              for d in declarations if d.startswith('input ')}
    # Gowin can move a pure geometry control cone across the pixel hierarchy.
    # Preserve that exact LUT cone instead of tying its exported result low.
    boundary_cells = {}
    def boundary(signal):
        if signal in inputs or signal in boundary_cells:return
        found = re.search(r'^  LUT\d+ \w+ \(\n\s*\.F\('+re.escape(signal)+r'\).*?^\);\n(?:defparam [^\n]+;\n)+',pixel,re.M|re.S)
        if not found:raise RuntimeError('Unsupported optimized boundary: '+signal)
        cell = found[0]
        for dependency in re.findall(r'\.I\d+\((\w+)\)',cell):boundary(dependency)
        boundary_cells[signal] = cell
    stub = pixel[:pixel.index('input ')]+'\n'.join(declarations)+'\n'
    for name in outputs:
        if re.fullmatch(r'n\d+_\d+',name):
            boundary(name)
            continue
        value = 'completion' if name == 'shader_done' else "1'b1" if name in ('shader_target_valid', 'shader_material_valid') else "'0"
        stub += f'assign {name} = {value};\n'
    for name,cell in boundary_cells.items():
        if name not in outputs:stub += f'wire {name};\n'
        stub += cell
    stub += '''reg [3:0] delay_count=0;reg completion=0;
always @(posedge gpu_clk)begin
 completion<=0;
 if(!engine_resetn)delay_count<=0;
 else if(shader_start)delay_count<=7;
 else if(delay_count!=0)begin delay_count<=delay_count-1'b1;if(delay_count==1)completion<=1;end
end
endmodule
'''
    prim_text = PRIMITIVES.read_text()
    primitive_names = set(re.findall(r'^module (\w+)', prim_text, re.M))
    needed = set(re.findall(r'^\s+(\w+)\s+\\?\S+\s*\(', mapped, re.M)) & primitive_names
    needed.add('GSR')
    while True:
        dependencies = set()
        for name in needed:
            dependencies.update(re.findall(r'^\s*(\w+)\s+\w+\s*\(',module(prim_text,name),re.M))
        expanded = needed | (dependencies & primitive_names)
        if expanded == needed:break
        needed = expanded
    primitive_modules = '`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',prim_text,re.M|re.S))+'\n'
    primitive_modules += '\n'.join(module(prim_text, n) for n in sorted(needed))
    bench = r'''`timescale 1ns/1ps
module tb;
reg clk=0,resetn=0,start=0,accepted=0,rv=0;
reg [255:0] packet=0,rd=0;
wire done,fetch;
wire [28:0] fetch_address;
wire [31:0] errors,vertices,triangles,culled,clipped,slivers;
wire [255:0] observed_shader=dut.shader_command & 256'hSHADER_MASK;
GSR GSR(.GSRI(1'b1));
always #6.666 clk=~clk;
gpu_geometry dut(.gpu_clk(clk),.engine_resetn(resetn),.v1_select(1'b1),.ext_start_Z(start),
 .v1_accepted(accepted),.v1_rx_valid(rv),.ext_command(packet),.v1_rx_data(rd),
 .v1_done(done),.fetch_valid(fetch),FETCH_PORTS
 .\geometry_stat[0] (errors),.\geometry_stat[1] (vertices),.\geometry_stat[2] (triangles),
 .\geometry_stat[3] (culled),.\geometry_stat[4] (clipped),.\geometry_stat[5] (slivers));
assign fetch_address[23:3]=dut.fetch_addr_3;
assign fetch_address[28]=0;
reg [7:0] memory[0:3145727];
reg [31:0] commands[0:CPU_WORDS-1],shader[0:SHADER_WORDS-1];
integer word_index=0,reads=0,cycle=0,pending=0,byte_address=0,active_command=-1,command_start=0;
function automatic integer index(input integer address);
 if(address>='h1700000 && address<'h1800000)return 2097152+address-'h1700000;
 $fatal(1,"Unexpected mesh read %h",address);return 0;
endfunction
always @(negedge clk)begin
 cycle++;accepted=0;rv=0;
 if(resetn)begin
  if(pending!=0)begin
   pending--;
   if(pending==0)begin rv=1;for(integer b=0;b<32;b++)rd[b*8+:8]=memory[index(byte_address+b)];end
  end else if(fetch && cycle%5!=0)begin
   accepted=1;byte_address=int'(fetch_address)*4;pending=11+cycle%13;reads++;
  end
 end
end
always @(posedge clk)if(resetn && dut.shader_start)begin
 for(integer w=0;w<8;w++)begin
  if(word_index>=SHADER_WORDS || observed_shader[w*32+:32]!==shader[word_index])
   $fatal(1,"Mapped shader command %0d word %0d got=%h expected=%h",word_index/8,w,observed_shader[w*32+:32],shader[word_index]);
  word_index++;
 end
end
always @(posedge clk)if(resetn && active_command>=0 && cycle-command_start>200000)
 $fatal(1,"Mapped command timeout command=%0d op=%h state=%h shader=%0d reads=%0d",active_command,packet[31:24],dut.state,word_index/8,reads);
initial begin
 $readmemh("REFERENCE/initial.hex",memory);
 $readmemh("REFERENCE/commands.hex",commands);
 $readmemh("REFERENCE/shader.hex",shader);
 repeat(8)@(negedge clk);resetn=1;repeat(4)@(negedge clk);
 for(integer c=0;c<CPU_WORDS/8;c++)begin
  active_command=c;command_start=cycle;
  for(integer w=0;w<8;w++)packet[w*32+:32]=commands[c*8+w];
  start=1;@(negedge clk);start=0;
  wait(done);@(negedge clk);repeat(3)@(negedge clk);
  if(c%64==0)begin $display("MAPPED command=%0d shader=%0d cycles=%0d",c,word_index/8,cycle);$fflush();end
 end
 active_command=-1;
 if(word_index!=SHADER_WORDS || errors!=0 || vertices!=VERTICES || triangles!=TRIANGLES || culled!=CULLED || clipped!=CLIPPED || slivers!=SLIVERS)
  $fatal(1,"Mapped counters words=%0d err=%0d v=%0d t=%0d c=%0d clip=%0d sliver=%0d",word_index,errors,vertices,triangles,culled,clipped,slivers);
 $display("PASS: synthesized geometry %0d commands, %0d shader commands exact, %0d mesh reads",CPU_WORDS/8,SHADER_WORDS/8,reads);$finish;
end
initial begin #20000000;$fatal(1,"Mapped geometry timeout state=%h",dut.state);end
endmodule
'''
    bench = bench.replace('FETCH_PORTS', ','.join(f'.fetch_addr_{b}(fetch_address[{b}])' for b in (0,1,2,24,25,26,27))+',')
    mask = sum(1<<int(n) for n in re.findall(r'^input shader_command_(\d+);',pixel,re.M))
    oracle = [int(w,16) for w in (reference/'shader.hex').read_text().split()]
    for i,word in enumerate(oracle):
        if word & ~((mask>>(32*(i%8)))&0xffffffff):
            raise RuntimeError('Reference uses optimized-away shader bits')
    replacements = dict(SHADER_MASK=f'{mask:064x}', REFERENCE=str(reference), CPU_WORDS=expected['input_commands']*8,
                        SHADER_WORDS=expected['shader_commands']*8, VERTICES=expected['vertices'],
                        TRIANGLES=expected['triangles'], CULLED=expected['culled'], CLIPPED=expected['clipped'], SLIVERS=expected['slivers'])
    for key, value in replacements.items():
        bench = bench.replace(key, str(value))
    (out/'bench.sv').write_text(bench)
    with tempfile.TemporaryDirectory(prefix='gpu_geometry_netlist_') as temporary:
        work = Path(temporary)
        (work/'mapped.v').write_text(mapped+'\n'+stub)
        (work/'primitives.v').write_text(primitive_modules)
        compiler = a.iverilog.resolve(strict=True)
        library = compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
        flags = ['-B',str(library)] if library.is_dir() else []
        with (out/'build.log').open('w') as log:
            subprocess.run([str(compiler),*flags,'-g2012','-s','tb','-o',str(work/'simulation.vvp'),
                            str(out/'bench.sv'),str(work/'mapped.v'),str(work/'primitives.v')],
                           stdout=log,stderr=log,check=True)
        with (out/'simulation.log').open('w') as log:
            # Official gate models run at only a few hundred simulated clocks
            # per second here. Keep the cycle watchdogs, but allow all three
            # views to finish instead of treating normal progress as a failure.
            run = subprocess.run([str(compiler.parent/'vvp'),str(work/'simulation.vvp')],stdout=log,stderr=log,timeout=7200)
        print((out/'simulation.log').read_text(),flush=True)
        run.check_returncode()
    result = dict(status='PASS', scope='synthesized geometry; stubbed pixel completion; exact shader commands',
                  netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
                  primitives_sha256=hashlib.sha256(PRIMITIVES.read_bytes()).hexdigest(), primitive_types=sorted(needed),
                  reference=str(reference), commands=expected['input_commands'], shader_commands=expected['shader_commands'],
                  shader_observed_mask=f'{mask:064x}',boundary_cones=sorted(boundary_cells),
                  reference_sha256={n:hashlib.sha256((reference/n).read_bytes()).hexdigest() for n in ('initial.hex','commands.hex','shader.hex','result.json')})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
