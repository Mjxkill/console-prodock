#!/usr/bin/env python3
"""Read-only R21r1 audit. Every incomplete proof stays explicit; never authorizes load."""
import functools
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path('/home/michael/console/TESTS/neo_720p_20261012/capture_memory_20261027')))
sys.path.insert(0,str(Path('/home/michael/console/tools')))
import build_memory_capture as b
import format_r21r1 as fmt
sys.path.insert(0,str(b.HERE.parent/'reset_sequence_20261025'))
from audit_routed import cells
from check_geometry_timing import inspect
from neo.timing import timing_checks
from neo.timing_closure import global_clock_routes
LOCAL='u_accel/u_v1/u_pixels/u_capture/'
BUS='u_gpu_debug/u_capture_bus/'
EXTRA={'u_accel/trace_observe_pixel_valid'}|{
 'u_accel/u_v1/u_pixels/u_copy/trace_observe_'+n for n in ('idle','low_one','check','validate')}

def clean(s):return s.replace('\\','')
def vec(s):
 v=tuple(float(n) for n in s.split(':'));assert len(v)==3,s
 return v

def drivers(data):
 result={}
 for name,(kind,pins) in data.items():
  for pin in ('Q','F','O','G','V'):
   if pin in pins:
    key=('constant',kind) if kind in ('GND','VCC') else (name,pin)
    result.setdefault(pins[pin],set()).add(key)
 return result

def parse_sdf(sdf):
 assert '(TIMESCALE 1 ns)' in sdf
 incoming={};cq={};clocks={};setup={};parsed={'IOPATH':0,'INTERCONNECT':0}
 def edge(dst,src,delay):incoming.setdefault(dst,[]).append((src,delay))
 def delays(text):
  assert re.fullmatch(r'(?:\([-+\d.eE:]+\)\s*)+',text),text
  values=[vec(v) for v in re.findall(r'\(([-+\d.eE:]+)\)',text)]
  assert values,text
  return tuple(max(v[i] for v in values) for i in range(3))
 for part in sdf.split('\n  (CELL\n')[1:]:
  m=re.search(r'\(INSTANCE ([^\s)]+)\)',part)
  if not m:continue
  name=clean(m[1]);kind=re.search(r'\(CELLTYPE "([^"]+)"\)',part)[1]
  for line in part.splitlines():
   if '(IOPATH ' in line:
    m=re.fullmatch(r'\s*\(IOPATH (?:\((?:pos|neg)edge (\S+)\)|(\S+)) ([^\s(]+)\s*(.+)\)\s*',line)
    assert m,line
    source,dest,delay=clean(m[1] or m[2]),clean(m[3]),delays(m[4]);parsed['IOPATH']+=1
    if kind.startswith('DFF'):
     if source=='CLK' and dest=='Q':cq[name]=delay
    else:edge(name+'/'+dest,name+'/'+source,delay)
   if '(SETUPHOLD ' in line and kind.startswith('DFF'):
    m=re.search(r'\(SETUPHOLD \((?:pos|neg)edge (\w+)\) \((?:pos|neg)edge CLK\) \(([^)]+)\)',line)
    assert m,line
    target=name+'/'+m[1];setup[target]=max(setup.get(target,0),max(vec(m[2])))
 for line in sdf.splitlines():
  if '(INTERCONNECT ' in line:
   m=re.fullmatch(r'\s*\(INTERCONNECT (\S+) (\S+) (.+)\)\s*',line);assert m,line
   source,dest,delay=clean(m[1]),clean(m[2]),delays(m[3]);parsed['INTERCONNECT']+=1
   edge(dest,source,delay)
   if dest.endswith('/CLK'):
    key=dest.removesuffix('/CLK');assert key not in clocks,key
    clocks[key]=(source,delay)
 raw={k:len(re.findall(r'\('+k+r'\s',sdf)) for k in parsed};assert parsed==raw,(parsed,raw)
 return incoming,cq,clocks,setup,parsed

def clock_period(sdc,tr,name):
 m=re.findall(r'^create_clock -name '+name+r' -period ([\d.]+)',sdc,re.M);assert len(m)==1,name
 n=re.findall(r'^\s*\d+\s+'+name+r'\s+Base\s+([\d.]+)\s',tr,re.M);assert len(n)==1,name
 assert float(m[0])==float(n[0]),(m,n)
 return float(m[0])

