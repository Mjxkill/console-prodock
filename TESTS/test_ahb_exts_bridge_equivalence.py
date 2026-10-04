#!/usr/bin/env python3
"""Compare all public bridge outputs every cycle, with traffic, stalls and resets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    current=ROOT/'tang/rtl/board/ahb_exts_bridge.v'
    (out/'current.v').write_bytes(current.read_bytes())
    (out/'reference.v').write_text(a.reference.read_text().replace('module ahb_exts_bridge (','module bridge_reference (',1))
    ports=dict(m_hrdata=32,m_hready=1,s_hsel=2,s_htrans=2,s_hwrite=1,s_haddr=32,s_hwdata=32)
    inputs='hclk,hresetn,m_hsel,m_haddr,m_htrans,m_hwrite,m_hwdata,s0_hrdata,s0_hready,s1_hrdata,s1_hready'.split(',')
    cells=''.join(f'wire [{bits-1}:0] ref_{name};\n' for name,bits in ports.items())
    for module,name,prefix in [('ahb_exts_bridge','dut',''),('bridge_reference','ref_dut','ref_')]:
        connections=[f'.{n}({n})' for n in inputs]+[f'.{n}({prefix}{n})' for n in ports]
        cells+=module+' '+name+'('+','.join(connections)+');\n'
    left='{'+','.join(ports)+'}';right='{'+','.join('ref_'+n for n in ports)+'}'
    bench='''`timescale 1ns/1ps
module tb;
reg hclk=0,hresetn=0,m_hsel=0,m_hwrite=0,s0_hready=0,s1_hready=0;
reg[31:0] m_haddr=0,m_hwdata=0,s0_hrdata=0,s1_hrdata=0;
reg[1:0] m_htrans=0;
wire[31:0] m_hrdata,s_haddr,s_hwdata;
wire m_hready,s_hwrite;wire[1:0]s_hsel,s_htrans;
CELLS
always #6.25 hclk=~hclk;
integer cycles=0,accepted=0,issued=0,cancelled=0;
reg pending=0,expect_issue=0,expected_wr=0;
reg[31:0] expected_addr=0,expected_data=0;
always @(posedge hclk)begin
 if(!hresetn)begin
  if(pending)cancelled=cancelled+1;
  pending<=0;expect_issue<=0;
 end else begin
  expect_issue<=pending;
  if(pending)expected_data<=m_hwdata;
  pending<=m_hready && m_hsel && m_htrans[1];
  if(m_hready && m_hsel && m_htrans[1])begin
   expected_addr<=m_haddr;expected_wr<=m_hwrite;accepted=accepted+1;
  end
 end
end
always @(negedge hclk)begin
 if(LEFT!==RIGHT)$fatal(1,"Bridge output/cycle mismatch at %0d",cycles);
 if(expect_issue)begin
  if(s_hsel!==(expected_addr[24]?2'b10:2'b01) || s_htrans!==2'b10 ||
     s_haddr!==expected_addr || s_hwrite!==expected_wr || s_hwdata!==expected_data)
   $fatal(1,"Accepted payload mismatch at %0d",cycles);
  issued=issued+1;
 end else if(s_hsel!=0)$fatal(1,"Unaccepted request replayed");
end
initial begin
 repeat(4)@(negedge hclk);
 for(integer i=0;i<250000;i=i+1)begin
  #1;hresetn=(i%997!=0);m_hsel=$urandom_range(0,3)!=0;
  m_htrans=$urandom_range(0,3);m_hwrite=$urandom_range(0,1);
  m_haddr=$urandom;m_hwdata=$urandom;
  s0_hrdata=$urandom;s1_hrdata=$urandom;
  s0_hready=$urandom_range(0,7)==0;s1_hready=$urandom_range(0,3)==0;
  cycles=cycles+1;@(negedge hclk);
 end
 #1;hresetn=0;repeat(4)@(negedge hclk);
 #1;if(accepted!=issued+cancelled)$fatal(1,"Request accounting %0d/%0d/%0d",accepted,issued,cancelled);
 $display("PASS: %0d cycles, %0d accepted, %0d issued, %0d cancelled before issue by reset; every public output exact",cycles,accepted,issued,cancelled);
 $finish;
end
endmodule
'''.replace('CELLS',cells).replace('LEFT',left).replace('RIGHT',right)
    (out/'tb.sv').write_text(bench)
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','-j','4','--timing','-Wno-fatal','--top-module','tb','--Mdir',str(out/'obj')]
                       +[str(out/f) for f in ('tb.sv','current.v','reference.v')],stdout=log,stderr=log,check=True)
    run=subprocess.run([str(out/'obj/Vtb')],capture_output=True,text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr);print(run.stdout,end='');run.check_returncode()
    result=dict(passed=True,cycles=250000,reference_sha256=hashlib.sha256(a.reference.read_bytes()).hexdigest(),
                current_sha256=hashlib.sha256(current.read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
