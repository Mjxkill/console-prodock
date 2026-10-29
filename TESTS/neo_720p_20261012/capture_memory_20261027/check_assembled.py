#!/usr/bin/env python3
"""Actual R21 mapped helper protocol and assembled COPY wires; no PnR."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import build_memory_capture as b

sys.path.insert(0,str(b.ROOT/'tools'))
from gowin_toolchain import PRIMITIVES
IVL=Path('/tmp/console-usb-sim-tools/extracted/usr')
ASSIST=b.ROOT/'TESTS/assisted_reviews_20261026'

def primitives(text,out):
 source=PRIMITIVES.read_text()
 modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',source,re.M|re.S)}
 needed={'GSR'}|(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',text,re.M))&modules.keys())
 while True:
  calls=set().union(*(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',modules[n],re.M)) for n in needed))
  new=needed|(calls&modules.keys())
  if new==needed:break
  needed=new
 path=out/'primitives.v'
 path.write_text('`timescale 1ns/1ps\n'+'\n'.join(re.findall(r'^primitive .*?^endprimitive',source,re.M|re.S))+'\n'+'\n'.join(modules[n] for n in sorted(needed)))
 return path,sorted(needed)

def run(out,files,args,marker):
 with (out/'compile.log').open('x') as log:
  subprocess.run([str(IVL/'bin/iverilog'),'-B',str(IVL/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(out/'sim.vvp'),*map(str,files)],stdout=log,stderr=log,check=True,timeout=180)
 runs=[]
 for name,options in args:
  path=out/(name+'.log')
  with path.open('x') as log:subprocess.run([str(IVL/'bin/vvp'),str(out/'sim.vvp'),*options],stdout=log,stderr=log,check=True,timeout=120)
  assert marker in path.read_text(),path
  runs.append(dict(name=name,passed=True,log_sha256=b.sha(path)))
 return runs

def main():
 b.prepared_guard();assembly=json.loads((b.OUT/'assembly.json').read_text())
 for name,h in assembly['inputs'].items():assert b.sha(b.OUT/name)==h,name
 out=b.HERE/'assembled_test_01';out.mkdir()
 helper=b.OUT/'capture_ip/neo_capture_local/neo_capture_local.vg'
 net=b.OUT/'console_neo.vg'
 result={'passed':False,'hardware_access':False,'routing_started':False,'netlist_sha256':b.sha(net),
  'inputs':{str(p):b.sha(p) for p in [Path(__file__),b.HERE/'build_memory_capture.py',b.OUT/'assembly.json',net,helper,PRIMITIVES]},'tests':{}}
 try:
  # Mapped helper body and untouched RTL bus use the already-reviewed complete
  # AHB/CDC protocol bench. A single top-level GSR replaces the synthesis GSR.
  folder=out/'protocol';folder.mkdir()
  htext=helper.read_text();htext,n=re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);','',htext);assert n==1
  mapped=folder/'helper.v';mapped.write_text(htext)
  original=ASSIST/'observer_copy_01/protocol_02/tb.sv';tb=original.read_text()
  tb=tb.replace('module tb;','module tb;\nGSR GSR(.GSRI(1\'b1));',1)
  bench=folder/'tb.sv';bench.write_text(tb)
  prim,used=primitives(htext,folder)
  bus=b.ROOT/'TESTS/neo_720p_20261012/local_capture_20261026/neo_capture_bus.v'
  debug=b.ROOT/'tang/impl/console_neo_n56r15_reset50ms/source/tang/boards/neo/neo_gpu_debug.v'
  files=[bench,mapped,prim,bus,debug]
  result['tests']['protocol']={'runs':run(folder,files,[('simulation',[])],'PASS local capture checks='),'primitives':used}
  for p in [original,*files]:result['inputs'][str(p)]=b.sha(p)
  # Complete dependency closure of gpu_geometry from the ASSEMBLED R21 .vg,
  # including the actual connected helper. No external observer or DUT edits.
  folder=out/'copy';folder.mkdir()
  modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',net.read_text(),re.M|re.S)}
  needed={'gpu_geometry'}
  while True:
   calls=set().union(*(set(re.findall(r'^\s*(\w+)\s+\\?\S+\s*\(',modules[n],re.M)) for n in needed))
   new=needed|(calls&modules.keys())
   if new==needed:break
   needed=new
  mapped=folder/'mapped.v';mapped.write_text('\n\n'.join(modules[n] for n in sorted(needed)))
  prim,used=primitives(mapped.read_text(),folder)
  spec=importlib.util.spec_from_file_location('copysim',ASSIST/'observer_copy_01/check_mapped_copy_r2.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  body=module.BODY
  body,n=re.subn(r'neo_capture_observed_test observer\(.*?\);','',body,flags=re.S);assert n==1
  original=ASSIST/'neo_fable_sim_01/copy_mapped_02/tb.sv'
  prefix=original.read_text().split('integer captures=0,')[0]
  for old,new in [('cap_arm','observer_arm'),('cap_snap','observer_snap'),('arm_ack','observer_arm_ack'),('snap_ack','observer_snap_ack'),
                  ('cap_ready','observer_ready'),('cap_beat','observer_beat'),('cap_held','observer_held')]:
   # Replace port VALUES only. Their declaration remains unused and harmless.
   prefix=prefix.replace('('+old+')','('+new+')')
  prefix=prefix.replace('gpu_geometry dut(\n','gpu_geometry dut(\n.trace_mem_events({2\'b00,(native_valid|cache_valid|copy_valid)}),\n',1)
  bench=folder/'tb.sv';bench.write_text(prefix+body)
  files=[bench,mapped,prim]
  result['tests']['copy']={'runs':run(folder,files,[(f'fault_{i}',[f'+fault={i}']) for i in range(4)],'PASS MAPPED COPY OBSERVER'),
   'modules':sorted(needed),'module_sha256':{n:hashlib.sha256(modules[n].encode()).hexdigest() for n in sorted(needed)},'primitives':used,
   'limits':'Geometry subset: true producer input supplied from actual native/cache/copy output flags; slot pending/accepted zero. Full gpu_accel provenance audited separately.'}
  for p in [original,Path(spec.origin),*files]:result['inputs'][str(p)]=b.sha(p)
  for path,h in result['inputs'].items():assert b.sha(Path(path))==h,path
  result['passed']=True
 except Exception as e:result['error']=repr(e)
 finally:
  result['logs']={str(p.relative_to(out)):b.sha(p) for p in out.rglob('*.log')}
  b.save(out/'result.json',result);print(json.dumps(result),flush=True)
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
