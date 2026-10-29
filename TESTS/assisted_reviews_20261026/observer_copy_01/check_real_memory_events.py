#!/usr/bin/env python3
"""New observer on real candidate R19 RTL native/slot/arbiter traffic."""
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SIM=HERE.parent/'neo_fable_sim_01'
spec=importlib.util.spec_from_file_location('csr',SIM/'check_csr_candidates.py')
csr=importlib.util.module_from_spec(spec);spec.loader.exec_module(csr)
HELPER=ROOT/'TESTS/neo_720p_20261012/capture_memory_20261027/neo_capture_memory.v'

EXTRA='''
reg observer_arm=0,observer_snap=0;
wire observer_arm_ack,observer_snap_ack,observer_ready,observer_beat;
wire[63:0]observer_held;
wire copy_start=dut.u_v1.u_pixels.state[41];
wire copy_idle=dut.u_v1.u_pixels.u_copy.state==0;
wire[23:0]copy_sample={dut.u_v1.u_pixels.copy_done,dut.u_v1.u_pixels.copy_bad,
 (dut.u_v1.u_pixels.u_copy.state==17),(dut.u_v1.u_pixels.u_copy.state==1),
 copy_idle,copy_start,!dut.u_v1.u_pixels.child_resetn[0],
 (dut.u_v1.u_pixels.child_resetn[0]&&copy_start&&copy_idle),
 dut.u_v1.u_pixels.u_copy.packet[87:80],dut.u_v1.u_pixels.packet[87:80]};
wire[3:0]memory_events={dut.v1_accepted,dut.v1_pending,
 (dut.u_v1.u_pixels.native_valid|dut.u_v1.u_pixels.copy_valid|dut.u_v1.u_pixels.cache_valid),
 dut.u_v1.u_pixels.native_issue};
neo_capture_local observer(.clk(mc),.resetn(rst),.sample(copy_sample),.mem_events(memory_events),
 .arm_req(observer_arm),.snap_req(observer_snap),.arm_ack(observer_arm_ack),.snap_ack(observer_snap_ack),
 .ready(observer_ready),.heartbeat(observer_beat),.held(observer_held));
task automatic obs_arm;
 integer n;
 @(negedge mc);observer_arm=~observer_arm;n=0;
 while(observer_arm_ack!==observer_arm && n<20)begin @(negedge mc);n++;end
 if(observer_arm_ack!==observer_arm)$fatal(1,"Observer real ARM timeout");
endtask
task automatic obs_snap;
 integer n;
 @(negedge mc);observer_snap=~observer_snap;n=0;
 while(observer_snap_ack!==observer_snap && n<20)begin @(negedge mc);n++;end
 if(observer_snap_ack!==observer_snap)$fatal(1,"Observer real SNAP timeout");
endtask
always @(negedge mc)if(rst && dut.mrst[1])begin
 if((^{dut.done_count,dut.command_bad,dut.command_lost,dut.v1_rejected,memory_events})===1'bx)
  $fatal(1,"Unknown application status or observed event");
 if(dut.v1_pending && (^{dut.v1_tx_write,dut.v1_tx_addr,dut.v1_tx_data,dut.v1_tx_mask})===1'bx)
  $fatal(1,"Unknown held transaction");
end
'''

def main():
 out=HERE/'real_memory_events_01';out.mkdir()
 manifest=SIM/'csr_candidates_01/result.json';prior=json.loads(manifest.read_text());assert prior['passed']
 for p,digest in prior['inputs'].items():assert csr.sha(ROOT/p)==digest,p
 assert csr.sha(HELPER)=='1051163608ea69c7f56ebb2a4363a7ac773285e7284e3f532b377054602f7a90'
 inputs=json.loads((SIM/'rtl_inputs.json').read_text())['sources']
 candidate=ROOT/prior['profiles']['neo']['candidate']
 sources=[candidate if Path(p).name=='gpu_accel.v' else ROOT/p for p in inputs if p.endswith('.v')]+[HELPER]
 result={'passed':False,'hardware_access':False,'scope':'Real R19 application except the isolated CSR simulation candidate; observer sees actual native issue, pixel producer, slot and ACK. External DDR model only.',
  'inputs':{csr.rel(p):csr.sha(p) for p in [Path(__file__),manifest,*sources]},'runs':{}}
 try:
  for case in ['clear','copy']:
   folder=out/case;folder.mkdir()
   text=(SIM/('tb_reviewed_r3.sv' if case=='clear' else 'tb_copy.sv')).read_text()
   text=text.replace('    integer before_writes,before_grants;' if case=='clear' else '    integer limit;',EXTRA+('\n    integer before_writes,before_grants;' if case=='clear' else '\n    integer limit;'))
   needle='        repeat(40)@(negedge mc);';assert text.count(needle)==1
   text=text.replace(needle,needle+'\n        obs_arm();')
   needle='        $display("PASS R19 REAL SLOT '+case.upper();assert text.count(needle)==1
   check='''        obs_snap();
        if(observer_held[63:56]!==8'hMASK)$fatal(1,"Wrong real memory events %h",observer_held);
        $display("PASS REAL MEMORY OBSERVER CASE trace=%h",observer_held);
'''.replace('MASK','df' if case=='clear' else 'de').replace('CASE',case)
   text=text.replace(needle,check+needle)
   bench=folder/'tb.sv';bench.write_text(text)
   shutil.copy2(csr.PROFILES['neo']/'rtl/video/font8x16.hex',folder/'font8x16.hex')
   result['runs'][case]=csr.run_ivl(folder,bench,sources,'PASS REAL MEMORY OBSERVER '+case)
   result['runs'][case]['bench_sha256']=csr.sha(bench)
  for p,digest in result['inputs'].items():assert csr.sha(ROOT/p)==digest,p
  result['passed']=True
 except Exception as e:result['error']=repr(e)
 finally:
  (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
