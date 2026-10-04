#!/usr/bin/env python3
"""Reproduce r20's two-enable C-pipeline mapping with Gowin's official model.

The vendor model is read locally, never modified or committed. This is a
localized reproduction, not full post-synthesis equivalence. The fixed case
keeps the second command register in fabric, like gpu_v1.packet.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--netlist', type=Path, required=True, help='frozen r20 synthesis output')
    p.add_argument('--primitives', type=Path, required=True, help='official gw5a/prim_sim.v')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    net = a.netlist.read_text()
    module = re.search(r'^module gpu_copy565\b.*?^endmodule', net, re.M | re.S)[0]
    params = dict(re.findall(r'defparam n421_s1\.(\w+)=([^;]+);', module))
    assert params['C_IREG_CE'] == '"CE0"' and params['C_PREG_CE'] == '"CE1"'
    assert params['C_IREG_CLK'] == params['C_PREG_CLK'] == '"CLK0"'
    ports = re.search(r'MULTALU27X18 n421_s1\s*\((.*?)\n\);', module, re.S)[1]
    assert '.CE({n24958_4,n34082_3})' in ports
    assert 'n2428_2,n2429_1' in ports and 'n2458_1,n2459_1' in ports
    prim = a.primitives.read_text()
    extracted = '\n'.join(re.search(r'^module '+name+r'\b.*?\bendmodule', prim, re.M | re.S)[0]
                          for name in ('MULTALU27X18', 'GSR'))
    (out/'primitives.v').write_text(extracted)
    bench = '''`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,fetch=0,issue=0;reg[31:0] raw=0;
reg[31:0] word1=0,packet1=0;wire[47:0] wrong,fixed;
integer failures=0;
GSR GSR(.GSRI(1'b1));
always #5 clk=~clk;
always @(posedge clk) if(rst)begin word1<=0;packet1<=0;end else begin
 if(fetch)word1<=raw;if(issue)packet1<=word1;end
CELLS
initial begin
 repeat(3)@(negedge clk);rst=0;
 for(integer i=0;i<64;i=i+1)begin
  raw=32'h00800000+i*32'h1000;fetch=1;@(negedge clk);fetch=0;
  raw=32'h019000f0;repeat(6)@(negedge clk);
  raw=32'h1e000000+i;issue=1;@(negedge clk);issue=0;
  repeat(3)@(negedge clk);
  if(wrong!=48'(packet1+832*240))failures=failures+1;
  if(fixed!=48'(packet1+832*240))$fatal(1,"Fixed C path: %h expected %h",fixed,48'(packet1+832*240));
  if(i==0)$display("old=%h fixed=%h expected=%h",wrong,fixed,48'(packet1+832*240));
 end
 if(failures!=64)$fatal(1,"Expected 64 reproductions, got %0d",failures);
 $display("PASS: 64 old mapping failures reproduced; 64 fabric-register cases exact");$finish;
end
endmodule
'''
    cells = []
    for name, c, signal in [('old', 'raw', 'wrong'), ('new', 'packet1', 'fixed')]:
        config = dict(params)
        if name == 'new':
            config['C_IREG_CLK'] = config['C_PREG_CLK'] = '"BYPASS"'
        cells.append(f'''MULTALU27X18 {name}(.A(27'd832),.B(18'd240),.C({{16'd0,{c}}}),.D(26'd0),
 .SIA(27'd0),.CASI(48'd0),.PSEL(1'b0),.ASEL(1'b0),.CSEL(1'b0),.CASISEL(1'b0),
 .PADDSUB(1'b0),.ACCSEL(1'b0),.ADDSUB(2'b0),.CLK({{1'b0,clk}}),
 .CE({{fetch,issue}}),.RESET({{1'b0,rst}}),.DOUT({signal}),.CASO(),.SOA());
'''+ '\n'.join(f'defparam {name}.{k}={v};' for k,v in config.items()))
    # "new" is a SystemVerilog keyword.
    (out/'tb.sv').write_text(bench.replace('CELLS', '\n'.join(cells)).replace('new(', 'fixed_dsp(').replace('new.', 'fixed_dsp.'))
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','--timing','-j','4','-Wno-fatal','--top-module','tb',
                        '--Mdir',str(out/'obj'),str(out/'tb.sv'),str(out/'primitives.v')],stdout=log,stderr=log,check=True)
    run = subprocess.run([str(out/'obj/Vtb')],text=True,capture_output=True,check=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    result = dict(passed=True, reproduced_failures=64, fixed_exact=64,
                  netlist_sha256=hashlib.sha256(a.netlist.read_bytes()).hexdigest(),
                  primitives_sha256=hashlib.sha256(a.primitives.read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(run.stdout, end=''); print(json.dumps(result))


if __name__ == '__main__':
    main()
