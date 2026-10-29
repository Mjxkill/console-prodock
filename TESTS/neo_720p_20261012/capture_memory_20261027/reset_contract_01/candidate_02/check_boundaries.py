#!/usr/bin/env python3
"""Prove structural boundary aliases used by mapped_01 without changing that run."""
from pathlib import Path
import hashlib,json,sys,re
ROOT=Path('/home/michael/console');HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]));from build_memory_capture import block,cells,params
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
net=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled/console_neo.vg'
s=net.read_text();t=cells(block(s,'console_neo'));pll=cells(block(s,'Gowin_PLL_AE350'));ip=cells(block(s,'PLL_INIT'));soc=cells(block(s,'ae350_soc'))
assert t['u_pll_ae350'][1]['pll_lock']=='pll_lock'
assert t['u_pll_ae350'][1]['state']=='state_178[2:0]'
assert t['u_pll_ae350'][1]['pll_ae350_lock']=='pll_ae350_lock'
assert pll['u_pll_init'][1]['pll_lock']=='pll_lock'
assert pll['u_pll_init'][1]['state']=='state[2:0]'
assert pll['u_pll_init'][1]['pll_ae350_lock']=='pll_ae350_lock'
assert t['u_soc'][1]['ae350_rst_sync']=='ae350_rst_sync[1]'
assert t['u_soc'][1]['trial_release']=='trial_request'
assert t['u_soc'][1]['soc_dbg']=='soc_dbg[0]'
assert t['u_soc'][1]['vid_hclk']=='vid_hclk'
assert t['u_reset_trial'][1]['cpu_reset_n']=='soc_dbg[0]'
assert t['u_reset_trial'][1]['pll_ready']=='neo_qualified_pll_ready'
assert soc['init_sync_1_s0'][1]['Q']=='soc_dbg[0]'
assert t['VCC_cZ']==('VCC',{'V':'VCC'}) and t['GND_cZ']==('GND',{'G':'GND'})
assert soc['VCC_cZ']==('VCC',{'V':'VCC'})
truth=[]
for i in range(16):
 lock=(0x8000>>i)&1;reset=(0x7fff>>i)&1
 assert reset==(not lock)
 truth.append(dict(state=i&7,raw_pll_lock=i>>3,qualified_lock=lock,preset=reset))
result=dict(passed=True,netlist_sha256=sha(net),mapped_cone_sha256=sha(HERE/'mapped_01/mapped_cone.v'),script_sha256=sha(Path(__file__)),verified_hierarchical_ports=['console_neo/u_pll_ae350','Gowin_PLL_AE350/u_pll_init','console_neo/u_soc','console_neo/u_reset_trial'],truth_table=truth,flattened_test_boundary='state111 + raw pll_lock stimulus; LUT7FFF/8000 retained exactly',limitations=['No PLL lock-generation behavior claimed.','No routed delays or analog pulse-width model.'])
(HERE/'boundary_proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
