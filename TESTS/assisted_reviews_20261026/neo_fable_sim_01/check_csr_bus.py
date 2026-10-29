#!/usr/bin/env python3
"""Validate TESTS-only CSR candidates on real AHB and strengthen X checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('csr',HERE/'check_csr_candidates.py')
csr=importlib.util.module_from_spec(spec)
spec.loader.exec_module(csr)

AHB='''`timescale 1ns/1ps
module tb;
reg hc=0,mc=0,rst=0,hc_run=1;
always #6.25 if(hc_run)hc=~hc;
always #6.666 mc=~mc;
reg sel=0,wr=0;reg[31:0]address=0,data=0;reg[1:0]trans=0;
wire[31:0]result;wire hready,bv,bw;wire[28:0]ba;wire[255:0]bwd;wire[31:0]bm;
gpu_accel #(.FONT_FILE("font8x16.hex"))dut(.hclk(hc),.hresetn(rst),.hsel(sel),.hwrite(wr),
.haddr(address),.hwdata(data),.htrans(trans),.hrdata(result),.hready(hready),
.mem_clk(mc),.valid(bv),.write(bw),.addr(ba),.wr_data(bwd),.wr_mask(bm),
.ready(1'b0),.rd_data(256'd0),.rd_valid(1'b0)DEBUG_PORTS);
integer reads=0,waits=0,checks=0;
reg[31:0] sampled_response;
reg sampled_rst;
always @(posedge hc)begin
  sampled_rst=rst;sampled_response=dut.response_data;
  #1;
  if(sampled_rst)begin
    if(result !== sampled_response)$fatal(1,"CSR output pipeline mismatch");
    if((^result)===1'bx)$fatal(1,"Unknown CSR output after reset");
    checks++;
  end else if(result!==0)$fatal(1,"CSR reset result");
end
task automatic read_csr(input[7:0]a,input integer pause);
 integer count;reg[31:0]expected;
 @(negedge hc);address=a;sel=1;trans=2;wr=0;
 @(posedge hc);if(hready!==1)$fatal(1,"CSR address not ready");
 @(negedge hc);sel=0;trans=0;
 if(pause)begin hc_run=0;#97;hc_run=1;end
 count=0;
 do begin
   @(posedge hc);if(hready===0)begin count++;waits++;end
   else if(hready!==1)$fatal(1,"Unknown CSR HREADY");
   if(count>3)$fatal(1,"Unbounded CSR read");
 end while(!hready);
 #2;
 expected=0;
 for(integer k=0;k<26;k++)if(a==k*4)expected=dut.register_value[k];
 if(result!==expected)$fatal(1,"CSR address %h got=%h expected=%h",a,result,expected);
 if(count!=1)$fatal(1,"CSR wait states got=%0d",count);
 reads++;
 @(negedge hc);
endtask
initial begin
 repeat(8)@(negedge hc);rst=1;repeat(20)@(negedge hc);
 for(integer round=0;round<2;round++)begin
   for(integer a=0;a<256;a++)read_csr(a,round==1 && a%17==0);
   @(negedge hc);rst=0;#73;@(negedge hc);rst=1;repeat(20)@(negedge hc);
 end
 if(reads!=512 || waits!=512 || checks<1024)$fatal(1,"Vacuous CSR test");
 if(bv!==0)$fatal(1,"CSR reads emitted a DDR request");
 $display("PASS AHB CSR reads=%0d waits=%0d pipeline_checks=%0d",reads,waits,checks);$finish;
end
initial begin #1000000;$fatal(1,"Global CSR timeout");end
endmodule
'''

X_MONITOR='''
// Explicit four-state guards: no silent if(X) on these control/payload paths.
always @(negedge mc)if(rst && dut.mrst[1])begin
  if((^{dut.v1_pending,dut.v1_accepted,bv,br,me,mready,mwready})===1'bx)
    $fatal(1,"UNKNOWN memory control");
  if(dut.v1_pending && (^{dut.v1_tx_write,dut.v1_tx_addr,dut.v1_tx_data,dut.v1_tx_mask})===1'bx)
    $fatal(1,"UNKNOWN held slot payload");
  if(me && (^{cmd,ma,md,mm,mwe,mend})===1'bx)$fatal(1,"UNKNOWN DDR transaction");
end
always @(negedge hc)if(rst)begin
  if((^{hready,dut.queue_valid,dut.queue_full})===1'bx)$fatal(1,"UNKNOWN command control");
end
'''

def main():
 out=HERE/'csr_validation_02';out.mkdir()
 manifest=HERE/'csr_candidates_01/result.json'
 proven=json.loads(manifest.read_text());assert proven['passed']
 for p,digest in proven['inputs'].items():assert csr.sha(ROOT/p)==digest,p
 result={'passed':False,'hardware_access':False,'common_sources_modified':False,
         'started_unix':time.time(),'inputs':{csr.rel(manifest):csr.sha(manifest),csr.rel(Path(__file__)):csr.sha(Path(__file__))},'profiles':{}}
 inputs=json.loads((HERE/'rtl_inputs.json').read_text())['sources']
 relatives=[Path(p).relative_to(csr.PROFILES['neo'].relative_to(ROOT)) for p in inputs]
 try:
  for profile in ['neo','prodock']:
   base=csr.PROFILES[profile];path=ROOT/proven['profiles'][profile]['candidate']
   assert csr.sha(path)==proven['profiles'][profile]['candidate_sha256']
   result['inputs'][csr.rel(path)]=csr.sha(path)
   sources=[path if p.name=='gpu_accel.v' else base/p for p in relatives if p.suffix=='.v']
   result['profiles'][profile]={}
   for test in ['ahb','clear','copy']:
    folder=out/profile/test;folder.mkdir(parents=True)
    if test=='ahb':
     ports=',.debug_state(),.debug_accept(),.observe_packet_words()' if profile=='neo' else ''
     text=AHB.replace('DEBUG_PORTS',ports);marker='PASS AHB CSR'
    else:
     text=(HERE/('tb_reviewed_r3.sv' if test=='clear' else 'tb_copy.sv')).read_text()
     if profile=='prodock':text=text.replace(',\n        .debug_state(),.debug_accept(),.observe_packet_words()','')
     assert text.count('endmodule')==1
     text=text.replace('endmodule',X_MONITOR+'\nendmodule')
     marker='PASS R19 REAL SLOT '+test.upper()
    bench=folder/'tb.sv';bench.write_text(text)
    shutil.copy2(base/'rtl/video/font8x16.hex',folder/'font8x16.hex')
    result['profiles'][profile][test]=csr.run_ivl(folder,bench,sources,marker)
    result['profiles'][profile][test]['bench_sha256']=csr.sha(bench)
  for p,digest in proven['inputs'].items():assert csr.sha(ROOT/p)==digest,p
  result['passed']=True
 except Exception as exc:result['error']=repr(exc)
 finally:
  result['finished_unix']=time.time()
  (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
