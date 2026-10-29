#!/usr/bin/env python3
"""Isolated R19 observation ECO. Prepare/synthesize/assemble only; no PnR/hardware."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment

PARENT=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
OUT=ROOT/'tang/impl/console_neo_n56r21_capture_memory'
BIT_SHA='1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
NET_SHA='dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'
HELP_SHA='1051163608ea69c7f56ebb2a4363a7ac773285e7284e3f532b377054602f7a90'
PROOFS=[ROOT/'TESTS/assisted_reviews_20261026/observer_copy_01'/n/'result.json'
        for n in ['protocol_02','mapped_copy_02','real_memory_events_01']]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def manifest(p):return {str(q.relative_to(p)):sha(q) for q in sorted(p.rglob('*')) if q.is_file()}
def norm(s):return re.sub(r'\s+','',s).replace('\\','')
def once(s,a,b):
 assert s.count(a)==1,a
 return s.replace(a,b,1)
def block(s,name):
 m=list(re.finditer(r'^module '+re.escape(name)+r'\b.*?^endmodule',s,re.M|re.S))
 assert len(m)==1,name
 return m[0][0]
def cells(s):
 return {norm(n):(k,{p:norm(v) for p,v in re.findall(r'\.(\w+)\(([^()]*)\)',ports)})
         for k,n,ports in re.findall(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',s,re.M|re.S)
         if k!='module'}
def params(s):
 return {norm(n):norm(v) for n,v in re.findall(r'^\s*defparam\s+(.+?)\s*=\s*([^;]+);',s,re.M)}
def add_ports(s,name,ports):
 s=once(s,'module '+name+' (\n','module '+name+' (\n'+''.join('  '+n+',\n' for n in ports))
 first=re.search(r'^(?:input|output|inout) ',s,re.M).start()
 return s[:first]+''.join(d+' '+w+n+';\n' for n,(d,w) in ports.items())+s[first:]
def add_instance_ports(s,name,ports):
 m=list(re.finditer(r'^\s*\w+\s+'+re.escape(name)+r'\s*\(\n',s,re.M));assert len(m)==1,name
 i=m[0].end();return s[:i]+''.join('    .'+n+'('+v+'),\n' for n,v in ports.items())+s[i:]
def append_logic(s,text):return once(s,'endmodule',text+'\nendmodule')

def verify_proofs():
 for proof in PROOFS:
  p=json.loads(proof.read_text());assert p['passed']
  for name,h in p['inputs'].items():
   f=Path(name);f=f if f.is_absolute() else ROOT/f
   assert sha(f)==h,name

def parent_guard():
 assert sha(PARENT/'console_neo.vg')==NET_SHA
 assert sha(PARENT/'impl/pnr/console_neo.fs')==BIT_SHA
 assert manifest(PARENT/'source')==json.loads((PARENT/'sources.json').read_text())
 assert sha(HERE/'neo_capture_memory.v')==HELP_SHA
 contract=json.loads((HERE/'contract.json').read_text())
 assert contract['helper_sha256']==HELP_SHA and contract['format']=='D*'
 verify_proofs()

def prepare():
 parent_guard();guard=before_build('neo',candidate=True)
 OUT.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',OUT/'source')
 for name in ['console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
  dest=OUT/('parent.vg' if name=='console_neo.vg' else name)
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,dest)
 helper=OUT/'source/tang/boards/neo/neo_capture_local.v'
 assert helper.is_file();shutil.copy2(HERE/'neo_capture_memory.v',helper)
 old=json.loads((PARENT/'sources.json').read_text());current=manifest(OUT/'source')
 assert set(old)==set(current)
 assert [p for p in old if old[p]!=current[p]]==['tang/boards/neo/neo_capture_local.v']
 save(OUT/'sources.json',current)
 folder=OUT/'capture_ip/neo_capture_local';folder.mkdir(parents=True)
 prj=ET.Element('Project');ET.SubElement(prj,'Version').text='beta'
 ET.SubElement(prj,'Device',id='GW5AST-138C',package='PBGA484A',speed='1',partNumber='GW5AST-LV138PG484AC1/I0')
 files=ET.SubElement(prj,'FileList');ET.SubElement(files,'File',path=str(helper),type='verilog')
 opts=ET.SubElement(prj,'OptionList')
 for k,v in [('disable_insert_pad','1'),('enable_dsrm','0'),('output_file','neo_capture_local.vg'),
             ('top_module','neo_capture_local'),('vcc','0.9'),('vccx','1.8'),('verilog_language','sysv-2017')]:
  ET.SubElement(opts,'Option',type=k,value=v)
 ET.indent(prj);ET.ElementTree(prj).write(folder/'helper.prj',encoding='utf-8',xml_declaration=True)
 (OUT/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)))
 shutil.copy2(Path(__file__),OUT/'build_memory_capture.py')
 record_build(OUT,guard)
 save(OUT/'preparation.json',dict(candidate=True,hardware_access=False,routing_started=False,
  parent=str(PARENT),parent_bitstream_sha256=BIT_SHA,parent_netlist_sha256=NET_SHA,
  common_sources_modified=False,application_RTL_changed=False,source_changes=['tang/boards/neo/neo_capture_local.v'],
  builder_sha256=sha(Path(__file__)),helper_sha256=HELP_SHA,
  external_inputs={str(p):sha(p) for p in [HERE/'contract.json',*PROOFS]},
  inputs={n:sha(OUT/n) for n in ['parent.vg','sources.json','build.tcl','capture_ip/neo_capture_local/helper.prj',
             'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc']}))
 print('R21 prepared; helper synthesis only authorized',flush=True)

def prepared_guard():
 parent_guard();before_build('neo',candidate=True)
 p=json.loads((OUT/'preparation.json').read_text());assert p['builder_sha256']==sha(Path(__file__))
 for n,h in p['inputs'].items():assert sha(OUT/n)==h,n
 for n,h in p['external_inputs'].items():assert sha(Path(n))==h,n
 assert manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text())

def synthesize():
 prepared_guard()
 tool=ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/GowinSynthesis'
 assert sha(tool)==sha(IDE/'bin/GowinSynthesis')
 folder=OUT/'capture_ip/neo_capture_local';assert not (folder/'neo_capture_local.vg').exists()
 attempt=len(list(folder.glob('synth_attempt_*.log')))+1;logpath=folder/f'synth_attempt_{attempt:02}.log'
 with logpath.open('x') as log:
  started=time.time();child=subprocess.Popen([str(tool),'-prj',str(folder/'helper.prj')],cwd=folder,env=environment(),stdout=log,stderr=log)
  print('R21_HELPER_SYNTH_STARTED pid='+str(child.pid),flush=True)
  rc=child.wait(timeout=180)
 text=logpath.read_text();ok=rc==0 and 'GowinSynthesis finish' in text and not re.search(r'^ERROR',text,re.M)
 result=dict(passed=ok,returncode=rc,pid=child.pid,tool_sha256=sha(tool),log_sha256=sha(logpath),
             started_unix=started,finished_unix=time.time(),hardware_access=False,routing_started=False)
 if ok:
  net=folder/'neo_capture_local.vg';assert not re.search(r'^\s*(?:I|O|IO)BUF\s',net.read_text(),re.M)
  result['netlist_sha256']=sha(net)
 save(folder/f'synth_attempt_{attempt:02}.json',result)
 if not ok:raise SystemExit('Helper synthesis failed; no route attempted')
 save(folder/'result.json',result);print('R21 helper synthesized; no route attempted',flush=True)

def assemble():
 prepared_guard()
 original=(OUT/'parent.vg').read_text();changed={}
 copy=block(original,'gpu_copy565');copycells=cells(copy)
 for i in range(80,88):
  assert copycells[f'packet_{i}_s0']==('DFFRE',dict(Q=f'packet_0[{i}]',D=f'packet[{i}]',CLK='gpu_clk',RESET='GND',CE='n7630_6'))
 assert copycells['n7630_s2'][1]==dict(F='n7630_6',I0='state_0[4]',I1='gpu_debug_state[50]',I2='state[41]',I3='l_31_18')
 assert params(copy)['n7630_s2.INIT']=="16'h4000"
 assert copycells['descriptor_bad_0_s0'][1]['RESET']=='n577_9'
 low=[f'packet[{i}]' for i in range(80,88)]+[f'packet_0[{i}]' for i in range(80,88)]
 low+=['n7630_6','n577_9','state[41]','trace_copy_idle','trace_copy_check','trace_copy_validate','copy_bad','copy_done']
 sample_alias='\n'.join(f'assign trace_copy_sample[{i}] = {v};' for i,v in enumerate(low))
 added_copy='''wire trace_copy_idle,trace_copy_low_one,trace_copy_check,trace_copy_validate;
LUT2 trace_observe_idle (.I0(l_31_18),.I1(state_0[4]),.F(trace_copy_idle));
defparam trace_observe_idle.INIT=4'h2;
LUT4 trace_observe_low_one (.I0(state_0[0]),.I1(state_0[1]),.I2(state_0[2]),.I3(state_0[3]),.F(trace_copy_low_one));
defparam trace_observe_low_one.INIT=16'h0002;
LUT2 trace_observe_check (.I0(trace_copy_low_one),.I1(state_0[4]),.F(trace_copy_check));
defparam trace_observe_check.INIT=4'h2;
LUT2 trace_observe_validate (.I0(trace_copy_low_one),.I1(state_0[4]),.F(trace_copy_validate));
defparam trace_observe_validate.INIT=4'h8;
'''+sample_alias
 new=add_ports(copy,'gpu_copy565',{'trace_copy_sample':('output','[23:0] ')})
 changed['gpu_copy565']=(copy,append_logic(new,added_copy))
 pixel=block(original,'gpu_v1')
 assert cells(pixel)['native_valid_s1'][1]['D']=='native_issue'
 new=add_ports(pixel,'gpu_v1',{'trace_mem_events':('input','[2:0] ')})
 new=add_instance_ports(new,'u_copy',{'trace_copy_sample':'trace_copy_sample[23:0]'})
 old_capture=re.search(r'  neo_capture_local u_capture \(.*?\);',new,re.S)[0]
 new_capture=re.sub(r'\.sample\(\{[^}]+\}\)', '.sample(trace_copy_sample[23:0]),.mem_events({trace_mem_events[2:0],native_issue})',old_capture)
 assert old_capture!=new_capture
 new=once(new,old_capture,new_capture)
 changed['gpu_v1']=(pixel,append_logic(new,'wire [23:0] trace_copy_sample;'))
 geom=block(original,'gpu_geometry')
 new=add_ports(geom,'gpu_geometry',{'trace_mem_events':('input','[2:0] ')})
 new=add_instance_ports(new,'u_pixels',{'trace_mem_events':'trace_mem_events[2:0]'})
 changed['gpu_geometry']=(geom,new)
 accel=block(original,'gpu_accel');ac=cells(accel)
 assert ac['n5020_s1'][1]==dict(F='n5020_4',I0='native_valid',I1='cache_valid',I2='copy_valid')
 assert params(accel)['n5020_s1.INIT']=="8'h01"
 assert ac['v1_pending_s2'][1]['Q']=='v1_pending' and ac['v1_accepted_s0'][1]['Q']=='v1_accepted'
 new=add_instance_ports(accel,'u_v1',{'trace_mem_events':'{v1_accepted,v1_pending,trace_pixel_valid}'})
 new=append_logic(new,'wire trace_pixel_valid;\nINV trace_observe_pixel_valid (.I(n5020_4),.O(trace_pixel_valid));')
 changed['gpu_accel']=(accel,new)
 helperpath=OUT/'capture_ip/neo_capture_local/neo_capture_local.vg'
 synth=json.loads((helperpath.parent/'result.json').read_text());assert synth['passed'] and sha(helperpath)==synth['netlist_sha256']
 helper=block(helperpath.read_text(),'neo_capture_local')
 helper,n=re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);','',helper);assert n==1
 oldhelper=block(original,'neo_capture_local');changed['neo_capture_local']=(oldhelper,helper)
 merged=original
 for old,new in changed.values():merged=once(merged,old,new)
 undone=merged
 for old,new in changed.values():undone=once(undone,new,old)
 assert undone==original
 # Verify every original application primitive and parameter. Composite port
 # changes are separately whitelisted observation-only additions below.
 primitive_audit={};addition_whitelist={
  'gpu_copy565':{'trace_observe_idle','trace_observe_low_one','trace_observe_check','trace_observe_validate'},
  'gpu_accel':{'trace_observe_pixel_valid'},'gpu_v1':set(),'gpu_geometry':set()}
 child_deltas={('gpu_copy565',None):{},('gpu_v1','u_copy'):{'trace_copy_sample':'trace_copy_sample[23:0]'},
  ('gpu_geometry','u_pixels'):{'trace_mem_events':'trace_mem_events[2:0]'},
  ('gpu_accel','u_v1'):{'trace_mem_events':'{v1_accepted,v1_pending,trace_pixel_valid}'}}
 for name in addition_whitelist:
  old,new=changed[name];oc,nc=cells(old),cells(new)
  assert set(nc)-set(oc)==addition_whitelist[name] and not set(oc)-set(nc)
  differences={n:(oc[n],nc[n]) for n in oc if oc[n]!=nc[n]}
  expected={child for (mod,child) in child_deltas if mod==name and child}
  if name=='gpu_v1':expected.add('u_capture')
  assert set(differences)==expected,(name,set(differences),expected)
  for (mod,child),extra in child_deltas.items():
   if mod==name and child:
    assert oc[child][0]==nc[child][0]
    assert nc[child][1]=={**oc[child][1],**extra}
  if name=='gpu_v1':
   assert nc['u_capture'][1]=={**oc['u_capture'][1],
     'sample':'trace_copy_sample[23:0]','mem_events':'{trace_mem_events[2:0],native_issue}'}
  op,np=params(old),params(new)
  assert all(np[k]==v for k,v in op.items())
  assert set(np)-set(op)=={n+'.INIT' for n in addition_whitelist[name] if nc[n][0].startswith('LUT')}
  primitive_audit[name]=dict(original_cells=len(oc),original_parameters=len(op),
                            changed_observation_instances=sorted(differences),added_observation_cells=sorted(addition_whitelist[name]))
 names=set(re.findall(r'^module (\w+)',original,re.M))
 assert names==set(re.findall(r'^module (\w+)',merged,re.M))
 assert all(block(original,n)==block(merged,n) for n in names-changed.keys())
 assert block(original,'console_neo')==block(merged,'console_neo')
 assert block(original,'neo_capture_bus')==block(merged,'neo_capture_bus')
 assert block(original,'neo_gpu_debug_0')==block(merged,'neo_gpu_debug_0')
 assert not (OUT/'console_neo.vg').exists();(OUT/'console_neo.vg').write_text(merged)
 (OUT/'observation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),merged.splitlines(True),fromfile='R19/console_neo.vg',tofile='R21/console_neo.vg')))
 save(OUT/'assembly.json',dict(candidate=True,passed=True,routing_started=False,hardware_access=False,
  parent_bitstream_sha256=BIT_SHA,parent_netlist_sha256=NET_SHA,netlist_sha256=sha(OUT/'console_neo.vg'),
  builder_sha256=sha(Path(__file__)),parent_recovered_byte_identical_by_undo=True,
  helper_replaced_only=True,changed_modules=sorted(changed),unchanged_modules=sorted(names-changed.keys()),
  original_application_primitives_and_parameters_intact=True,primitive_audit=primitive_audit,
  top_and_NCP_bus_unchanged=True,sourcewidth_bits=list(range(80,88)),sample_lsb_first=low,
  mem_events_lsb_first=['gpu_v1/native_issue','NOT gpu_accel/n5020_4','gpu_accel/v1_pending','gpu_accel/v1_accepted'],
  same_CST=True,same_SDC=True,same_PNR_options=True,same_DDR_PLL_reset=True,
  inputs={n:sha(OUT/n) for n in ['console_neo.vg','sources.json','build.tcl','observation.diff',
      'capture_ip/neo_capture_local/neo_capture_local.vg','capture_ip/neo_capture_local/result.json',
      'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc']},
  pending=['Mapped full wiring simulation and helper protocol test.',
           'Root review before PnR; timing and physical observer routes remain unqualified.',
           'Hardware repetition must establish whether original R19 symptoms persist.']))
 record_build(OUT,before_build('neo',candidate=True))
 print('R21 assembled; application primitives intact; no PnR launched',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','synth','assemble']);a=p.parse_args()
 {'prepare':prepare,'synth':synthesize,'assemble':assemble}[a.action]()