def main():
 build=Path('/home/michael/console/tang/impl/console_neo_n56r21r2_resetqual_coupled');out=Path(__file__).resolve().parent/'postroute_01/observer';assert not out.exists()
 assert json.loads((build/'route_result.json').read_text())['status']=='ROUTED_NOT_QUALIFIED'
 data=json.loads((build/'assembly.json').read_text())
 for name,h in data['inputs'].items():assert b.sha(build/name)==h,name
 assert b.manifest(build/'source')==json.loads((build/'sources.json').read_text())
 b.parent_guard()
 pnr=build/'impl/pnr'
 files=[Path(__file__),build/'assembly.json',build/'sources.json',build/'console_neo.vg',build/'route_result.json',build/'build.tcl',
 b.PARENT/'impl/pnr/console_neo.vo',build/'source/tang/boards/neo/neo.sdc',build/'source/tang/boards/neo/neo_capture_bus.v']+[
 pnr/('console_neo'+e) for e in ('.vo','.sdf','.tr','.fs','.rpt.txt')]
 hashes={str(p):b.sha(p) for p in files}
 tr=(pnr/'console_neo.tr').read_text();rpt=(pnr/'console_neo.rpt.txt').read_text();sdc=(build/'source/tang/boards/neo/neo.sdc').read_text()
 gpu_period=clock_period(sdc,tr,'ddr3_sys_clk');bus_period=clock_period(sdc,tr,'bus80_clk')
 old,op=cells(b.PARENT/'impl/pnr/console_neo.vo');new,np=cells(pnr/'console_neo.vo');od,nd=drivers(old),drivers(new)
 # Resolve exactly the five synth-generated aliases, not arbitrary LOCAL names.
 helper=b.block((build/'console_neo.vg').read_text(),'neo_capture_local')
 held_alias={int(i):(None if value=='GND' else int(j)) for i,value,j in
             re.findall(r'^assign held\[(\d+)\] = (GND|held\[(\d+)\]);',helper,re.M)}
 assert held_alias=={50:49,55:None,61:None,62:60,63:60},held_alias
 expected_bus_changes={};bus_bit_errors=[];bus_bit_map={}
 for i in range(64):
  lut=BUS+'n'+str(320-i)+'_s1'
  j=held_alias.get(i,i);net='GND' if j is None else 'trace_held['+str(j)+']'
  before=old.get(lut);after=new.get(lut)
  desired=dict(before[1],I1=net) if before else {}
  ok=bool(before and after and before[0]==after[0]=='LUT2' and after[1]==desired and np.get(lut+'.INIT')==op.get(lut+'.INIT')=="4'h8")
  if not ok:bus_bit_errors.append(dict(bit=i,lut=lut,actual=after,expected=desired))
  bus_bit_map[str(i)]=dict(lut=lut,net=net,alias_source=j,drivers=sorted(nd.get(net,set())))
  if ok and (before!=after or od.get(before[1]['I1'],set())!=nd.get(after[1]['I1'],set())):
   expected_bus_changes[lut]=dict(before=before,after=after,bit=i,
     driver_before=sorted(od.get(before[1]['I1'],set())),driver_after=sorted(nd.get(after[1]['I1'],set())))

 # New helper must also preserve its synthesized primitives and internal graph.
 hc=b.cells(helper);hp=b.params(helper);hd=drivers(hc)
 helper_errors=[];helper_external_pins=[];allowed_constant_pins=set()
 for name,(kind,pins) in hc.items():
  if kind in ('VCC','GND'):continue
  physical=LOCAL+name
  if physical not in new or new[physical][0]!=kind:
   helper_errors.append(dict(cell=physical,reason='missing/type'));continue
  for pin,net in pins.items():
   if pin in ('Q','F','O','G','V'):continue
   expected=hd.get(net,set());actual=nd.get(new[physical][1].get(pin),set())
   if expected and all(n=='constant' for n,p in expected):allowed_constant_pins.add(physical+'/'+pin)
   if expected:
    expected={(n if n=='constant' else LOCAL+n,p) for n,p in expected}
    if actual!=expected:helper_errors.append(dict(cell=physical,pin=pin,expected=sorted(expected),actual=sorted(actual)))
   else:helper_external_pins.append(dict(cell=physical,pin=pin,source_port=net,actual_net=new[physical][1].get(pin),actual_drivers=sorted(actual)))
 for key,value in hp.items():
  if np.get(LOCAL+key)!=value:helper_errors.append(dict(parameter=LOCAL+key,expected=value,actual=np.get(LOCAL+key)))
 helper_unexpected=sorted(n for n in new if n.startswith(LOCAL) and n.removeprefix(LOCAL) not in hc)
 missing=sorted(n for n in old.keys()-new.keys() if not n.startswith(LOCAL));changed={};aliases={}
 for name in old.keys()&new.keys():
  if name.startswith(LOCAL) or name in expected_bus_changes:continue
  ok,oi=old[name];nk,ni=new[name]
  delta={p:dict(before=oi.get(p),after=ni.get(p)) for p in oi.keys()|ni.keys() if oi.get(p)!=ni.get(p) or od.get(oi.get(p),set())!=nd.get(ni.get(p),set())}
  if ok==nk and not delta:continue
  equivalent=ok==nk
  for item in delta.values():
   src=od.get(item['before'],set());dst=nd.get(item['after'],set())
   item['driver_identity_before']=sorted(src);item['driver_identity_after']=sorted(dst)
   # No alias proof may hide a changed/new observer driver. Existing bus
   # connections from the helper are reviewed separately as observation-only.
   equivalent &= bool(src) and src==dst and len(src)==1 and not any(k[0].startswith(LOCAL) for k in src)
  (aliases if equivalent else changed)[name]=dict(before=old[name],after=new[name],pin_changes=delta)
 params_changed={k:dict(before=v,after=np.get(k)) for k,v in op.items() if not k.startswith(LOCAL) and np.get(k)!=v}
 additions=sorted(new.keys()-old.keys());unexpected_added=[n for n in additions if not n.startswith(LOCAL) and n not in EXTRA]
 incoming,cq,clocks,setup,parse_counts=parse_sdf((pnr/'console_neo.sdf').read_text())
 constants=[];terminal_kinds={};cycles=[];visiting=set();cone_gaps={}
 def terminal(pin):
  name,port=pin.rsplit('/',1)
  if name in new:
   kind,pins=new[name]
   if kind in ('GND','VCC'):return 'CONST:'+kind
   net=pins.get(port)
   src=nd.get(net,set())
   if src and all(n=='constant' for n,p in src):return 'CONST:'+str(sorted(src))
  return 'TERMINAL:'+pin
 @functools.lru_cache(None)
 def origins(pin):
  name,port=pin.rsplit('/',1)
  if name in cq and port=='Q':return {name:cq[name]}
  if name in new:
   kind,pins=new[name]
   if (kind.startswith('LUT') and port=='F') or (kind=='INV' and port=='O'):
    want={name+'/'+p for p in pins if p.startswith('I')}
    got={src for src,delay in incoming.get(pin,[])}
    if want!=got:cone_gaps[pin]=dict(expected=sorted(want),actual=sorted(got))
   elif port in pins and port not in ('Q','F','O','G','V'):
    want={n+'/'+p for n,p in nd.get(pins[port],set()) if n!='constant'}
    got={src for src,delay in incoming.get(pin,[])}
    if want and want!=got:cone_gaps[pin]=dict(expected=sorted(want),actual=sorted(got))
  if pin in visiting:cycles.append(pin);return {'CYCLE:'+pin:(0.,0.,0.)}
  if not incoming.get(pin):
   key=terminal(pin);terminal_kinds[pin]=key
   return {} if key.startswith('CONST:') else {key:(0.,0.,0.)}
  visiting.add(pin);found={}
  for source,delay in incoming[pin]:
   for origin,before in origins(source).items():
    value=tuple(a+c for a,c in zip(before,delay))
    found[origin]=tuple(max(a,c) for a,c in zip(value,found[origin])) if origin in found else value
  visiting.remove(pin);return found
 observer_ff={n:v for n,v in new.items() if n.startswith((LOCAL,BUS)) and v[0].startswith('DFF')}
 wrong_clocks={n:v for n,v in observer_ff.items() if v[1].get('CLK')!=('gpu_clk' if n.startswith(LOCAL) else 'vid_hclk')}
 sample=sorted(n for n in observer_ff if n.startswith((LOCAL+'at_event_',LOCAL+'after_event_')))
 memory=sorted(n for n in observer_ff if n.startswith(LOCAL+'mem_seen_'))
 held_ff=sorted(n for n in observer_ff if n.startswith(LOCAL+'held_'))
 shadow=sorted(n for n in observer_ff if n.startswith(BUS+'shadow_'))
 bad_observer_kinds={n:k for n,(k,pins) in observer_ff.items() if k!='DFFCE'}
 coverage={'sample48':len(sample)==48,'sticky4':len(memory)==4,'shadow64':len(shadow)==64,'held59':len(held_ff)==59}
 # Synthesis aliases:50=49,62=60,63=60; constant zeros:55 and61.
 held_bus=bus_bit_map;shadow_sources={};shadow_bad={};held_bit_driver={}
 for n,(kind,pins) in hc.items():
  q=pins.get('Q','');m=re.fullmatch(r'held\[(\d+)\]',q)
  if m:held_bit_driver[int(m[1])]=LOCAL+n
 assert set(held_bit_driver)==set(range(64))-set(held_alias)
 for i in range(64):
  j=held_alias.get(i,i);want={('constant','GND')} if j is None else {(held_bit_driver[j],'Q')}
  actual=set(tuple(x) for x in bus_bit_map[str(i)]['drivers'])
  if actual!=want:bus_bit_errors.append(dict(bit=i,expected_driver=sorted(want),actual=sorted(actual)))
 bounds=[];uncovered=[];crossings=[];clock_missing=[];terminals=[]
 for name in sample+memory+held_ff:
  for pin in ('D','CE'):
   if pin not in new[name][1]:continue
   target=name+'/'+pin;net=new[name][1][pin]
   if nd.get(net,set()) and all(n=='constant' for n,p in nd[net]):
    constants.append(target);continue
   found=origins(target)
   if not found:uncovered.append(target)
   for origin,delay in found.items():
    if origin.startswith(('TERMINAL:','CYCLE:')):
     terminals.append(dict(source=origin,destination=target));continue
    if origin not in clocks or name not in clocks or target not in setup:
     clock_missing.append(dict(source=origin,destination=target));continue
    sc,sd=clocks[origin];dc,dd=clocks[name]
    if sc!=dc or new[origin][1].get('CLK')!='gpu_clk' or new[origin][0].startswith('DFFN'):
     crossings.append(dict(source=origin,destination=target,source_clock=sc,destination_clock=dc));continue
    lower=gpu_period+min(dd)-max(sd)-max(delay)-setup[target]
    bounds.append(dict(source=origin,destination=target,conservative_setup_ns=lower,
     delay_by_corner_ns=delay,source_clock_by_corner_ns=sd,destination_clock_by_corner_ns=dd,setup_ns=setup[target]))
 held=[]
 for name in shadow:
  target=name+'/D';found=origins(target);shadow_sources[name]=list(found)
  foreign=[n for n in found if not n.startswith(LOCAL+'held_') and not n.startswith(BUS)]
  hs=[n for n in found if n.startswith(LOCAL+'held_')]
  bit=int(re.fullmatch(re.escape(BUS)+r'shadow_(\d+)_s1',name)[1])
  expected_const=held_alias.get(bit,bit) is None
  want_held=set() if expected_const else {held_bit_driver[held_alias.get(bit,bit)]}
  if foreign or set(hs)!=want_held:
   shadow_bad[name]={'foreign':foreign,'held_origins':hs,'expected_constant_zero':expected_const}
  for origin in hs:
   delay=found[origin];sp=setup.get(target)
   held.append(dict(source=origin,destination=name,max_by_corner_ns=delay,setup_ns=sp,
                    protocol_margin_ns=None if sp is None else 2*bus_period-max(delay)-sp))
 held_max=max((max(p['max_by_corner_ns']) for p in held),default=None)
 # Header constant bits may have no held FF only when proven in routed netlist;
 # currently any absent mapped origin remains in shadow_bad for explicit review.
 async_controls={n:{p:v for p,v in pins.items() if p in ('RESET','CLEAR','SET','PRESET') and
                   not (nd.get(v,set()) and all(x=='constant' for x,y in nd[v]))}
                 for n,(k,pins) in observer_ff.items()}
 async_controls={n:p for n,p in async_controls.items() if p}
 summary=inspect(build,'console_neo');timing=timing_checks(tr);routes=global_clock_routes(rpt)
 required=json.loads((build/'source/tang/boards/neo/timing_closure.json').read_text())['required_primary_clocks']
 missing_primary=sorted(set(required)-{n for n,k,_ in routes if k=='PRIMARY'})
 constraints=re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$',tr,re.M)
 expected={' '.join(l.split()) for l in sdc.splitlines() if l.startswith(('create_','set_','report_timing '))}
 constraints_passed=bool(constraints) and all(s=='Actived' for s,_ in constraints) and expected=={' '.join(c.split()) for _,c in constraints}
 min_bound=min((x['conservative_setup_ns'] for x in bounds),default=None)
 gates=dict(global_timing=summary['status']=='PASS' and set(timing)=={'setup','hold','recovery','removal'} and all(v>=0 for v in timing.values()),
  application_structural=not(missing or changed or params_changed or unexpected_added or bus_bit_errors),observer_clocks=not(wrong_clocks or bad_observer_kinds),
  observer_helper=not(helper_errors or helper_unexpected),observer_coverage=all(coverage.values()),observer_cones=bool(bounds) and not(uncovered or crossings or clock_missing or terminals or cycles or cone_gaps or set(constants)-allowed_constant_pins) and {x['destination'].rsplit('/',1)[0] for x in bounds}==set(sample+memory+held_ff),
  observer_setup=min_bound is not None and min_bound>0,
  held_shadow=bool(held) and not shadow_bad and all(x['protocol_margin_ns'] is not None and x['protocol_margin_ns']>0 for x in held),
  constraints=constraints_passed and not missing_primary)
 result=dict(audit_complete=True,hardware_access=False,loaded=False,load_authorized=False,root_review_required=True,
  build=str(build),input_sha256=hashes,bitstream_sha256=b.sha(pnr/'console_neo.fs'),netlist_sha256=b.sha(build/'console_neo.vg'),
  qualification_status='PASS' if all(gates.values()) else 'FAIL',gates=gates,timing=timing,timing_summary=summary,
  missing_parent_cells=missing,changed_parent_cells=changed,alias_only_parent_changes=aliases,changed_parent_parameters=params_changed,
  added_cells=additions,unexpected_added_cells=unexpected_added,application_structural_passed=gates['application_structural'],
  intentional_bus_observation_changes=expected_bus_changes,bus_bit_errors=bus_bit_errors,held_synthesis_aliases=held_alias,
  observer_ff_count=len(observer_ff),sample_ff_count=len(sample),sticky_ff_count=len(memory),shadow_ff_count=len(shadow),held_ff_count=len(held_ff),
  coverage=coverage,helper_errors=helper_errors,helper_unexpected=helper_unexpected,helper_external_pins=helper_external_pins,wrong_observer_clocks=wrong_clocks,bad_observer_kinds=bad_observer_kinds,observer_async_controls=async_controls,sdf_parse_counts=parse_counts,
  sample_setup_bounds=bounds,sample_setup_lower_bound_ns=min_bound,sample_cone_without_registered_origins=uncovered,
  sample_missing_clock_or_setup=clock_missing,sample_async_origins=crossings,sample_terminal_origins=terminals,
  constant_destination_pins=constants,unexpected_constants=sorted(set(constants)-allowed_constant_pins),cone_gaps=cone_gaps,terminal_kinds=terminal_kinds,combinational_cycles=cycles,
  held_shadow_paths=held,held_shadow_max_ns=held_max,held_shadow_bad=shadow_bad,held_sources_by_bit=held_bus,
  held_shadow_protocol_budget_ns=2*bus_period,held_shadow_bound_passed=gates['held_shadow'],
  protocol_budget_basis='Two additional destination bus cycles after observing synchronized ACK. held and ACK launch at the same GPU edge; budget includes source CQ, full data path and destination setup. Existing SDC max_delay8ns remains unchanged and its STA failures are reported separately.',
  clock_periods_ns={'ddr3_sys_clk':gpu_period,'bus80_clk':bus_period},required_primary=required,missing_primary=missing_primary,
  global_routes=routes,constraints_passed=constraints_passed,active_constraints=len(constraints),
  limits=['No hardware or complete GPU qualification; root review and explicit diagnostic exception required.',
  'Cross-corner SDF local bounds are deliberately conservative, not independent STA.',
  'SDF missing reset arcs are not zero: async controls are enumerated, recovery/removal remain global STA.',
  'Missing origin/clock/setup, mismatched count or CDC origin fails an explicit gate; no automatic waiver.'])
 assert all(b.sha(Path(p))==h for p,h in hashes.items())
 out.mkdir();b.save(out/'result.json',result)
 print(json.dumps({k:result[k] for k in ['bitstream_sha256','qualification_status','gates','timing','application_structural_passed',
  'observer_ff_count','sample_ff_count','sticky_ff_count','sample_setup_lower_bound_ns','held_shadow_max_ns','missing_primary']}),flush=True)
if __name__=='__main__':main()
