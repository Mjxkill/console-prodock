#!/usr/bin/env python3
"""No Gowin launch: preparation checks and adversarial post-route fixtures."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import sys
from unittest.mock import patch
import prepare_route as p
import launch_route as launch
import audit_postroute as audit

def synthetic_route():
 old,old_params=audit.cells((p.PARENT/'impl/pnr/console_neo.vo').read_text())
 all_drivers=audit.drivers(old);expected=json.loads((p.OUT/'postroute_expected.json').read_text())
 keep={n for n in old if n.startswith(audit.OBS)}
 external={}
 for name,port in expected['helper_ports'].items():
  if port['direction']!='input':continue
  for i,bit in enumerate(port['bits']):
   net=expected['input_connections'][name]+(f'[{i}]' if len(port['bits'])>1 else '')
   p.require(bool(all_drivers.get(net)),'unresolved baseline input '+net)
   keep.update(n for n,pin in all_drivers[net] if n!='CONST');external[bit]=net
 old={n:old[n] for n in keep};new=deepcopy(old);params=dict(old_params)
 def net(bit):return external.get(bit,'__utw_bit_'+str(bit))
 for name,cell in expected['helper_cells'].items():
  physical=audit.PREFIX+name
  new[physical]=(cell['type'],{pin:net(bits[0]) for pin,bits in cell['connections'].items()})
  for param,value in cell['parameters'].items():params[physical+'.'+param]=str(len(value))+"'b"+value
 for i in range(32):
  mux=audit.OBS+f'utw_mux_{i}';ff=audit.OBS+f'hrdata_{i}_s0';result='__utw_mux_'+str(i)
  new[mux]=('LUT3',{'I0':old[ff][1]['D'],'I1':net(expected['helper_ports']['read_data']['bits'][i]),'I2':net(expected['helper_ports']['read_hit']['bits'][0]),'F':result})
  params[mux+'.INIT']="8'hca";new[ff][1]['D']=result
 return old,new,params,expected

def main():
 out=Path(sys.argv[1]) if len(sys.argv)>1 else p.HERE/'tests_final';out.mkdir(exist_ok=False);checks=[]
 p.check();checks.append(dict(name='real prepared candidate and library guards',passed=True))
 with tempfile.TemporaryDirectory(prefix='utw_review_guard_') as td:
  path=Path(td)/'review.json'
  good=dict(passed=True,purpose='UTW1 full PNR',netlist_sha256=p.NET_SHA,
   preparation_sha256=p.sha(p.OUT/'preparation.json'),launcher_sha256=p.sha(Path(launch.__file__)))
  path.write_text(json.dumps(good));launch.review_guard(path)
  for key,value in [('passed',False),('purpose','incremental'),('netlist_sha256','0'*64),('preparation_sha256','0'*64),('launcher_sha256','0'*64)]:
   path.write_text(json.dumps({**good,key:value}))
   try:launch.review_guard(path)
   except RuntimeError as exc:checks.append(dict(name='reject review '+key,passed=True,error=str(exc)))
   else:raise RuntimeError('accepted wrong review '+key)
  path.write_text(json.dumps(good))
  before={q.name for q in p.OUT.iterdir()}
  original_popen=launch.subprocess.Popen
  def only_inventory(command,*args,**kwargs):
   if command[:2]==['git','ls-files']:return original_popen(command,*args,**kwargs)
   raise AssertionError('Gowin/non-inventory process forbidden in this check-only test')
  with patch.object(sys,'argv',[launch.__file__,'--check-only','--review',str(path)]),patch.object(launch.subprocess,'Popen',side_effect=only_inventory),contextlib.redirect_stdout(io.StringIO()):
   launch.main()
  p.require({q.name for q in p.OUT.iterdir()}==before,'check-only mutated output')
  checks.append(dict(name='launcher check-only never spawns and creates no route output',passed=True))
 old,new,params,expected=synthetic_route()
 normal=audit.check_structure(old,new,params,expected)
 p.save(out/'synthetic_normal.json',normal)
 p.require(normal['passed'],'synthetic graph fails '+str(normal['errors'][:3]))
 checks.append(dict(name='synthetic physical aliases preserve full driver graph',passed=True))
 ffs=[n for n,(kind,pins) in new.items() if n.startswith(audit.PREFIX) and kind=='DFFRE']
 ff=next(n for n in ffs if 'r_raw1.bit_reg[0]' in n)
 ground=next(net for name,(kind,pins) in new.items() if kind=='GND' for pin,net in pins.items() if pin=='G')
 cases=[]
 for pin in ['CLK','RESET','CE','D']:
  changed=deepcopy(new);changed[ff][1][pin]=ground;cases.append(('wrong witness '+pin,changed,params))
 changed=deepcopy(new);del changed[ff];cases.append(('missing witness FF',changed,params))
 changed_params={**params,ff+'.INIT':"1'b1"};cases.append(('wrong witness INIT',new,changed_params))
 mux=audit.OBS+'utw_mux_0';changed=deepcopy(new);changed[mux][1]['I0']=changed[mux][1]['I1'];cases.append(('old read input replaced',changed,params))
 cases.append(('wrong mux truth table',new,{**params,mux+'.INIT':"8'hac"}))
 changed=deepcopy(new);changed[audit.OBS+'hrdata_0_s0'][1]['CE']=ground;cases.append(('old read CE changed',changed,params))
 changed=deepcopy(new);changed[audit.PREFIX+'unexpected_memory']=('SDPB',{'DO':'x'});cases.append(('RAM or unexpected cell added',changed,params))
 changed=deepcopy(new);changed[audit.OBS+'receive_index_0_s0'][1]['D']=changed[ff][1]['Q'];cases.append(('witness feeds application state',changed,params))
 for name,changed,pars in cases:
  result=audit.check_structure(old,changed,pars,expected)
  p.require(not result['passed'],'audit accepted '+name)
  checks.append(dict(name=name,passed=True,rejection_count=len(result['errors']),first_error=result['errors'][0]))
 # Empty timing reports must never constitute closure of the 434 registers.
 timing=audit.timing_inventory('', '', '',expected)
 p.require(timing['target_registers']==434 and len(timing['unreported_registers'])==434 and not timing['full_setup_hold_coverage_proven'],'missing timing coverage accepted')
 checks.append(dict(name='empty STA/SDF stays incomplete for all 434 registers',passed=True))
 p.save(out/'result.json',dict(passed=True,hardware_access=False,Gowin_executed=False,
  synthetic_routed_fixture=True,actual_candidate_routed=False,cases=checks,
  inputs={str(path):p.sha(path) for path in [Path(__file__),Path(p.__file__),Path(launch.__file__),Path(audit.__file__),p.OUT/'preparation.json',p.OUT/'postroute_expected.json']}))
 print(json.dumps(dict(passed=True,cases=len(checks),Gowin_executed=False)))

if __name__=='__main__':main()
