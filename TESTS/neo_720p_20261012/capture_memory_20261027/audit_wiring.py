#!/usr/bin/env python3
"""Compositional check of actual R21 observation aliases, cells and LUT tables."""
import itertools
import json
import re
from pathlib import Path
import build_memory_capture as b

def lut(init,values):
 width,value=init.split("'h");return (int(value,16)>>sum(v<<i for i,v in enumerate(values)))&1

def main():
 before=(b.OUT/'parent.vg').read_text();after=(b.OUT/'console_neo.vg').read_text()
 old={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',before,re.M|re.S)}
 new={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',after,re.M|re.S)}
 result={'passed':False,'hardware_access':False,'routing_started':False,
         'netlist_sha256':b.sha(b.OUT/'console_neo.vg'),
         'inputs':{str(p):b.sha(p) for p in [Path(__file__),b.HERE/'build_memory_capture.py',b.OUT/'parent.vg',b.OUT/'console_neo.vg',b.OUT/'assembly.json']}}
 try:
  declarations={}
  for mod in ('gpu_accel','gpu_geometry','gpu_v1','gpu_copy565'):
   # Existing aliases/declarations are byte-identical subsets. Only added
   # observer aliases and declarations are permitted, no old alias is edited.
   decl=lambda s:set(re.findall(r'^(?:wire|assign)\s+[^;]+;',s,re.M))
   was,now=decl(old[mod]),decl(new[mod]);assert was<=now,(mod,was-now)
   declarations[mod]={'old_preserved':len(was),'new_observation_declarations':sorted(now-was)}
  ac,gc,pc,cc=(b.cells(new[n]) for n in ('gpu_accel','gpu_geometry','gpu_v1','gpu_copy565'))
  ap,cp=b.params(new['gpu_accel']),b.params(new['gpu_copy565'])
  chain={
   'gpu_accel.u_v1.trace_mem_events':ac['u_v1'][1]['trace_mem_events'],
   'gpu_geometry.u_pixels.trace_mem_events':gc['u_pixels'][1]['trace_mem_events'],
   'gpu_v1.u_capture.mem_events':pc['u_capture'][1]['mem_events']}
  assert chain=={'gpu_accel.u_v1.trace_mem_events':'{v1_accepted,v1_pending,trace_pixel_valid}',
                'gpu_geometry.u_pixels.trace_mem_events':'trace_mem_events[2:0]',
                'gpu_v1.u_capture.mem_events':'{trace_mem_events[2:0],native_issue}'}
  assert ac['trace_observe_pixel_valid']==('INV',{'I':'n5020_4','O':'trace_pixel_valid'})
  assert ac['n5020_s1']==('LUT3',{'F':'n5020_4','I0':'native_valid','I1':'cache_valid','I2':'copy_valid'})
  assert ac['v1_pending_s2'][1]['Q']=='v1_pending'
  assert ac['v1_accepted_s0'][1]['Q']=='v1_accepted'
  assert pc['native_valid_s1'][1]['D']=='native_issue'
  event_cases=0
  for issue,native,cache,copy,pending,accepted in itertools.product(range(2),repeat=6):
   producer=1-lut(ap['n5020_s1.INIT'],[native,cache,copy])
   assert producer==(native|cache|copy)
   # Evaluate the proven concatenations across both composite instances.
   accel_value=(accepted<<2)|(pending<<1)|producer
   geometry_value=accel_value&7
   actual=(geometry_value<<1)|issue
   expected=issue|((native|cache|copy)<<1)|(pending<<2)|(accepted<<3)
   assert actual==expected
   event_cases+=1
  aliases={int(i):b.norm(v) for i,v in re.findall(r'^assign trace_copy_sample\[(\d+)\] = ([^;]+);',new['gpu_copy565'],re.M)}
  assert set(aliases)==set(range(24))
  for i in range(8):
   ff=cc[f'packet_{80+i}_s0'];assert ff[0]=='DFFRE'
   assert ff[1]['D']==aliases[i]==f'packet[{80+i}]'
   assert ff[1]['Q']==aliases[8+i]==f'packet_0[{80+i}]'
   assert ff[1]['CE']==aliases[16]=='n7630_6'
   assert ff[1]['RESET']=='GND' and cp[f'packet_{80+i}_s0.INIT']=="1'b0"
  assert cc['descriptor_bad_0_s0'][1]['RESET']==aliases[17]=='n577_9'
  reset_driver=[(n,c) for n,c in cc.items() if c[1].get('O')=='n577_9']
  assert len(reset_driver)==1 and reset_driver[0][1]==('INV',{'O':'n577_9','I':'gpu_debug_state[50]'})
  assert aliases[18]=='state[41]' and aliases[22]=='copy_bad' and aliases[23]=='copy_done'
  assert pc['u_copy'][1]['trace_copy_sample']=='trace_copy_sample[23:0]'
  assert pc['u_capture'][1]['sample']=='trace_copy_sample[23:0]'
  for n in ('trace_observe_idle','trace_observe_low_one','trace_observe_check','trace_observe_validate'):
   assert n in cc
  cases=0
  for state,resetn,start in itertools.product(range(32),range(2),range(2)):
   bits=[(state>>i)&1 for i in range(5)]
   low_zero=lut(cp['l_31_s10.INIT'],[bits[1],bits[0],bits[2],bits[3]])
   low_one=lut(cp['trace_observe_low_one.INIT'],bits[:4])
   idle=lut(cp['trace_observe_idle.INIT'],[low_zero,bits[4]])
   check=lut(cp['trace_observe_check.INIT'],[low_one,bits[4]])
   validate=lut(cp['trace_observe_validate.INIT'],[low_one,bits[4]])
   ce=lut(cp['n7630_s2.INIT'],[bits[4],resetn,start,low_zero])
   assert (idle,check,validate)==(int(state==0),int(state==1),int(state==17))
   assert ce==int(state==0 and resetn and start)
   cases+=1
  result.update(passed=True,old_wire_assign_declarations=declarations,event_port_chain=chain,
                event_truth_cases=event_cases,copy_state_reset_start_truth_cases=cases,
                sample_aliases_lsb_first=aliases,reset_driver=reset_driver,
                scope='Exact composite netlist connections plus exhaustive Boolean evaluation; complements actual helper and COPY simulations, no physical timing claim')
 except Exception as e:result['error']=repr(e)
 finally:
  b.save(b.HERE/'wiring_audit.json',result);print(json.dumps(result),flush=True)
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
