#!/usr/bin/env python3
"""Independent event scoreboard, exhaustive address sweeps, real primitives."""
import json
from pathlib import Path
import random
import subprocess
import sys
import prepare_candidate as pc
HERE=Path(__file__).resolve().parent
IV='/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog'
IVLIB='/tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl'
VVP='/tmp/console-usb-sim-tools/extracted/usr/bin/vvp'
PRIM=Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')
MASK=2**32-1

class Reference:
 def __init__(self):self.reset()
 def reset(self):
  self.raw=[0]*3;self.tags=[0]*3;self.count=[0]*3
  self.total=self.frames=self.outside=0
  self.seen=0;self.expected=0;self.last=0;self.lastbusy=0;self.active=0
  self.order=self.duplicate=self.overflow=0
 def step(self,rst,valid,busy,index,word,seq):
  if rst:self.reset();return
  if not valid:return
  self.order|=index!=self.expected
  self.duplicate|=(index==0 and self.active) or (index in (1,2) and bool(self.seen&(1<<index)))
  if index<3:
   self.raw[index]=word;self.tags[index]=seq
   self.overflow|=self.count[index]==MASK;self.count[index]=(self.count[index]+1)&MASK
  self.overflow|=self.total==MASK;self.total=(self.total+1)&MASK
  if index==31:self.overflow|=self.frames==MASK;self.frames=(self.frames+1)&MASK
  if not busy:self.overflow|=self.outside==MASK;self.outside=(self.outside+1)&MASK
  if index==0:self.seen=1
  elif index in (1,2):self.seen|=1<<index
  self.active=int(index!=31);self.expected=(index+1)%32;self.last=index;self.lastbusy=busy
 def read(self,address):
  if address<192 or address%4:return 0,0
  status=(self.lastbusy<<21)|(self.last<<16)|(self.expected<<8)|(int(self.overflow)<<6)|(int(self.duplicate)<<5)|(int(self.order)<<4)|(self.active<<3)|self.seen
  registers=[0x55545731,0x10001,self.raw[0],self.raw[1],self.raw[2],self.raw[1],*self.count,self.total,self.frames,self.outside,status,*self.tags]
  return 1,registers[(address-192)//4]

def vectors(path):
 model=Reference();rows=[];rng=random.Random(0x55545731);phases=[]
 def tick(r=0,v=0,b=1,i=0,w=0,s=0,a=0):
  model.step(r,v,b,i,w,s);hit,data=model.read(a)
  rows.append([r,v,b,i,w,s,a,hit,data])
 def sweep(label):
  phases.append(dict(label=label,start=len(rows)))
  for a in range(256):tick(a=a)
  for a in range(255,-1,-1):tick(a=a)
 tick(r=1);sweep('reset, all 256 byte offsets both orders')
 for seq in range(4):
  for i in range(32):
   for _ in range(rng.randrange(4)):tick(a=rng.randrange(256))
   tick(v=1,i=i,w=[0x55544e41,1,2][i] if i<3 else rng.getrandbits(32),s=seq,a=192+4*rng.randrange(16))
  sweep('complete frame '+str(seq))
 for i in range(2):tick(v=1,i=i,w=0xfac00000+i,s=4)
 sweep('incomplete frame, slot2 stale and different tag')
 tick(r=1,v=1,i=2,w=MASK,s=9);sweep('reset wins over valid')
 for i in range(32):tick(v=1,b=0,i=i,w=0xab000000+i,s=0)
 sweep('all events outside busy are captured and counted')
 tick(r=1)
 for i in [0,1,1,2,0,31]:tick(v=1,i=i,w=i)
 sweep('duplicates and jumps sticky')
 tick(r=1);sweep('reset clears all sticky flags')
 for n in range(6000):
  tick(r=int(rng.randrange(300)==0),v=int(rng.randrange(4)!=0),b=rng.randrange(2),i=rng.randrange(32),w=rng.getrandbits(32),s=rng.getrandbits(32),a=rng.randrange(256))
 sweep('random events and reset phases')
 path.write_text(''.join(' '.join(f'{v:x}' for v in row)+'\n' for row in rows))
 return dict(cycles=len(rows),phases=phases,seed='0x55545731')

TB='''`timescale 1ns/1ps
module tb;
 reg hclk=0,hreset=0,reply_valid=0,busy=0;
 reg [4:0] receive_index=0;
 reg [31:0] reply=0,completed_count=0;
 reg [7:0] address=0;
 wire read_hit; wire [31:0] read_data;
 GSR GSR(.GSRI(1'b1));
 neo_usb_reply_witness dut(.*);
 always #5 hclk=~hclk;
 integer fd,got,n=0,er,ev,eb,ei,ew,es,ea,eh,ed;
 string file;
 initial begin
  if(!$value$plusargs("vectors=%s",file))$fatal(1,"missing vectors");
  fd=$fopen(file,"r");if(!fd)$fatal(1,"open vectors");
  while(!$feof(fd))begin
   got=$fscanf(fd,"%h %h %h %h %h %h %h %h %h\\n",er,ev,eb,ei,ew,es,ea,eh,ed);
   if(got!=9)$fatal(1,"bad vector %0d got%0d",n,got);
   @(negedge hclk);hreset=er[0];reply_valid=ev[0];busy=eb[0];receive_index=ei[4:0];reply=ew;completed_count=es;address=ea[7:0];
   @(posedge hclk);#1;
   if(read_hit!==eh[0] || read_data!==ed)$fatal(1,"vector%0d addr%02h hit%b/%b data%08h/%08h",n,address,read_hit,eh[0],read_data,ed);
   n=n+1;
  end
  $fclose(fd);$display("PASS WITNESS SCOREBOARD cycles=%0d",n);$finish;
 end
 initial begin #2000000;$fatal(1,"deadline");end
endmodule
'''

def compile_run(out,name,source,tb,args=None):
 sim=out/(name+'.vvp');log=out/(name+'_compile.log')
 r=subprocess.run([IV,'-B',IVLIB,'-g2012','-s','tb','-o',str(sim),str(tb),str(source),str(PRIM)],capture_output=True,text=True,timeout=45)
 log.write_text(r.stdout+r.stderr)
 pc.require(r.returncode==0 and not r.stderr,'primitive compile error/warning '+str(log))
 r=subprocess.run([VVP,str(sim)]+(args or []),capture_output=True,text=True,timeout=45)
 (out/(name+'.log')).write_text(r.stdout+r.stderr)
 return dict(name=name,returncode=r.returncode,passed=r.returncode==0 and 'PASS WITNESS' in r.stdout,log=r.stdout)

def main():
 out=pc.new_output(Path(sys.argv[1]));info=vectors(out/'vectors.txt');(out/'tb.sv').write_text(TB)
 sources={'rtl':HERE/'neo_usb_reply_witness.v','mapped':HERE/'mapping_02/helper_mapped.v'}
 results=[]
 for name,source in sources.items():results.append(compile_run(out,name,source,out/'tb.sv',['+vectors='+str(out/'vectors.txt')]))
 # Overflow is unreachable in a short run without injection. Force the
 # already registered counter bus to MAX for one accepted event, then release.
 # This is an explicit synthetic fault/initial-state test, not hardware data.
 for name,source in sources.items():
  for counter,index,busy in [('count0',0,1),('count1',1,1),('count2',2,1),('total',8,1),('frames',31,1),('outside_count',8,0)]:
   overflow_tb='''`timescale 1ns/1ps
module tb;
 reg hclk=0,hreset=1,reply_valid=0,busy=1;reg [4:0] receive_index=0;
 reg [31:0] reply=1,completed_count=0;reg [7:0] address=8'hf0;
 wire read_hit;wire [31:0] read_data;GSR GSR(.GSRI(1'b1));
 neo_usb_reply_witness dut(.*);always #5 hclk=~hclk;
 initial begin
  repeat(2)@(negedge hclk);hreset=0;
  force dut.COUNTER=32'hffffffff;
  reply_valid=1;receive_index=INDEX;busy=BUSY;
  @(posedge hclk);#1;release dut.COUNTER;#1;
  if(dut.COUNTER!==0 || read_data[6]!==1)$fatal(1,"overflow did not wrap/flag");
  @(negedge hclk);reply_valid=0;
  repeat(3)@(negedge hclk);
  if(read_data[6]!==1)$fatal(1,"overflow not sticky");
  hreset=1;@(posedge hclk);#1;if(read_data!==0)$fatal(1,"reset overflow");
  $display("PASS WITNESS OVERFLOW COUNTER");$finish;
 end
endmodule
'''.replace('COUNTER',counter).replace('INDEX',str(index)).replace('BUSY',str(busy))
   if name=='mapped' and counter=='total':
    # Yosys retains this bus under its flattened explicit-register alias.
    overflow_tb=overflow_tb.replace('dut.total','dut.\\r_total.q ')
   tb=out/f'tb_{name}_{counter}.sv';tb.write_text(overflow_tb)
   results.append(compile_run(out,name+'_'+counter,source,tb))
 result=dict(passed=all(x['passed'] for x in results),hardware_access=False,SDF=False,scoreboard=info,cases=results,
  inputs={str(p):pc.sha(p) for p in [Path(__file__),HERE/'prepare_candidate.py',*sources.values(),PRIM]})
 pc.save(out/'result.json',result);print(json.dumps(dict(passed=result['passed'],cases=len(results),cycles=info['cycles'])))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
