#!/usr/bin/env python3
"""Graph, parser counterexamples, helper and full observer integration; no Gowin."""
import json
from pathlib import Path
import re
import subprocess
import sys
import prepare_format as f
sys.path.insert(0,str(f.FROZEN))
import test_helper as th
import test_integration as ti

def main():
 out=Path(sys.argv[1]);out.mkdir(exist_ok=False);f.check(require_tests=False)
 helper=f.OUT/'helper_normalized.v';proof=json.loads((f.OUT/'serialization_proof.json').read_text())
 data=json.loads((f.FROZEN/'mapping_02/helper.json').read_text())['modules']['neo_usb_reply_witness']
 refs=proof['bit_references'];results=[]
 (out/'tb_helper.sv').write_text(th.TB)
 for name,source in [('original',f.FROZEN/'mapping_02/helper_mapped.v'),('normalized',helper)]:
  results.append(th.compile_run(out,name,source,out/'tb_helper.sv',['+vectors='+str(f.FROZEN/'helper_tests_02/vectors.txt')]))
 for counter,index,busy in [('count0',0,1),('count1',1,1),('count2',2,1),('total',8,1),('frames',31,1),('outside_count',8,0)]:
  key='r_total.q' if counter=='total' else counter;bits=data['netnames'][key]['bits']
  wires=['dut.'+refs[str(bit)] for bit in bits]
  joined='{'+','.join(reversed(wires))+'}'
  text='''`timescale 1ns/1ps
module tb;
 reg hclk=0,hreset=1,reply_valid=0,busy=1;reg [4:0] receive_index=0;
 reg [31:0] reply=1,completed_count=0;reg [7:0] address=8'hf0;
 wire read_hit;wire [31:0] read_data;GSR GSR(.GSRI(1'b1));
 neo_usb_reply_witness dut(.*);always #5 hclk=~hclk;
 initial begin
  repeat(2)@(negedge hclk);hreset=0;
  FORCE
  reply_valid=1;receive_index=INDEX;busy=BUSY;
  @(posedge hclk);#1;RELEASE #1;
  if(COUNTER!==0 || read_data[6]!==1)$fatal(1,"overflow wrap/flag");
  @(negedge hclk);reply_valid=0;repeat(3)@(negedge hclk);
  if(read_data[6]!==1)$fatal(1,"overflow not sticky");
  hreset=1;@(posedge hclk);#1;if(read_data!==0)$fatal(1,"reset overflow");
  $display("PASS WITNESS NORMALIZED OVERFLOW");$finish;
 end
endmodule
'''.replace('FORCE','\n'.join('force '+wire+"=1'b1;" for wire in wires)).replace('RELEASE','\n'.join('release '+wire+';' for wire in wires)).replace('COUNTER',joined).replace('INDEX',str(index)).replace('BUSY',str(busy))
  tb=out/f'tb_overflow_{counter}.sv';tb.write_text(text)
  results.append(th.compile_run(out,'overflow_'+counter,helper,tb))
 # Explicit lexer/graph negative controls: legal IEEE syntax is not evidence
 # of acceptance by Gowin. Original PA2060/PA2000 log remains the real evidence.
 symbols={'a':[0,1,2,3],'x.y':[4],'z':[5,6,7]}
 require=f.require
 require(f.expr('{a[3:2],\\x.y ,z[1:0]}',symbols)==[5,6,4,2,3],'concat LSB order')
 require(f.number('2')==f.number("32'd2")==2,'unsized decimal parameter')
 for bad in ['a[4]','z[4:0]','unknown','a[1]+a[0]']:
  try:f.expr(bad,symbols)
  except RuntimeError:results.append(dict(name='reject expression '+bad,passed=True))
  else:raise RuntimeError('accepted bad expression '+bad)
 text=helper.read_text();norm_symbols=proof['normalized_symbols']
 old=f.block((f.PARENT/'console_neo.vg').read_text(),'neo_usb_reply_witness')
 # The original must contain all observed failure classes; the emitted helper
 # has no escape, no internal bus, and no slice/concat assignment at all.
 require(re.search(r'wire\s+\[0:0\]\s+\\r_duplicate\.q',old) is not None,'one-bit vector counterexample missing')
 require(re.search(r'assign\s+[^;]*\[[0-9]+:[0-9]+\]\s*=',old) is not None,'slice assignment counterexample missing')
 require(not re.search(r'\\|\bassign\s+[^;]*[:,{}]',text),'rejected serialization construct remains')
 oldcells,oldparams,_=f.parsed(text,norm_symbols)
 first=next(name for name,cell in oldcells.items() if cell['type']=='LUT4')
 wrong=text.replace('defparam '+first+'.INIT = '+oldparams[(first,'INIT')]+';','defparam '+first+".INIT = 16'h0000;",1)
 _,wrongparams,_=f.parsed(wrong,norm_symbols)
 require(wrongparams!=oldparams,'parameter mutant not detected')
 results.append(dict(name='parameter mutation differs in graph proof',passed=True))
 # Full observer/FIFO baseline and candidate share bus/clock stimuli.
 original=(f.previous.PARENT/'console_neo.vg').read_text()
 baseline=f.block(original,'usb_idle_trace').replace('module usb_idle_trace (','module usb_idle_trace_base (',1)
 support='\n'.join(f.block(original,n) for n in ['ddr_dcfifo','ddr_dcfifo_0'])
 (out/'mapped_cut.v').write_text((f.OUT/'observer_normalized.v').read_text()+'\n'+baseline+'\n'+support+'\n'+text)
 tb=ti.testbench();target='dut.utw_observer.\\r_total.q '
 require(tb.count(target)==1,'counter bench reference changed')
 counter='{'+','.join('dut.utw_observer.'+refs[str(bit)] for bit in reversed(data['netnames']['r_total.q']['bits']))+'}'
 tb=tb.replace(target,counter);(out/'tb_integration.sv').write_text(tb)
 r=subprocess.run([th.IV,'-B',th.IVLIB,'-g2012','-s','usb_idle_trace_protocol_tb','-o',str(out/'integration.vvp'),str(out/'tb_integration.sv'),str(out/'mapped_cut.v'),str(th.PRIM)],capture_output=True,text=True,timeout=60)
 (out/'integration_compile.log').write_text(r.stdout+r.stderr);require(r.returncode==0 and not r.stderr,'integration compile '+r.stderr[-1500:])
 for case,args in enumerate([['+hp=6.25','+up=8.333333','+phase=.317'],['+hp=6.241','+up=8.342','+phase=3.713'],['+hp=8.342','+up=6.241','+phase=1.117']]):
  banks={}
  for mode in range(3):
   r=subprocess.run([th.VVP,str(out/'integration.vvp'),f'+mode={mode}']+args,capture_output=True,text=True,timeout=45)
   (out/f'integration_{case}_{mode}.log').write_text(r.stdout+r.stderr)
   results.append(dict(name=f'integration_{case}_{mode}',passed=r.returncode==0 and 'PASS EXACT SNAPSHOT' in r.stdout,returncode=r.returncode))
   banks[mode]=[(int(n),int(i),int(v,16)) for n,i,v in re.findall(r'BANK seq=(\d+) word=(\d+) value=([0-9a-f]+)',r.stdout)]
  for mode in [1,2]:
   require(len(banks[0])==len(banks[mode])==160,'incomplete bank log')
   diffs=[(a,b) for a,b in zip(banks[0],banks[mode]) if a!=b]
   require(len(diffs)==5 and all(a[1]==b[1]==1 and a[2]==1 and b[2]==0 for a,b in diffs),'fault changed other words')
 result=dict(passed=all(row['passed'] for row in results),hardware_access=False,Gowin_executed=False,new_synthesis=False,
  netlist_sha256=f.sha(f.OUT/'console_neo.vg'),cases=results,scoreboard_cycles_per_version=12013,
  graph_proof_sha256=f.sha(f.OUT/'serialization_proof.json'),
  inputs={str(path):f.sha(path) for path in [Path(__file__),Path(f.__file__),Path(th.__file__),Path(ti.__file__),helper,f.OUT/'observer_normalized.v',f.OUT/'format_assembly.json',f.FROZEN/'helper_tests_02/vectors.txt',Path(th.IV),Path(th.VVP),th.PRIM]})
 f.save(out/'result.json',result);require(result['passed'],'format validation failed')
 f.save(f.HERE/'validation.json',dict(proof=str((out/'result.json').resolve()),sha256=f.sha(out/'result.json')))
 print(json.dumps(dict(passed=True,cases=len(results),netlist_sha256=result['netlist_sha256'])))

if __name__=='__main__':main()
