#!/usr/bin/env python3
"""Extract actual packet tables from both ELFs and exercise exact R19 GPU RTL."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
RTL=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local/source/tang/rtl/video'
TC=Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin')
IVL=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
LIB=IVL.parents[1]/'lib/x86_64-linux-gnu/ivl'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def packets(build):
    names=subprocess.run([str(TC/'riscv-none-elf-nm'),'-n',str(build/'microdma.elf')],
                         capture_output=True,text=True,check=True,timeout=10).stdout
    symbols={line.split()[2]:int(line.split()[0],16) for line in names.splitlines() if len(line.split())==3}
    data=(build/'microdma.bin').read_bytes()
    return {name:list(struct.unpack_from('<8I',data,symbols[name]-0xa0004000))
            for name in ['target_words','clear_words']}

def main():
    out=HERE/'rtl_payload_02';out.mkdir()
    old=packets(HERE/'build_01');new=packets(HERE/'build_02')
    def sv(words):return '{'+','.join(f"32'h{word:08x}" for word in reversed(words))+'}'
    bench=r'''
`timescale 1ns/1ps
module tb;
 reg clk=0,rst=1,start=0;reg[3:0] child_resetn=0;reg[255:0] command=0;
 wire done,busy,valid,write,target_valid;wire[28:0]addr;
 wire[255:0]data;wire[31:0]mask,rejected;
 integer cycle=0,phase=0,requests=0,waits=0;wire ready=cycle%7==6;
 always #5 clk=~clk;
 gpu_v1 dut(.clk(clk),.rst(rst),.child_resetn(child_resetn),.start(start),.command(command),
 .done(done),.busy(busy),.observe_packet_word0(),.target_config_valid(target_valid),
 .material_config_valid(),.rejected(rejected),.fragments(),.passed(),.texture_hits(),.texture_misses(),
 .valid(valid),.write(write),.addr(addr),.wr_data(data),.wr_mask(mask),.ready(ready),
 .rd_valid(1'b0),.rd_data(256'd0));
 always @(posedge clk)begin
  cycle<=cycle+1;if(cycle>10000)$fatal(1,"RTL timeout");
  if(!rst && valid)begin
   if(phase!=3 && phase!=5)$fatal(1,"Unexpected DMA phase%0d",phase);
   if(!write || addr!==29'h04800008 || data!=={16{16'h6b4d}})
    $fatal(1,"Wrong native footprint");
   if(mask!==(phase==3 ? 32'hfffffffc:32'd0))$fatal(1,"Wrong byte mask");
   if(ready)requests<=requests+1;else waits<=waits+1;
  end
 end
 task send(input[255:0] packet);
  integer n;
  begin @(negedge clk);command=packet;start=1;@(negedge clk);start=0;n=0;
   while(!done && n<1000)begin @(negedge clk);n=n+1;end
   if(!done)$fatal(1,"Command completion timeout");@(negedge clk);
  end
 endtask
 task reset;
  begin @(negedge clk);rst=1;child_resetn=0;repeat(5)@(negedge clk);
   rst=0;child_resetn=15;repeat(5)@(negedge clk);end
 endtask
 initial begin
  reset();phase=1;send(OLD_TARGET);
  if(target_valid || rejected!=1 || requests!=0)$fatal(1,"Old TARGET was not rejected");
  send(OLD_CLEAR);
  if(rejected!=2 || requests!=0)$fatal(1,"CLEAR after invalid TARGET must reject");
  $display("PASS actualBIN01: TARGET rejected, CLEAR rejected, zero DMA");
  reset();phase=2;send(NEW_TARGET);
  if(!target_valid || rejected!=0 || requests!=0)$fatal(1,"New TARGET invalid");
  phase=3;send(OLD_CLEAR);
  if(rejected!=0 || requests!=1)$fatal(1,"Transposed CLEAR clip mismatch");
  $display("PASS transposedCLEAR: valid TARGET16x1 clips rectangle1x16 to1pixel/2bytes");
  reset();phase=4;send(NEW_TARGET);
  if(!target_valid || rejected!=0 || requests!=1)$fatal(1,"New TARGET second control");
  phase=5;send(NEW_CLEAR);
  if(rejected!=0 || requests!=2 || waits==0)$fatal(1,"New CLEAR footprint mismatch");
  phase=6;repeat(15)@(negedge clk);
  if(requests!=2)$fatal(1,"Late duplicate DMA");
  $display("PASS actualBIN02: TARGET valid, CLEAR1nativewrite32bytes, stalls%0d",waits);
  $finish;
 end
endmodule
'''
    for tag,packet in [('OLD_TARGET',old['target_words']),('OLD_CLEAR',old['clear_words']),
                       ('NEW_TARGET',new['target_words']),('NEW_CLEAR',new['clear_words'])]:
        bench=bench.replace(tag,sv(packet))
    source=out/'tb.sv';source.write_text(bench)
    sources=[RTL/(name+'.v') for name in ['gpu_v1','gpu_copy565','gpu_texture_cache','gpu_triangle','gpu_perspective']]
    commands=[[str(IVL),'-B',str(LIB),'-g2012','-s','tb','-o',str(out/'tb.vvp'),str(source),*map(str,sources)],
              [str(IVL.with_name('vvp')),str(out/'tb.vvp')]]
    runs=[]
    for i,command in enumerate(commands):
        run=subprocess.run(command,capture_output=True,text=True,timeout=30)
        log=out/f'{i}.log';log.write_text(run.stdout+run.stderr)
        runs.append(dict(command=command,returncode=run.returncode,log_sha256=sha(log)))
        if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    assert 'PASS actualBIN02:' in run.stdout
    result=dict(passed=True,hardware_access=False,scope='Exact R19 gpu_v1 RTL, packets extracted from exact ELF tables',
        old_packets=old,new_packets=new,runs=runs,
        inputs={str(path):sha(path) for path in [Path(__file__),source,*sources,IVL,IVL.with_name('vvp'),
            HERE/'build_01/microdma.bin',HERE/'build_02/microdma.bin']})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(run.stdout)

if __name__=='__main__':main()
