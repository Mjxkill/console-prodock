#!/usr/bin/env python3
"""Extract the exact assembled reset cone and compare to candidate RTL; no PnR."""
from pathlib import Path
import re,json,hashlib,sys,subprocess
HERE=Path(__file__).resolve().parent
ROOT=Path('/home/michael/console');sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(HERE.parents[1]))
from build_memory_capture import block,cells,params
from gowin_toolchain import PRIMITIVES
from check_neo_fifo_mapped import module
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
OUT=HERE/'mapped_01';OUT.mkdir(exist_ok=False)
s=(BUILD/'console_neo.vg').read_text();top=block(s,'console_neo');soc=block(s,'ae350_soc');pll=block(s,'PLL_INIT')
def cell(source,name):
 a=re.findall(r'^\s*\w+\s+'+re.escape(name)+r'\s*\([^;]*?\);',source,re.M|re.S);assert len(a)==1,name
 d=re.findall(r'^\s*defparam\s+'+re.escape(name)+r'\.[^;]+;',source,re.M)
 return a[0]+'\n'+'\n'.join(d)+'\n'
top_names=['n4009_s2','ae350_rst_sync_0_s0','ae350_rst_sync_1_s0','neo_qualified_pll_lut','u_reset_trial']
soc_names=['init_sync_0_s0','init_sync_1_s0','neo_qualified_clear_lut']
selected=[('console_neo',n,cell(top,n)) for n in top_names]+[('ae350_soc',n,cell(soc,n)) for n in soc_names]+[('PLL_INIT','pll_ae350_lock_s',cell(pll,'pll_ae350_lock_s'))]
# Exact LUTs are complementary across all 16 combinations of PLL_INIT state and LOCK.
assert params(top)['n4009_s2.INIT']=="16'h7FFF"
assert params(pll)['pll_ae350_lock_s.INIT']=="16'h8000"
assert cells(top)['n4009_s2'][1]==dict(F='n4009_7',I0='state_178[0]',I1='state_178[1]',I2='state_178[2]',I3='pll_lock')
assert cells(pll)['pll_ae350_lock_s'][1]==dict(F='pll_ae350_lock',I0='state[0]',I1='state[1]',I2='state[2]',I3='pll_lock')
header="""`timescale 1ns/1ps
module exact_chain(input wire clk,bus80_clk,rtc_clk,pll_ae350_lock,ddr_init,uart_rx,
 output wire por_n,trial_done_o,trial_holding_o);
 wire clk_d=clk,vid_hclk=bus80_clk,uart_rx_d=uart_rx;
 wire VCC=1'b1,GND=1'b0;
 wire [2:0] state_178=3'b111,state=state_178;
 wire pll_lock=pll_ae350_lock;
 wire [1:0] ae350_rst_sync;
 wire [0:0] soc_dbg;wire [1:0] init_sync;
 wire trial_request,trial_mode,trial_holding,trial_done,trial_ahb_tick,trial_rtc_tick;
 wire [3:0] trial_epoch;
 wire n4009_7,neo_qualified_clear,neo_qualified_pll_ready;
 wire generated_pll_ready;
 wire trial_release=trial_request;
"""
# Rename only the flattened PLL ready net consistently to preserve the bench input name.
# This is alpha-renaming of a net; no primitive, INIT, or connection equation changes.
body=''.join(c for _,_,c in selected)
body=re.sub(r'\bpll_ae350_lock\b','generated_pll_ready',body)
cone=header+body+"""assign por_n=soc_dbg[0];assign trial_done_o=trial_done;assign trial_holding_o=trial_holding;
endmodule
"""
cone+=block(s,'neo_reset_trial')+'\n'+block(s,'neo_reset_trial_rx')+'\n'
(OUT/'mapped_cone.v').write_text(cone)
pt=PRIMITIVES.read_text();avail=set(re.findall(r'^module (\w+)',pt,re.M))
needed=(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',cone,re.M))&avail)|{'GSR'}
while True:
 deps=set()
 for n in needed:deps |= set(re.findall(r'^\s*(\w+)\s+\w+\s*\(',module(pt,n),re.M))&avail
 if deps<=needed:break
 needed|=deps
prim='`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',pt,re.M|re.S))+'\n'+'\n'.join(module(pt,n) for n in sorted(needed))
(OUT/'primitives.v').write_text(prim)
rtl=(HERE/'exact_chain.sv').read_text()+'\n'+(HERE/'neo_reset_trial.v').read_text()+'\n'+(HERE/'neo_reset_trial_rx.v').read_text()
for n in ['exact_soc_reset','exact_chain','neo_reset_trial_rx','neo_reset_trial']:
 rtl=re.sub(r'\b'+n+r'\b',n+'_rtl',rtl)
