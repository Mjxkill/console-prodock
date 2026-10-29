#!/usr/bin/env python3
"""Mapped R19 observer+FIFO versus exact baseline, and boundary fault models."""
import json
from pathlib import Path
import re
import subprocess
import sys
import prepare_candidate as pc
from test_helper import IV,IVLIB,VVP,PRIM
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREV=ROOT/'TESTS/neo_common_cause_20261027/utna_header_netlist_01'

EXTRA='''
 integer mode=0;
 initial if($value$plusargs("mode=%d",mode))begin end
 // Injection 1 zeroes the already read reply bit presented to BOTH bank and
 // witness at index1. It is a boundary fault model, not an identified FIFO bug.
 always @(negedge hclk)begin
  if(mode==1 && dut.reply_valid && dut.receive_index==1)begin
   force dut.reply[0]=1'b0;force base.reply[0]=1'b0;
  end else begin release dut.reply[0];release base.reply[0];end
 end
 initial begin
  #200;
  // Injection 2 changes only the bank lane1 validity result, downstream from
  // the witness. RAM contents are not claimed to be physically faulty.
  if(mode==2)begin force dut.bank_ER_RS_87=1'b0;force base.bank_ER_RS_87=1'b0;end
 end
 always @(negedge hclk)begin
  if(reset_n && !dut.hreset)begin
   if({dut.reply_valid,dut.reply,dut.busy,dut.receive_index,dut.snapshot_count,read_pending_net} !==
      {base.reply_valid,base.reply,base.busy,base.receive_index,base.snapshot_count,base_read_pending})
    $fatal(1,"witness altered original control or data");
  end
 end
 task witness_check(input [31:0] command_value,input [31:0] sequence_value);
  reg [31:0] v,alias_value;
  bus_read('hc0,v);if(v!==32'h55545731)$fatal(1,"witness ID");
  bus_read('hc4,v);if(v!==32'h00010001)$fatal(1,"witness ABI");
  bus_read('hc8,v);if(v!==32'h55544e41)$fatal(1,"raw0");
  bus_read('hcc,v);if(v!==(mode==1?32'd0:32'd1))$fatal(1,"raw1 boundary");
  bus_read('hd4,alias_value);if(v!==alias_value)$fatal(1,"raw1 alias");
  bus_read('hd0,v);if(v!==command_value)$fatal(1,"raw2");
  for(integer a='hd8;a<='he0;a=a+4)begin bus_read(a,v);if(v!==sequence_value)$fatal(1,"slot count addr%h",a);end
  bus_read('he4,v);if(v!==sequence_value*32)$fatal(1,"event count");
  bus_read('he8,v);if(v!==sequence_value)$fatal(1,"frame count");
  bus_read('hec,v);if(v!==0)$fatal(1,"outside busy");
  bus_read('hf0,v);if(v!==32'h003f0007)$fatal(1,"completion status %h",v);
  for(integer a='hf4;a<='hfc;a=a+4)begin bus_read(a,v);if(v!==sequence_value-1)$fatal(1,"slot tag");end
  $display("WITNESS mode=%0d seq=%0d command=%0d bank1=%h raw1=%h status=%h",mode,sequence_value,command_value,words[1],alias_value,32'h003f0007);
 endtask
 task sweep_byte_addresses;
  reg [31:0] v;
  for(integer a=0;a<256;a=a+1)begin
   bus_read(a,v);
   if(a>=192 && (a%4)!=0 && v!==0)$fatal(1,"unaligned witness address aliased %h",a);
  end
 endtask
 task zero_witness_state;
  reg [31:0] v;
  for(integer a='hc8;a<256;a=a+4)begin bus_read(a,v);if(v!==0)$fatal(1,"state not reset %h=%h",a,v);end
 endtask
'''

