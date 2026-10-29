#!/usr/bin/env python3
"""Prepare isolated R19 observer ECO only. No route/program/hardware commands."""
import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
NET_SHA='dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'
BIT_SHA='1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
VO_SHA='c519aedf27fdd29151ee10a668dcc9577bee8546dac2bdd6d263a2040ec1b6a2'
HELPER=HERE/'neo_usb_reply_witness.v'
YOSYS=ROOT/'optimizer/.tools/oss-cad-suite/bin/yosys'
EXPECTED_FF=402

def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def manifest(path):return {str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
def block(text,name):
 matches=list(re.finditer(r'^module '+re.escape(name)+r'\b.*?^endmodule',text,re.M|re.S))
 require(len(matches)==1,'nonunique module '+name);return matches[0][0]
def once(text,old,new):
 require(text.count(old)==1,'nonunique replacement '+old[:100]);return text.replace(old,new,1)
def norm(value):return re.sub(r'\s+','',value).replace('\\','')
def cells(text):
 result={}
 for kind,name,ports in re.findall(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S):
  if kind=='module':continue
  name=norm(name);require(name not in result,'duplicate cell '+name)
  result[name]=(kind,{pin:norm(net) for pin,net in re.findall(r'\.(\w+)\(([^()]*)\)',ports)})
 return result
def params(text):return {norm(n):norm(v) for n,v in re.findall(r'^\s*defparam\s+(.+?)\s*=\s*([^;]+);',text,re.M)}
def parent_guard(parent=PARENT):
 for path,expected in [('console_neo.vg',NET_SHA),('impl/pnr/console_neo.fs',BIT_SHA),('impl/pnr/console_neo.vo',VO_SHA)]:
  require(sha(parent/path)==expected,'parent identity '+path)
 require(manifest(parent/'source')==json.loads((parent/'sources.json').read_text()),'parent source snapshot')
def new_output(path):
 path=path.resolve();require(path.parent==HERE,'output must be immediate child of this isolated folder')
 path.mkdir(exist_ok=False);return path

def map_helper(out):
 parent_guard();out=new_output(out)
 source=out/'neo_usb_reply_witness.v';shutil.copy2(HELPER,source)
 # Avoid synth_gowin -vout: it splits vector ports. Explicit write preserves
 # vector ports and emits primitive-only Verilog plus parameters.
 script=(f'read_verilog {source}; synth_gowin -family gw5a -strict-gw5a-dffs '
  '-top neo_usb_reply_witness -nobram -nolutram -noiopads; '
  f'write_verilog -simple-lhs -decimal -attr2comment -defparam -renameprefix utw {out}/helper_mapped.v; '
  f'write_json {out}/helper.json')
 (out/'map.ys').write_text(script+'\n')
 with (out/'yosys.log').open('x') as log:
  result=subprocess.run([str(YOSYS),'-Q','-T','-s',str(out/'map.ys')],stdout=log,stderr=subprocess.STDOUT,timeout=60,cwd=ROOT)
 require(result.returncode==0,'helper mapping failed; see log')
 data=json.loads((out/'helper.json').read_text())['modules']['neo_usb_reply_witness']
 types=Counter(c['type'] for c in data['cells'].values())
 allowed={'DFFRE','ALU','LUT1','LUT2','LUT3','LUT4','MUX2_LUT5','MUX2_LUT6','MUX2_LUT7','MUX2_LUT8','VCC','GND','$scopeinfo'}
 require(set(types)<=allowed,'unexpected primitive or inferred memory')
 require(types['DFFRE']==EXPECTED_FF,'wrong witness register count')
 require(set(data['ports'])=={'hclk','hreset','reply_valid','busy','receive_index','reply','completed_count','address','read_hit','read_data'},'unexpected ports')
 for name,cell in data['cells'].items():
  if cell['type']=='DFFRE':
   require(cell['connections']['CLK']==data['ports']['hclk']['bits'],'new clock '+name)
   require(cell['connections']['RESET']==data['ports']['hreset']['bits'],'new reset '+name)
 mapped=(out/'helper_mapped.v').read_text()
 require(not re.search(r'^\s*(?:GSR|[A-Z]*RAM\w*|[A-Z]*DP\w*|[IO]BUF|PLL\w*)\s',mapped,re.M),'forbidden primitive')
 save(out/'result.json',dict(passed=True,candidate=True,hardware_qualification='FAIL (not routed or tested)',
  hardware_access=False,routing_started=False,Gowin_executed=False,SDF=False,
  tool=str(YOSYS),tool_sha256=sha(YOSYS),builder_sha256=sha(Path(__file__)),helper_sha256=sha(HELPER),
  cell_counts=dict(sorted(types.items())),ff=EXPECTED_FF,clock='hclk',reset='hreset',memory_cells=0,
  inputs={str(p.relative_to(out)):sha(p) for p in [source,out/'map.ys',out/'helper_mapped.v',out/'helper.json',out/'yosys.log']}))
 print(json.dumps(dict(mapped=True,output=str(out),cell_counts=dict(types))))

def transform(original,helper):
 old=block(original,'usb_idle_trace');oc=cells(old);op=params(old)
 require('neo_usb_reply_witness' not in original,'witness already present')
 require('utw_' not in old,'reserved name collision')
 # Frozen original reads +C0..FF as zero; preserve all decoding and bank
 # controls, extending only the input of its existing registered read bus.
 require(sha(PARENT/'source/tang/rtl/usb/usb_idle_trace.v')=='97854f943d523304877e4fafc52c53e71ef03cb3e54940f13cd1a7a0bdbe8d9f','register contract source changed')
 new=old;changed={};addition=[]
 for i in range(32):
  name=f'hrdata_{i}_s0';kind,pins=oc[name]
  require(kind=='DFFRE' and pins['Q']==f'usb_trace_hrdata[{i}]' and pins['CLK']=='vid_hclk' and pins['CE']=='read_pending' and pins['RESET']=='hreset','read register mismatch '+name)
  pattern=r'  DFFRE '+re.escape(name)+r' \(.*?\);';matches=list(re.finditer(pattern,new,re.S));require(len(matches)==1,name)
  before=matches[0][0];after=once(before,'.D('+pins['D']+')',f'.D(utw_read_mux[{i}])')
  new=once(new,before,after);changed[name]=(before,after)
  addition.append(f"LUT3 utw_mux_{i}(.I0({pins['D']}),.I1(utw_read_data[{i}]),.I2(utw_read_hit),.F(utw_read_mux[{i}]));\ndefparam utw_mux_{i}.INIT=8'hca;")
 instance='''neo_usb_reply_witness utw_observer (
 .hclk(vid_hclk),.hreset(hreset),.reply_valid(reply_valid),.busy(busy),
 .receive_index(receive_index),.reply(reply),.completed_count(snapshot_count),
 .address(address),.read_hit(utw_read_hit),.read_data(utw_read_data));'''
 decl='wire utw_read_hit;\nwire [31:0] utw_read_data,utw_read_mux;\n'
 idx=re.search(r'^wire ',new,re.M).start();new=new[:idx]+decl+new[idx:]
 tail='\n'+instance+'\n'+'\n'.join(addition)+'\n'
 new=once(new,'endmodule',tail+'endmodule')
 nc=cells(new);np=params(new)
 expected_added={'utw_observer'}|{f'utw_mux_{i}' for i in range(32)}
 require(set(nc)-set(oc)==expected_added and not(set(oc)-set(nc)),'unexpected primitive additions/removals')
 actual_changed={n for n in oc if oc[n]!=nc[n]}
 require(actual_changed==set(changed),'unexpected existing primitive mutation')
 for name in actual_changed:
  i=int(name.split('_')[1]);require(nc[name]==(oc[name][0],{**oc[name][1],'D':f'utw_read_mux[{i}]'}),'non-D read pin changed')
 require(all(np[k]==v for k,v in op.items()),'original primitive parameter changed')
 require(set(np)-set(op)=={f'utw_mux_{i}.INIT' for i in range(32)},'unexpected parameters')
 for i in range(32):require(np[f'utw_mux_{i}.INIT']=="8'hca",'wrong read mux truth table')
 undo=once(new,tail,'');undo=once(undo,decl,'')
 for before,after in changed.values():undo=once(undo,after,before)
 require(undo==old,'observer reversal not byte-identical')
 merged=once(original,old,new)+'\n'+helper+'\n'
 require(once(merged,'\n'+helper+'\n','').replace(new,old,1)==original,'full reversal failed')
 names=set(re.findall(r'^module (\w+)',original,re.M))
 require(set(re.findall(r'^module (\w+)',merged,re.M))==names|{'neo_usb_reply_witness'},'module set changed')
 for name in names-{'usb_idle_trace'}:require(block(original,name)==block(merged,name),'unrelated module changed '+name)
 return merged,new,dict(old_cells=len(oc),old_parameters=len(op),changed_pins={n:['D'] for n in sorted(changed)},
  added_cells=sorted(expected_added),unchanged_modules=sorted(names-{'usb_idle_trace'}),
  original_recovered_byte_identical=True,new_CDC=False,new_clock=False,read_only_extension='0xe90020c0..0xe90020fc aligned')

def assemble(mapping,out):
 parent_guard();mapping=mapping.resolve()
 require(mapping.parent==HERE,'mapping outside isolated folder')
 record=json.loads((mapping/'result.json').read_text())
 require(record['passed'] and record['helper_sha256']==sha(HELPER) and record['builder_sha256']==sha(Path(__file__)),'stale mapping inputs')
 require(record['tool_sha256']==sha(YOSYS),'mapping tool changed')
 for name,digest in record['inputs'].items():require(sha(mapping/name)==digest,'mapping input hash '+name)
 original=(PARENT/'console_neo.vg').read_text();helper=block((mapping/'helper_mapped.v').read_text(),'neo_usb_reply_witness')
 merged,observer,audit=transform(original,helper)
 out=new_output(out);shutil.copytree(PARENT/'source',out/'source')
 helper_path=out/'source/tang/boards/neo/neo_usb_reply_witness.v';require(not helper_path.exists(),'source name collision');shutil.copy2(HELPER,helper_path)
 source_manifest=manifest(out/'source');old_manifest=json.loads((PARENT/'sources.json').read_text())
 require(set(source_manifest)-set(old_manifest)=={'tang/boards/neo/neo_usb_reply_witness.v'},'unexpected source extension')
 require(all(source_manifest[k]==v for k,v in old_manifest.items()),'parent source changed')
 (out/'console_neo.vg').write_text(merged);(out/'observer.v').write_text(observer+'\n')
 shutil.copy2(mapping/'helper_mapped.v',out/'helper_mapped.v')
 save(out/'sources.json',source_manifest)
 (out/'observation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),merged.splitlines(True),fromfile='exact_R19',tofile='witness_candidate')))
 save(out/'assembly.json',dict(passed=True,candidate=True,hardware_qualification='FAIL (not routed or tested)',hardware_access=False,routing_started=False,Gowin_executed=False,
  parent=str(PARENT),parent_bitstream_sha256=BIT_SHA,parent_netlist_sha256=NET_SHA,parent_routed_netlist_sha256=VO_SHA,
  builder_sha256=sha(Path(__file__)),helper_sha256=sha(HELPER),mapping=str(mapping),mapping_result_sha256=sha(mapping/'result.json'),
  application_sources_unchanged=True,application_netlist_unchanged_except_read_data_mux=True,audit=audit,
  inputs={str(p.relative_to(out)):sha(p) for p in [out/'console_neo.vg',out/'observer.v',out/'helper_mapped.v',out/'sources.json',out/'observation.diff']},
  pending=['Independent review and primitive simulation.','No Gowin reader/P&R/STA/board proof; helper mapped by Yosys only.','New tap fanout and read mux change physical loading; original anomaly must persist for boundary interpretation.']))
 print(json.dumps(dict(assembled=True,output=str(out),sha256=sha(out/'console_neo.vg'))))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
 p=sub.add_parser('map');p.add_argument('--out',type=Path,required=True)
 p=sub.add_parser('assemble');p.add_argument('--mapping',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=parser.parse_args()
 if a.action=='map':map_helper(a.out)
 else:assemble(a.mapping,a.out)
