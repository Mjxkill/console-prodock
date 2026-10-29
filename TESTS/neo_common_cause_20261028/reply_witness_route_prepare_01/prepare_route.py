#!/usr/bin/env python3
"""R22 UTW1: prepare/check only. This program never launches Gowin or hardware."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FROZEN=ROOT/'TESTS/neo_common_cause_20261028/reply_witness_candidate_01'
CANDIDATE=FROZEN/'candidate_01'
PARENT=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
OUT=ROOT/'tang/impl/console_neo_n56r22_utw1'
NET_SHA='fa0185400736119ed68d6792656b6a80e328742acfa1deff7e7acdc02e4f24d1'
MANIFEST_SHA='4ee235ce1aef6c57a8fe647b9138533e616549e78d35a05c627277bc4414e1c2'
TOOL_SHA='a387ae6cdf022748a243757b4aedd98c39d12e26e224d70620bb4d7896b49522'
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,PRIMITIVES
sys.path.insert(0,str(FROZEN))
import prepare_candidate as frozen

def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def manifest(path):return {str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
def block(text,name):
 matches=list(re.finditer(r'^module\s+'+re.escape(name)+r'\b.*?^endmodule[^\n]*',text,re.M|re.S))
 require(len(matches)==1,'module '+name);return matches[0][0]

def compatibility():
 old_prim=Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')
 require(sha(old_prim)=='2ec53fec48601d2d491299bc3a28b4b199d3a79708f1dd38f72555a5c688ebd5','old simulation library changed')
 old,new=old_prim.read_text(),PRIMITIVES.read_text()
 helper=json.loads((FROZEN/'mapping_02/helper.json').read_text())['modules']['neo_usb_reply_witness']
 kinds=sorted({c['type'] for c in helper['cells'].values()}-{'$scopeinfo'})
 records={};parameters={}
 for kind in kinds:
  a,b=block(old,kind),block(new,kind)
  require(a==b,'helper primitive changed in installed Gowin '+kind)
  ports=set(re.search(r'^module\s+\w+\s*\(([^)]*)\)',b,re.M)[1].replace(' ','').split(','))
  params=set(re.findall(r'\bparameter\s+(\w+)\s*=',b))
  records[kind]=dict(identical_between_libraries=True,sha256=hashlib.sha256(a.encode()).hexdigest(),ports=sorted(ports),parameters=sorted(params))
  parameters[kind]=params
 for name,cell in helper['cells'].items():
  if cell['type']=='$scopeinfo':continue
  info=records[cell['type']]
  require(set(cell['connections'])==set(info['ports']),'primitive pin mismatch '+name)
  require(set(cell['parameters'])<=set(info['parameters']),'primitive parameter mismatch '+name)
  require(all(len(v)==1 for v in cell['connections'].values()),'unexpected vector primitive pin '+name)
  if cell['type']=='DFFRE':
   require(cell['connections']['CLK']==helper['ports']['hclk']['bits'],'non-HCLK FF '+name)
   require(cell['connections']['RESET']==helper['ports']['hreset']['bits'],'non-hreset FF '+name)
 require(sum(c['type']=='DFFRE' for c in helper['cells'].values())==402,'witness FF count')
 text=block((CANDIDATE/'console_neo.vg').read_text(),'neo_usb_reply_witness')
 # Gowin's netlist reader requires declarations before cells. A previous
 # diagnostic failed precisely on declarations appended after instances.
 first_cell=re.search(r'^\s*(?:DFFRE|ALU|LUT[1-4]|MUX2_LUT[5-8]|VCC|GND)\s',text,re.M).start()
 require(not re.search(r'^\s*(?:wire|input|output|inout)\s',text[first_cell:],re.M),'helper declaration after first cell')
 observer=block((CANDIDATE/'console_neo.vg').read_text(),'usb_idle_trace')
 require(observer.index('wire utw_read_hit;')<observer.index('utw_read_mux[0])'),'extension declaration order')
 require(sha(IDE/'bin/gw_sh')==TOOL_SHA,'Gowin launcher differs from reviewed R19 tool')
 return dict(passed=True,hardware_access=False,Gowin_executed=False,
  old_library=str(old_prim),old_library_sha256=sha(old_prim),current_library=str(PRIMITIVES),current_library_sha256=sha(PRIMITIVES),
  types=records,ff=402,all_new_ff_HCLK=True,all_new_ff_synchronous_hreset=True,
  declaration_order_checked=True,actual_Gowin_reader_acceptance='NOT_EXECUTED',tool=str(IDE/'bin/gw_sh'),tool_sha256=TOOL_SHA)

def frozen_guard():
 require(sha(FROZEN/'manifest.json')==MANIFEST_SHA,'frozen candidate manifest changed')
 saved=json.loads((FROZEN/'manifest.json').read_text())
 for name,digest in saved['files'].items():require(sha(FROZEN/name)==digest,'frozen candidate file changed '+name)
 frozen.parent_guard()
 require(sha(CANDIDATE/'console_neo.vg')==NET_SHA,'candidate netlist changed')
 require(manifest(CANDIDATE/'source')==json.loads((CANDIDATE/'sources.json').read_text()),'candidate source manifest changed')
 for p in ['helper_tests_02/result.json','integration_tests_02/result.json','guard_tests_01/result.json','offline_tests_03/result.json']:
  require(json.loads((FROZEN/p).read_text())['passed'],'frozen proof failed '+p)

def settings(parent=PARENT,out=OUT):
 text=(parent/'build.tcl').read_text()
 require(not re.search(r'\b(?:inc_place|inc_pnr|run\s+synthesis)\b',text),'incremental/synthesis option forbidden on changed netlist')
 require(text.count('run pnr')==1 and text.rstrip().endswith('run pnr'),'unexpected route script')
 changed=text.replace(str(parent),str(out))
 require(changed.replace(str(out),str(parent))==text,'nonreversible path rewrite')
 require([line for line in changed.splitlines() if line.startswith('add_file ')]==[
  'add_file {'+str(out/'console_neo.vg')+'}',
  'add_file {'+str(out/'source/tang/boards/neo/neo.cst')+'}',
  'add_file {'+str(out/'source/tang/boards/neo/neo.sdc')+'}'],'unexpected build inputs')
 return changed

def expected_audit():
 helper=json.loads((FROZEN/'mapping_02/helper.json').read_text())['modules']['neo_usb_reply_witness']
 return dict(schema=1,helper_prefix='u_usb_idle_trace/utw_observer/',observer_prefix='u_usb_idle_trace/',
  cell_counts=dict(Counter(c['type'] for c in helper['cells'].values() if c['type']!='$scopeinfo')),
  helper_ports=helper['ports'],helper_cells={n:c for n,c in helper['cells'].items() if c['type']!='$scopeinfo'},
  input_connections={'hclk':'vid_hclk','hreset':'u_usb_idle_trace/hreset','reply_valid':'u_usb_idle_trace/reply_valid','busy':'u_usb_idle_trace/busy','receive_index':'u_usb_idle_trace/receive_index','reply':'u_usb_idle_trace/reply','completed_count':'u_usb_idle_trace/snapshot_count','address':'u_usb_idle_trace/address'},
  read_registers=[f'u_usb_idle_trace/hrdata_{i}_s0' for i in range(32)],muxes=[f'u_usb_idle_trace/utw_mux_{i}' for i in range(32)],
  mux_INIT=0xca,ff_count=402,read_data_latency='existing hrdata DFFRE only',new_CDC=False,
  mandatory=['All 402 DFFRE present, same HCLK and synchronous hreset; no memory substituted.',
   'All helper cell pins/parameters and port taps compared by driver identity, not just net spelling.',
   'All 32 read mux INIT=0xca; original D path on I0, witness on I1, read_hit on I2.',
   'Original hrdata CLK/CE/RESET/Q unchanged; no driver from witness feeds old state/control.',
   'No new false path/multicycle/clock exemption; all same-HCLK setup/hold paths covered.',
   'Check reply taps -> witness D, index/reply_valid/busy -> CE/flags, hreset -> RESET, address -> mux -> hrdata D.',
   'Include helper internal counter/data/read paths and original source timing after added fanout.',
   'Global setup/hold/recovery/removal and PLL/DDRx/USB/HDMI/reset deltas stay explicit.',
   'Missing names, aliases not proven, missing SDF arcs or unreported endpoints remain incomplete/FAIL.'])

def prepare():
 frozen_guard();lib=compatibility();contract=before_build('neo',candidate=True)
 script=settings();require(not OUT.exists(),'output exists; do not reuse candidate folder')
 OUT.mkdir();shutil.copytree(CANDIDATE/'source',OUT/'source')
 for name in ['console_neo.vg','sources.json'] :shutil.copy2(CANDIDATE/name,OUT/name)
 for name in ['font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
  destination=OUT/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,destination)
 (OUT/'build.tcl').write_text(script)
 save(OUT/'primitive_compatibility.json',lib);save(OUT/'postroute_expected.json',expected_audit())
 record_build(OUT,contract)
 require(manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text()),'copied source mismatch')
 for name in ['neo.cst','neo.sdc']:require(sha(OUT/'source/tang/boards/neo'/name)==sha(PARENT/'source/tang/boards/neo'/name),'changed inherited '+name)
 require(sha(OUT/'console_neo.vg')==NET_SHA,'copy netlist mismatch')
 inputs=['console_neo.vg','sources.json','build.tcl','primitive_compatibility.json','postroute_expected.json',
  'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']
 save(OUT/'preparation.json',dict(prepared=True,candidate=True,board='neo',hardware_access=False,Gowin_executed=False,routing_started=False,release_qualified=False,
  parent=str(PARENT),frozen_candidate=str(CANDIDATE),netlist_sha256=NET_SHA,frozen_manifest_sha256=MANIFEST_SHA,
  builder=str(Path(__file__)),builder_sha256=sha(Path(__file__)),tool=str(IDE/'bin/gw_sh'),tool_sha256=TOOL_SHA,
  identical_parent_CST=True,identical_parent_SDC=True,identical_parent_options=True,path_rewrite_only=True,
  full_pnr_required=True,incremental_pnr=False,new_constraints=False,
  new_constraints_reason='All witness state and read mux are in existing bus80/HCLK domain, which is already constrained. No CDC or new clock. Actual STA coverage still mandatory.',
  source_owner='isolated Neo snapshot; common and reference sources unchanged',inputs={name:sha(OUT/name) for name in inputs},
  local_regressions=contract['local_regressions'],pending=['Root review and separate Gowin launch.','Gowin reader acceptance; complete P&R and post-route audit.','No hardware qualification by preparation.']))
 print(json.dumps(dict(prepared=True,path=str(OUT),preparation_sha256=sha(OUT/'preparation.json'),netlist_sha256=NET_SHA,Gowin_executed=False)))

def check():
 frozen_guard();lib=compatibility();record=json.loads((OUT/'preparation.json').read_text())
 require(record['builder_sha256']==sha(Path(__file__)),'preparer changed')
 require(record['netlist_sha256']==NET_SHA,'wrong prepared identity')
 for name,digest in record['inputs'].items():require(sha(OUT/name)==digest,'prepared input changed '+name)
 require(manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text()),'prepared source changed')
 require((OUT/'build.tcl').read_text()==settings(),'build script changed')
 require(json.loads((OUT/'primitive_compatibility.json').read_text())==lib,'library audit changed')
 guard=before_build('neo',candidate=True)
 return dict(passed=True,prepared=str(OUT),netlist_sha256=NET_SHA,preparation_sha256=sha(OUT/'preparation.json'),local_regressions=guard['local_regressions'],Gowin_executed=False,hardware_access=False)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--prepare-only',action='store_true');group.add_argument('--check-only',action='store_true')
 args=parser.parse_args()
 if args.prepare_only:prepare()
 else:print(json.dumps(check()))
