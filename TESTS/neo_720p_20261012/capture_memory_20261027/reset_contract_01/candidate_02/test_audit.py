#!/usr/bin/env python3
"""Counterchecks on real parent/candidate cell graphs; no board or PnR."""
from pathlib import Path
import importlib.util,json,hashlib,copy
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r21r2_audit',HERE/'audit_routed.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old,op=a.routed_cells(a.PARENT/'impl/pnr/console_neo.vo');on=(a.PARENT/'console_neo.vg').read_text();nn=(a.BUILD/'console_neo.vg').read_text()
# A real old VO must never be accepted as the changed candidate merely because most cells match.
r=a.structural(old,op,old,op,on,nn)
assert not r['passed'] and r['reset_gate_errors'] and r['helper_errors']
# Derive a fixture from the synthesized candidate helper and real parent graph.
# This fixture is a graph checker test, explicitly NOT a routed or timing result.
flat,hp=a.flatten_helper(nn);top=a.b.cells(a.b.block(on,'console_neo'))['u_reset_trial'][1]
root_port=lambda n: top[n] if n in top else None
aliases={}
for n in flat:
 for v in flat[n][1].values():
  if v.startswith('@'):
   m=a.re.fullmatch(r'@(\w+)(\[\d+\])?',v);base,sl=m[1],m[2] or ''
   x='neo_qualified_pll_ready' if base=='pll_ready' else top[base]
   aliases[v]=a.re.sub(r'\[\d+:\d+\]$','',x)+sl if sl else x
aliases.update({'$GND':'GND','$VCC':'VCC'})
new={n:v for n,v in old.items() if not n.startswith(a.PREFIX)}
for n,(k,pins) in flat.items():
 if k in ('GND','VCC'):continue
 new[n]=[k,{p:aliases.get(v,v) for p,v in pins.items()}]
new['neo_qualified_pll_lut']=['LUT2',dict(F='neo_qualified_pll_ready',I0='pll_ae350_lock',I1='ae350_rst_sync[1]')]
new['u_soc/neo_qualified_clear_lut']=['LUT2',dict(F='neo_qualified_clear',I0='ae350_rst_sync[1]',I1='trial_request')]
for n in ['u_soc/init_sync_0_s0','u_soc/init_sync_1_s0']:
 k,pins=new[n];new[n]=[k,dict(pins,CLEAR='neo_qualified_clear')]
np={k:v for k,v in op.items() if not k.startswith(a.PREFIX)};np.update(hp)
np['neo_qualified_pll_lut.INIT']="4'h2";np['u_soc/neo_qualified_clear_lut.INIT']="4'hB"
base=a.structural(old,op,new,np,on,nn);assert base['passed'],json.dumps(base)[:6000]
tests={'old_routed_parent_rejected':True,'synthetic_candidate_graph_accepted':True}
def expect_bad(name,mut):
 cells=copy.deepcopy(new);params=dict(np);mut(cells,params)
 result=a.structural(old,op,cells,params,on,nn);assert not result['passed'],name;tests[name]=True
expect_bad('clear_wrong_source_rejected',lambda c,p:c['u_soc/init_sync_1_s0'][1].update(CLEAR='ae350_rst_sync[1]'))
expect_bad('new_gate_wrong_init_rejected',lambda c,p:p.update({'neo_qualified_pll_lut.INIT':"4'h8"}))
expect_bad('original_ff_init_change_rejected',lambda c,p:p.update({'u_soc/init_sync_1_s0.INIT':"1'b1"}))
expect_bad('unexpected_original_cell_parameter_rejected',lambda c,p:p.update({'u_soc/init_sync_1_s0.EXTRA':"1'b1"}))
expect_bad('helper_pin_wrong_driver_rejected',lambda c,p:c['u_reset_trial/ready_meta_1_s0'][1].update(D='VCC'))
# Renaming an application net everywhere is harmless; the driver graph must prove it.
renamed=copy.deepcopy(new);q=renamed['ae350_rst_sync_0_s0'][1]['Q']
for k,pins in renamed.values():
 for pin,value in list(pins.items()):
  if value==q:pins[pin]='renamed_first_reset_net'
assert a.structural(old,op,renamed,np,on,nn)['passed'];tests['consistent_net_alias_accepted']=True
result=dict(passed=True,tests=tests,scope='Graph-checker positive/negative tests using a synthetic candidate graph; NOT a routed result',inputs={str(p):sha(p) for p in [Path(__file__),HERE/'audit_routed.py',a.PARENT/'impl/pnr/console_neo.vo',a.PARENT/'console_neo.vg',a.BUILD/'console_neo.vg']})
(HERE/'audit_negative_controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
