#!/usr/bin/env python3
"""Real R19 mapped COPY plus external exact helper body, zero delay only."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREVIOUS=HERE.parent/'neo_fable_sim_01/copy_mapped_02'
HELPER=ROOT/'TESTS/neo_720p_20261012/capture_memory_20261027/neo_capture_memory.v'
IVL=Path('/tmp/console-usb-sim-tools/extracted/usr')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

BODY='''
reg observer_arm=0,observer_snap=0;
wire observer_arm_ack,observer_snap_ack,observer_ready,observer_beat;
wire [63:0] observer_held;
wire [23:0] copy_sample={dut.u_pixels.u_copy.copy_done,dut.u_pixels.u_copy.copy_bad,
    (dut.u_pixels.u_copy.state_0==17),(dut.u_pixels.u_copy.state_0==1),
    (dut.u_pixels.u_copy.state_0==0),dut.u_pixels.state[41],!child_resetn,
    dut.u_pixels.u_copy.n7630_6,dut.u_pixels.u_copy.packet_0[87:80],dut.u_pixels.packet[87:80]};
wire [3:0] observer_events={2'b00,(native_valid|cache_valid|copy_valid),dut.u_pixels.native_issue};
// External observer has an isolated module name to coexist with the original
// observer already in the unmodified R19 netlist. The helper body is exact.
neo_capture_observed_test observer(.clk(clk),.resetn(resetn),.sample(copy_sample),
 .mem_events(observer_events),.arm_req(observer_arm),.snap_req(observer_snap),
 .arm_ack(observer_arm_ack),.snap_ack(observer_snap_ack),.ready(observer_ready),
 .heartbeat(observer_beat),.held(observer_held));
integer fault=0,checks=0;
task send(input[255:0]words);
 @(negedge clk);command=words;start=1;
 @(negedge clk);start=0;command={8{32'hbaddcafe}};
endtask
task arm_observer;
 integer n;
 @(negedge clk);observer_arm=~observer_arm;n=0;
 while(observer_arm_ack!==observer_arm && n<20)begin @(negedge clk);n++;end
 if(observer_arm_ack!==observer_arm)$fatal(1,"Observer ARM timeout");
endtask
task snapshot_observer;
 integer n;
 @(negedge clk);observer_snap=~observer_snap;n=0;
 while(observer_snap_ack!==observer_snap && n<20)begin @(negedge clk);n++;end
 if(observer_snap_ack!==observer_snap || observer_held[63:60]!==4'hd || (^observer_held)===1'bx)
  $fatal(1,"Observer SNAP timeout/unknown");
endtask
integer n;
reg[63:0]saved;
initial begin
 if($value$plusargs("fault=%d",fault))begin end
 repeat(10)@(negedge clk);resetn=1;repeat(3)@(negedge clk);child_resetn=1;
 repeat(8)@(negedge clk);
 send(256'h0000000000000000000000000100010000800010008100000080002016000000);
 n=0;while(done!==1 && n<200)begin @(negedge clk);n++;end
 if(done!==1 || rejected!==0 || dut.shader_target_valid!==1)$fatal(1,"Actual mapped TARGET failed");
 repeat(8)@(negedge clk);
 arm_observer();snapshot_observer();
 if(observer_held[51:48]!==8 || observer_held[59:56]!==0)$fatal(1,"Old events before COPY");checks++;
 if(fault==1)force dut.u_pixels.u_copy.n7630_6=0;
 if(fault==2)force dut.u_pixels.u_copy.packet_0[87:80]=0;
 if(fault==3)force dut.u_pixels.packet[87:80]=0;
 send(256'h000000000010000100000000000000000000002000100001008080001d000000);
 n=0;while(done!==1 && copy_valid!==1 && n<300)begin @(negedge clk);n++;end
 if(n==300)$fatal(1,"COPY did not reach descriptor result");
 // The source stimulus remains honest: faults are explicit mapped signal
 // injections, never presented as observations of hardware behavior.
 snapshot_observer();saved=observer_held;
 if(saved[51:48]!==7)$fatal(1,"Missing at/after capture %h",saved);checks++;
 if(saved[7:0] !== (fault==3 ? 8'h00:8'h10))$fatal(1,"Observed COPY D wrong");
 if(saved[31:24] !== (fault==3 ? 8'h00:8'h10))$fatal(1,"Observed after D wrong");
 if(saved[39:32] !== (fault==0 ? 8'h10:8'h00))$fatal(1,"Observed after Q wrong");
 if(saved[16] !== (fault!=1) || saved[18]!==1 || saved[19]!==1 || saved[17]!==0)
  $fatal(1,"Observed capture edge controls wrong");
 if(saved[59:56] !== (fault==0 ? 4'h2:4'h0))$fatal(1,"Producer sticky event wrong");
 if(fault==0)begin
  if(copy_valid!==1 || rejected!==0 || dut.u_pixels.u_copy.descriptor_bad!==0)$fatal(1,"Valid COPY result");
 end else begin
  if(done!==1 || rejected!==1 || dut.u_pixels.u_copy.descriptor_bad !== (fault==1 ? 3'b011:3'b001))
   $fatal(1,"Injected COPY fault result");
 end
 checks+=7;
 // Explicit held bus must survive an idle interval and repeated snapshot.
 repeat(20)@(negedge clk);if(observer_held!==saved)$fatal(1,"HELD spontaneous change");
 snapshot_observer();if(observer_held!==saved)$fatal(1,"Stable snapshot changed");checks+=2;
 arm_observer();snapshot_observer();
 if(observer_held[51:48]!==8)$fatal(1,"Re-arm replayed prior capture");checks++;
 $display("PASS MAPPED COPY OBSERVER fault=%0d checks=%0d trace=%h bad=%b",fault,checks,saved,dut.u_pixels.u_copy.descriptor_bad);
 $finish;
end
initial begin #1000000;$fatal(1,"Bounded mapped observer timeout");end
endmodule
'''

def main():
 out=HERE/'mapped_copy_01';out.mkdir()
 prior=json.loads((PREVIOUS/'result.json').read_text());assert prior['passed']
 for path,digest in prior['inputs'].items():
  path=Path(path);path=path if path.is_absolute() else ROOT/path
  assert sha(path)==digest,path
 assert sha(HELPER)=='1051163608ea69c7f56ebb2a4363a7ac773285e7284e3f532b377054602f7a90'
 original=HELPER.read_text();assert original.count('module neo_capture_local(')==1
 named=out/'helper_named.v';named.write_text(original.replace('module neo_capture_local(','module neo_capture_observed_test('))
 assert named.read_text().replace('module neo_capture_observed_test(','module neo_capture_local(')==original
 prefix=(PREVIOUS/'tb.sv').read_text().split('integer captures=0;')[0]
 # r2 declarations share a line beginning exactly integer captures=0,
 # so avoid bringing any existing check code into this new bench.
 prefix=(PREVIOUS/'tb.sv').read_text().split('integer captures=0,')[0]
 assert prefix.rstrip().endswith('));')
 bench=out/'tb.sv';bench.write_text(prefix+BODY)
 files=[bench,PREVIOUS/'mapped.v',PREVIOUS/'primitives.v',named]
 result={'passed':False,'hardware_access':False,'scope':'Exact R19 mapped geometry/pixels/COPY; unchanged official primitives, real new helper body under alternate test module name; no memory/slot/timing qualification',
  'inputs':{str(f):sha(f) for f in [Path(__file__),HELPER,PREVIOUS/'result.json',*files]},'runs':[]}
 try:
  with (out/'compile.log').open('w') as log:
   subprocess.run([str(IVL/'bin/iverilog'),'-B',str(IVL/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),*map(str,files)],stdout=log,stderr=log,timeout=120,check=True)
  for fault in range(4):
   logpath=out/f'fault_{fault}.log'
   with logpath.open('w') as log:subprocess.run([str(IVL/'bin/vvp'),str(out/'sim.vvp'),f'+fault={fault}'],stdout=log,stderr=log,timeout=90,check=True)
   assert 'PASS MAPPED COPY OBSERVER' in logpath.read_text()
   result['runs'].append({'fault':fault,'passed':True,'log_sha256':sha(logpath)})
  for path,digest in result['inputs'].items():assert sha(Path(path))==digest,path
  result['passed']=True
 except Exception as e:result['error']=repr(e)
 finally:
  result['logs']={p.name:sha(p) for p in out.glob('*.log')}
  (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
