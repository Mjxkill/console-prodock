#!/usr/bin/env python3
"""Prepare an isolated R22r1 launch copy, adding timing REPORTS only."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'TESTS/neo_common_cause_20261028/reply_witness_format_r1'))
import prepare_format as prior
from board_contract import before_build,record_build
require,sha,save=prior.require,prior.sha,prior.save
previous=prior.previous
PARENT=prior.OUT
OUT=ROOT/'tang/impl/console_neo_n56r22r1_utw1_reports'
SDC='tang/boards/neo/neo.sdc'
NET_SHA='0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191'
FORMAT_SHA='51dc9f89927ec99123004b0883f505c6a5008e36d8d85faf7fb1003790a8ee97'
DOC=Path('/home/michael/gowin/IDE/doc/EN/SUG940-2.0.4E_Gowin Design Timing Constraints User Guide.pdf')

def report_suffix(expected):
 regs=sorted(expected['helper_prefix']+name for name,cell in expected['helper_cells'].items() if cell['type']=='DFFRE')
 require(len(regs)==402,'not 402 witness FF')
 read=expected['read_registers'];require(len(read)==32,'not 32 read FF')
 regs+=read;require(len(set(regs))==434,'duplicate registers')
 require(all(re.fullmatch(r'[a-zA-Z0-9_/]+',r) for r in regs),'unsafe register name')
 lines=['','// UTW1 reports only: exact endpoints, no added or changed timing constraints.',
 '// SUG940-2.0.4E section 5.5.1. Each D/CE/RESET pin is queried separately.',
 '// Missing, empty or capped reports remain unproven and must be audited after route.']
 endpoints=[]
 for reg in regs:
  for pin in ('D','CE','RESET'):
   endpoint=reg+'/'+pin;endpoints.append(endpoint)
   for mode in ('setup','hold'):
    lines.append('report_timing -'+mode+' -to [get_pins {'+endpoint+'}] -max_paths 10000 -max_common_paths 3')
 return '\n'.join(lines)+'\n',endpoints

def validate_sdc(parent,candidate,expected):
 suffix,endpoints=report_suffix(expected)
 require(candidate==parent+suffix,'SDC differs beyond exact reporting suffix')
 commands=[line for line in suffix.splitlines() if line and not line.startswith('//')]
 require(len(commands)==2604,'missing report statements')
 require(all(re.fullmatch(r'report_timing -(setup|hold) -to \[get_pins \{[a-zA-Z0-9_/]+\}\] -max_paths 10000 -max_common_paths 3',line) for line in commands),'non-report or unexpected command')
 return dict(passed=True,parent_sdc_prefix_byte_identical=True,timing_constraints_changed=False,
  setup_reports=1302,hold_reports=1302,registers=434,pins_per_register=['D','CE','RESET'],
  per_report_max_paths=10000,max_common_paths=3,endpoint_names=endpoints,
  caveat='Requests only; actual name resolution, active endpoint coverage and STA results must be checked after routing. No closure claim.')

def prepare():
 checked=prior.check();require(sha(PARENT/'format_assembly.json')==FORMAT_SHA,'parent assembly changed')
 require(checked['netlist_sha256']==NET_SHA,'wrong logic')
 expected=json.loads((PARENT/'postroute_expected.json').read_text())
 parent_sdc=(PARENT/'source'/SDC).read_text();suffix,_=report_suffix(expected)
 proof=validate_sdc(parent_sdc,parent_sdc+suffix,expected)
 contract=before_build('neo',candidate=True)
 OUT.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',OUT/'source')
 files=['console_neo.vg','helper_normalized.v','observer_normalized.v','serialization_proof.json','postroute_expected.json',
        'font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']
 for name in files:
  dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,dest)
 (OUT/'source'/SDC).write_text(parent_sdc+suffix)
 sources=previous.manifest(OUT/'source');old=json.loads((PARENT/'sources.json').read_text())
 require(set(sources)==set(old),'source inventory changed')
 require([name for name in sources if sources[name]!=old[name]]==[SDC],'source changed beyond SDC')
 save(OUT/'sources.json',sources)
 (OUT/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)))
 save(OUT/'timing_report_requests.json',proof)
 record_build(OUT,contract)
 inputs=files+['sources.json','build.tcl','timing_report_requests.json','source/'+SDC,'source/tang/boards/neo/neo.cst']
 save(OUT/'reports_assembly.json',dict(passed=True,candidate=True,hardware_access=False,Gowin_executed=False,
  parent=str(PARENT),format_assembly_sha256=FORMAT_SHA,netlist_sha256=NET_SHA,
  builder_sha256=sha(Path(__file__)),logic_test_proof=checked['validation'],
  same_netlist=True,same_CST=True,same_options=True,source_RTL_changed=False,timing_constraints_changed=False,
  SDC_difference='Append 2604 report_timing setup/hold requests; exact original SDC prefix retained.',
  sources_difference=[SDC],parent_sources_sha256=sha(PARENT/'sources.json'),parent_sdc_sha256=sha(PARENT/'source'/SDC),
  official_syntax_reference=dict(path=str(DOC),sha256=sha(DOC),section='5.5.1, pages 73-75'),
  inputs={name:sha(OUT/name) for name in inputs},local_regressions=contract['local_regressions'],
  pending=['Root review before sole full PNR launch.','Gowin reader acceptance, routed structure and resolved timing endpoints.','Hardware unqualified.']))
 print(json.dumps(dict(prepared=True,path=str(OUT),netlist_sha256=NET_SHA,reports_assembly_sha256=sha(OUT/'reports_assembly.json'))))

def check():
 checked=prior.check();require(checked['netlist_sha256']==NET_SHA,'parent netlist changed')
 require(sha(PARENT/'format_assembly.json')==FORMAT_SHA,'parent assembly changed')
 record=json.loads((OUT/'reports_assembly.json').read_text());require(record['builder_sha256']==sha(Path(__file__)),'report builder changed')
 for name,digest in record['inputs'].items():require(sha(OUT/name)==digest,'report launch input changed '+name)
 require(previous.manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text()),'source snapshot changed')
 expected=json.loads((OUT/'postroute_expected.json').read_text())
 validate_sdc((PARENT/'source'/SDC).read_text(),(OUT/'source'/SDC).read_text(),expected)
 require(sha(OUT/'console_neo.vg')==NET_SHA,'different tested netlist')
 require((OUT/'build.tcl').read_text()==(PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)),'build options changed')
 guard=before_build('neo',candidate=True)
 return dict(passed=True,netlist_sha256=NET_SHA,format_assembly_sha256=FORMAT_SHA,
  reports_assembly_sha256=sha(OUT/'reports_assembly.json'),validation=checked['validation'],
  local_regressions=guard['local_regressions'],timing_constraints_changed=False,hardware_access=False,Gowin_executed=False)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
 actions.add_argument('--prepare-only',action='store_true');actions.add_argument('--check-only',action='store_true');args=parser.parse_args()
 if args.prepare_only:prepare()
 else:print(json.dumps(check()))