def testbench():
 tb=(PREV/'tb.sv').read_text()
 start=tb.index(' usb_idle_trace dut(');end=tb.index('\n reg [31:0] words',start)
 inst=tb[start:end].replace('usb_idle_trace dut(','usb_idle_trace_base base(').replace('.read_pending(read_pending_net)', '.read_pending(base_read_pending)').replace('.n6_5(reset_merge_net)', '.n6_5(base_reset_merge)').replace('.usb_trace_hrdata(hrdata)', '.usb_trace_hrdata(base_hrdata)')
 tb=tb[:end]+'\n wire base_read_pending,base_reset_merge;wire [31:0] base_hrdata;\n'+inst+tb[end:]
 tb=pc.once(tb,'  value=hrdata;','''  value=hrdata;
  if(addr<192 && hrdata!==base_hrdata)$fatal(1,"old MMIO changed addr%h got%h base%h",addr,hrdata,base_hrdata);
  if(addr>=192 && base_hrdata!==0)$fatal(1,"extension address not reserved zero in baseline");''')
 tb=pc.once(tb,'words[1]!==1 || words[2]!==value','words[1]!==(mode==0?32\'d1:32\'d0) || words[2]!==value')
 tb=pc.once(tb,'  for(integer k=0;k<32;k=k+1)held[k]=words[k];', '''  for(integer k=0;k<32;k=k+1)begin
   held[k]=words[k];$display("BANK seq=%0d word=%0d value=%08h",seq,k,words[k]);
  end
  witness_check(value,seq);''')
 tb=pc.once(tb,' initial begin\n  #100;reset_n=1;',EXTRA+'\n initial begin\n  #100;reset_n=1;')
 tb=pc.once(tb,'  command(1);if(words[3]', '''  zero_witness_state();sweep_byte_addresses();
  for(integer a='hc0;a<256;a=a+1)bus_write(a,32'hffffffff);
  zero_witness_state();bus_read(8,s);if(s!==0)$fatal(1,"extension write changed sequence");
  command(1);if(words[3]''')
 tb=pc.once(tb,'  $display("PASS EXACT SNAPSHOT', '''  sweep_byte_addresses();witness_check(2,4);
  @(negedge clk);u_run=0;
  bus_write(12,2);repeat(20)@(negedge hclk);
  bus_read(4,s);if(s!==1)$fatal(1,"pending command while USB clock stopped");
  bus_read('he8,s);if(s!==4)$fatal(1,"spurious frame while USB clock stopped");
  @(negedge hclk);reset_n=0;repeat(20)@(negedge hclk);reset_n=1;
  repeat(20)@(negedge hclk);
  if(dut.utw_observer.\\r_total.q !==0)$fatal(1,"witness not reset with USB clock stopped");
  u_run=1;repeat(50)@(negedge hclk);zero_witness_state();
  bus_read(8,s);if(s!==0)$fatal(1,"snapshot count not reset");
  command(2);witness_check(2,1);
  $display("PASS EXACT SNAPSHOT''')
 return tb

def main():
 pc.parent_guard();out=pc.new_output(Path(sys.argv[1]));candidate=HERE/'candidate_01'
 assembly=json.loads((candidate/'assembly.json').read_text())
 for name,digest in assembly['inputs'].items():pc.require(pc.sha(candidate/name)==digest,'candidate changed '+name)
 original=(pc.PARENT/'console_neo.vg').read_text()
 support='\n'.join(pc.block(original,n) for n in ['ddr_dcfifo','ddr_dcfifo_0'])
 baseline=pc.block(original,'usb_idle_trace').replace('module usb_idle_trace (','module usb_idle_trace_base (',1)
 (out/'mapped_cut.v').write_text((candidate/'observer.v').read_text()+'\n'+baseline+'\n'+support+'\n'+(candidate/'helper_mapped.v').read_text())
 (out/'tb.sv').write_text(testbench())
 r=subprocess.run([IV,'-B',IVLIB,'-g2012','-s','usb_idle_trace_protocol_tb','-o',str(out/'test.vvp'),str(out/'tb.sv'),str(out/'mapped_cut.v'),str(PRIM)],capture_output=True,text=True,timeout=60)
 (out/'compile.log').write_text(r.stdout+r.stderr);pc.require(r.returncode==0 and not r.stderr,'compile warning/error '+r.stderr[-2000:])
 records=[]
 for case,args in enumerate([['+hp=6.25','+up=8.333333','+phase=.317'],['+hp=6.241','+up=8.342','+phase=3.713'],['+hp=8.342','+up=6.241','+phase=1.117']]):
  banks={}
  for mode in range(3):
   r=subprocess.run([VVP,str(out/'test.vvp'),f'+mode={mode}']+args,capture_output=True,text=True,timeout=45)
   (out/f'case{case}_mode{mode}.log').write_text(r.stdout+r.stderr)
   bank=[(int(s),int(i),int(v,16)) for s,i,v in re.findall(r'BANK seq=(\d+) word=(\d+) value=([0-9a-f]+)',r.stdout)]
   banks[mode]=bank
   records.append(dict(case=case,mode=mode,args=args,returncode=r.returncode,passed=r.returncode==0 and 'PASS EXACT SNAPSHOT' in r.stdout,bank_words=len(bank)))
  for mode in [1,2]:
   baseline=banks[0];injected=banks[mode]
   pc.require(len(baseline)==len(injected)==160,'incomplete integration logs')
   differences=[(a,b) for a,b in zip(baseline,injected) if a!=b]
   pc.require(len(differences)==5 and all(a[1]==b[1]==1 and a[2]==1 and b[2]==0 for a,b in differences),'injection changed words beyond version')
 result=dict(passed=all(x['passed'] for x in records),cases=records,hardware_access=False,SDF=False,
  baseline_comparison='exact mapped R19 in parallel; old MMIO byte offsets and all reply/control states match',
  injections={'0':'none: bank1=1, witness1=1','1':'reply bit0 forced low for slot1: bank1=0, witness1=0','2':'lane1 bank validity forced low: bank1=0, witness1=1'},
  qualification='Local fault-model separation only; original hardware version0 remains FAIL.',
  inputs={str(p):pc.sha(p) for p in [Path(__file__),HERE/'prepare_candidate.py',candidate/'assembly.json',out/'mapped_cut.v',out/'tb.sv',PRIM]})
 pc.save(out/'result.json',result);print(json.dumps(dict(passed=result['passed'],cases=len(records))))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
