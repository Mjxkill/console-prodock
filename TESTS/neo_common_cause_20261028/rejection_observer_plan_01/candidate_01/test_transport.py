#!/usr/bin/env python3
"""Exercise both exact mapped NGDB transports and their unchanged address cones.

The CPU/AHB master is modeled. Bank modules, 17 shared address LUTs, NCP,
the overlay and FF primitives are the actual candidate/reference structures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import patch_transport as pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
import inspect_decision as inv
BIN = ROOT/'optimizer/.tools/oss-cad-suite/bin'
PRIM = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')

TB = r'''
`timescale 1ns/1ps
module tb;
 GSR GSR(.GSRI(1'b1));
 reg hclk=0,gclk=0,reset=1,gpu_run=1;
 real hp=6.25,gp=6.6665;
 always #(hp) hclk=~hclk;
 always #(gp) if(gpu_run)gclk=~gclk;
 reg [31:0] addr=0;
 reg wr=0,trans=0,data_bit=0;
 reg [639:0] payload=0,next_payload=0,old_payload=0;
 reg manual_pending=0;
 wire [31:0] gpu_data,scan_data;
 wire gpu_wait,scan_wait,prime_request;
 integer checks=0,trial,i;
 reg [31:0] got,seq0,seq1;
 // Reproduce the exact same-edge NBA hazard of manual freeze vs held capture.
 always @(posedge gclk) if(manual_pending && prime_request)begin
   payload<=next_payload;manual_pending<=0;
 end
 @DECLARATIONS@
 @INSTANCES@
 task write_reg(input integer page,input integer offset);
 begin
  @(negedge hclk);addr=(page<<12)|offset;wr=1;trans=1;data_bit=1;
  @(negedge hclk);wr=0;trans=0;
  repeat(2)@(negedge hclk);data_bit=0;
 end endtask
 task read_reg(input integer page,input integer offset,output reg[31:0] value);
 begin
  @(negedge hclk);addr=(page<<12)|offset;wr=0;trans=1;
  repeat(3)@(posedge hclk);#1;value=page==5?gpu_data:scan_data;
  @(negedge hclk);trans=0;repeat(2)@(negedge hclk);
 end endtask
 task snapshot(input integer page);
 integer tries;reg[31:0] before_count,after_count;
 begin
  read_reg(page,12,before_count);write_reg(page,4);
  after_count=before_count;tries=0;
  while(after_count==before_count && tries<100)begin read_reg(page,12,after_count);tries=tries+1;end
  if(after_count!=before_count+1)$fatal(1,"snapshot count page%0d got%h before%h",page,after_count,before_count);
  read_reg(page,4,after_count);
  if(after_count[1:0]!=2)$fatal(1,"snapshot not ready page%0d status%h",page,after_count);
 end endtask
 task verify_page(input integer page,input [319:0] expected);
 integer word_index,offset;reg[31:0] value;
 begin
  for(word_index=0;word_index<10;word_index=word_index+1)begin
   offset=word_index<8 ? 32+4*word_index:16+4*(word_index-8);
   read_reg(page,offset,value);
   if(value!==expected[word_index*32+:32])
    $fatal(1,"payload page%0d word%0d got%h expected%h",page,word_index,value,expected[word_index*32+:32]);
   checks=checks+1;
  end
 end endtask
 initial begin
  repeat(5)@(negedge hclk);reset=0;repeat(12)@(negedge hclk);
  read_reg(5,0,got);if(got!==32'h4e474442)$fatal(1,"GPU ID %h",got);
  read_reg(6,0,got);if(got!==32'h4e474442)$fatal(1,"SCAN ID %h",got);
  for(trial=0;trial<6;trial=trial+1)begin
   for(i=0;i<20;i=i+1)next_payload[i*32+:32]=$random;
   if(trial==3)begin hp=7.1;gp=4.9;end
   // Prime captures old payload, and only then publishes the frozen new one.
   old_payload=payload;manual_pending=1;snapshot(5);
   if(manual_pending)$fatal(1,"prime not observed in GPU domain");
   verify_page(5,old_payload[319:0]);
   snapshot(5);snapshot(6);
   verify_page(5,payload[319:0]);verify_page(6,payload[639:320]);
   verify_page(6,payload[639:320]);verify_page(5,payload[319:0]);
  end
  // GPU stopped: AHB must not invent a fresh acknowledgement or capture.
  @(negedge gclk);gpu_run=0;
  read_reg(5,12,seq0);write_reg(5,4);repeat(15)@(negedge hclk);
  read_reg(5,12,seq1);if(seq1!==seq0)$fatal(1,"ACK while GPU stopped");
  read_reg(5,4,got);if(!got[0])$fatal(1,"missing busy while GPU stopped");
  gpu_run=1;repeat(20)@(negedge hclk);
  read_reg(5,12,seq1);if(seq1!==seq0+1)$fatal(1,"resume count");
  verify_page(5,payload[319:0]);
  // Reset while a request is pending clears both transport-valid flags.
  @(negedge gclk);gpu_run=0;write_reg(6,4);reset=1;
  repeat(4)@(negedge hclk);gpu_run=1;repeat(5)@(negedge hclk);reset=0;
  repeat(12)@(negedge hclk);
  read_reg(5,4,got);if(got[1:0]!=0)$fatal(1,"GPU stale valid after reset");
  read_reg(6,4,got);if(got[1:0]!=0)$fatal(1,"SCAN stale valid after reset");
  snapshot(5);snapshot(6);verify_page(5,payload[319:0]);verify_page(6,payload[639:320]);
  $display("RESULT PASS checks=%0d nominal80_75=1 drift=1 stopped=1 reset_pending=1",checks);$finish;
 end
 initial begin #2000000;$fatal(1,"transport watchdog");end
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembly',type=Path,required=True)
    parser.add_argument('--mapping',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();out=a.out.resolve();assert out.parent==HERE
    assembly=a.assembly.resolve();mapping=a.mapping.resolve()
    assert assembly.parent==HERE and mapping.parent==HERE
    original=(inv.BUILD/'console_neo.vg').read_text()
    candidate=(assembly/'console_neo.vg').read_text()
    cells=inv.cells(inv.module(original,'gpu_accel'))
    drivers={c['ports']['F']:(n,c) for n,c in cells.items() if c['kind'].startswith('LUT')}
    roots=['n571_5','n579_5','n587_5','n596_6','n47_5','n613_6','n622_6','n632_7',
           'n640_5','n649_6','n658_6','n668_7','n677_6','n687_7','n697_7','n708_8','n716_5']
    kept={};leaves=set()
    def visit(net):
        if net not in drivers:leaves.add(net);return
        name,c=drivers[net]
        if name in kept:return
        kept[name]=c
        for pin,value in c['ports'].items():
            if pin!='F':visit(value)
    for net in roots:visit(net)
    assert len(kept)==17
    shared=set(roots)|{v for v in leaves if not v.startswith('bus_haddr_')}
    declarations=['wire '+','.join(sorted(shared))+';']
    # Gowin shares readiness synchronizers between the two original banks;
    # these top-level bindings must be preserved, not tied to mock data zero.
    shared.update({'observe_meta_s1','observe_meta_s2_6','observe_meta_s2_9'})
    declarations += ['wire [9:8] observe_meta_s1;',
                     'wire observe_meta_s2_6,observe_meta_s2_9;']
    for net in leaves:
        if net.startswith('bus_haddr_'):
            declarations.append(f'wire {net}=addr[{net.rsplit("_",1)[1]}];')
    instances=[]
    for name,c in kept.items():
        instances.append(c['kind']+' decode_'+name+'('+','.join('.'+p+'('+v+')' for p,v in c['ports'].items())+');')
        instances.extend('defparam decode_'+name+'.'+p+'='+v+';' for p,v in c['parameters'].items())
    modules=[]
    for module,label in [('neo_gpu_debug_0','gpu'),('neo_gpu_debug','scan')]:
        text=inv.module(candidate,module);modules.append(text);connections=[]
        for direction,width,name in re.findall(r'^(input|output)\s+(\[[^]]+\]\s*)?(\\\S+|\w+)\s*;',text,re.M):
            if direction=='input':
                if name in shared:value=name
                elif name.startswith('bus_haddr_'):value='addr['+name.rsplit('_',1)[1]+']'
                else:value={'vid_hclk':'hclk','gpu_clk':'gclk','n6_6':'reset','n237_5':'reset',
                            'vid_hrstn':'!reset','bus_hwrite':'wr','bus_hwdata':'data_bit','bus_htrans':'trans',
                            'up':"1'b1",'\\g_inferred_storage.mem_10':"1'b1",'trace_ready':"1'b1",
                            'scan_debug_live_224':'!reset',
                            'rjc_payload':'payload[319:0]' if label=='gpu' else 'payload[639:320]'}.get(name,"'0")
            elif name in shared:value=name
            else:
                value={'debug_hrdata':'gpu_data','scan_debug_hrdata':'scan_data','read_wait':label+'_wait',
                       'rjc_snapshot_request':'prime_request'}.get(name)
                if value is None:
                    value=label+'_'+name.replace('\\','')
                    declarations.append('wire '+(width or '')+value+';')
            connections.append('.'+pt.escaped(name)+'('+value+')')
        instances.append(module+' '+label+'('+','.join(connections)+');')
    out.mkdir(exist_ok=False)
    (out/'banks.v').write_text('\n'.join(modules+[inv.module(original,'neo_capture_bus')])+'\n')
    (out/'tb.sv').write_text(TB.replace('@DECLARATIONS@','\n'.join(declarations)).replace('@INSTANCES@','\n'.join(instances)))
    cmd=[BIN/'iverilog','-g2012','-s','tb','-o',out/'sim.vvp',out/'banks.v',
         mapping/'neo_rjc_readback_mapped.v',PRIM,out/'tb.sv']
    with (out/'compile.log').open('x') as log:
        p=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=60)
    assert p.returncode==0,out/'compile.log'
    with (out/'test.log').open('x') as log:
        p=subprocess.run([str(BIN/'vvp'),str(out/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=60)
    text=(out/'test.log').read_text();passed=p.returncode==0 and 'RESULT PASS' in text
    inputs=[Path(__file__),assembly/'console_neo.vg',mapping/'neo_rjc_readback_mapped.v',PRIM]
    result={'passed':passed,'hardware':False,'exact_banks':True,'original_address_LUTs':len(kept),
            'scope':'80/75 MHz, shifted ratio, manual NBA prime, opposite bank read order, stopped GPU, reset pending',
            'limits':['AHB master and data producers modeled; no DDR or hardware assertion.'],
            'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));assert passed,out/'test.log'


if __name__=='__main__':main()