(OUT/'rtl_reference.sv').write_text(rtl)
tb=(HERE/'invariants_tb.sv').read_text();needle=' integer phase_ps=1000'
addition=""" GSR GSR(.GSRI(1'b1));
 wire rp,rd,rh;
 exact_chain_rtl reference(.clk(clk),.bus80_clk(bus80),.rtc_clk(rtc),.pll_ae350_lock(locked),.ddr_init(ready),.uart_rx(rx),.por_n(rp),.trial_done_o(rd),.trial_holding_o(rh));
 always @(posedge clk or posedge bus80 or negedge locked or negedge ready) begin
  #0.002;
  if({por,done,holding,dut.trial_request,dut.trial_epoch,dut.trial_mode} !==
     {rp,rd,rh,reference.trial_request,reference.trial_epoch,reference.trial_mode})
   $fatal(1,"Mapped/RTL reset cone mismatch at %0t",$time);
 end
"""
assert tb.count(needle)==1;tb=tb.replace(needle,addition+needle)
(OUT/'tb.sv').write_text(tb)
result=dict(passed=False,scope='Exact assembled fabric reset cone and helper with official functional primitives, compared against candidate02 RTL',hardware_access=False,timing=False,metastability=False,netlist_sha256=sha(BUILD/'console_neo.vg'),primitive_library_sha256=sha(PRIMITIVES),selected_cells=[dict(module=m,instance=n,exact_text_sha256=hashlib.sha256(c.encode()).hexdigest()) for m,n,c in selected],primitive_types=sorted(needed),boundaries=['PLL_INIT state fixed111; raw lock stimulus enters the two exact complementary LUT4 cones. This is no PLL/CPU behavioral model.','Clocks and DDRready are externally driven.','Only PLL ready net alpha-renamed when flattening PLL_INIT.','SoC trial_release alias equals actual top trial_request; original cells/pins/INIT preserved.'],inputs={str(p):sha(p) for p in [Path(__file__),BUILD/'assembly.json',OUT/'mapped_cone.v',OUT/'primitives.v',OUT/'rtl_reference.sv',OUT/'tb.sv']})
compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
try:
 with (OUT/'compile.log').open('x') as log:
  subprocess.run([str(compiler),'-B',str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(OUT/'sim.vvp'),*[str(OUT/n) for n in ['tb.sv','mapped_cone.v','primitives.v','rtl_reference.sv']]],stdout=log,stderr=log,check=True,timeout=60)
 with (OUT/'simulation.log').open('x') as log:
  child=subprocess.Popen([str(compiler.parent/'vvp'),str(OUT/'sim.vvp'),'+PHASE_PS=1000'],cwd=OUT,stdout=log,stderr=log)
  print('MAPPED_RUNNING pid='+str(child.pid),flush=True);rc=child.wait(timeout=1200)
 result['returncode']=rc
 assert rc==0 and 'INVARIANTS_PASS' in (OUT/'simulation.log').read_text()
 result['passed']=True
finally:
 result['outputs']={p.name:sha(p) for p in OUT.iterdir() if p.name in ['compile.log','simulation.log','events.csv']}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
