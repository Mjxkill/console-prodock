#!/usr/bin/env python3
"""Serialize the frozen mapped graph in Gowin's restricted .vg syntax."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OLD_TOOLS=ROOT/'TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01'
sys.path.insert(0,str(OLD_TOOLS));import prepare_route as previous
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
PARENT=previous.OUT
OUT=ROOT/'tang/impl/console_neo_n56r22r1_utw1_format'
FROZEN=previous.FROZEN
PARENT_SHA=previous.NET_SHA
LOG_SHA='91e5719883d65fe831c763fdc654bf798434211f45340b0b1daa2ce41555a07c'
IDENT=re.compile(r'[a-zA-Z_][a-zA-Z0-9_$]*\Z')
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def block(text,name):return previous.block(text,name)
def clean(text):return re.sub(r'//[^\n]*','',re.sub(r'/\*.*?\*/','',text,flags=re.S))
def vname(text):return text[1:] if text.startswith('\\') else text
def number(value):
 if re.fullmatch(r'\d+',value.strip()):return int(value.strip(),10)
 m=re.fullmatch(r"(\d+)'([bhd])([0-9a-fA-F]+)",value.strip())
 require(m is not None,'bad literal '+value);return int(m[3],{'b':2,'h':16,'d':10}[m[2]])

class Expr:
 def __init__(self,text,symbols):self.text=text;self.i=0;self.symbols=symbols
 def ws(self):
  while self.i<len(self.text) and self.text[self.i].isspace():self.i+=1
 def parse(self):
  self.ws();require(self.i<len(self.text),'empty expression')
  if self.text[self.i]=='{':
   self.i+=1;parts=[]
   while True:
    parts.append(self.parse());self.ws();require(self.i<len(self.text),'unclosed concat')
    c=self.text[self.i];self.i+=1
    if c=='}':break
    require(c==',','bad concat separator')
   return [b for part in reversed(parts) for b in part]
  if self.text[self.i]=='\\':
   m=re.match(r'\\\S+',self.text[self.i:]);name=m[0][1:];self.i+=len(m[0])
  else:
   m=re.match(r'[a-zA-Z_][a-zA-Z0-9_$]*',self.text[self.i:]);require(m is not None,'unsupported expression '+self.text)
   name=m[0];self.i+=len(name)
  require(name in self.symbols,'unknown signal '+name)
  bits=self.symbols[name];self.ws()
  if self.i<len(self.text) and self.text[self.i]=='[':
   m=re.match(r'\[(\d+)(?::(\d+))?\]',self.text[self.i:]);require(m is not None,'bad slice')
   self.i+=len(m[0]);left=int(m[1]);right=int(m[2]) if m[2] is not None else left
   step=1 if left>=right else -1
   require(max(left,right)<len(bits),'out of range '+name)
   return [bits[i] for i in range(right,left+step,step)]
  return list(bits)
def expr(text,symbols):
 parser=Expr(text,symbols);bits=parser.parse();parser.ws();require(parser.i==len(text),'expression trailing tokens '+text);return bits

def parsed(text,symbols):
 text=clean(text);cells={};parameters={};aliases=[]
 for kind,name,ports in re.findall(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S):
  if kind=='module':continue
  name=vname(name);require(name not in cells,'duplicate cell '+name)
  pins={pin:expr(value,symbols) for pin,value in re.findall(r'\.(\w+)\(([^()]*)\)',ports)}
  cells[name]=dict(type=kind,connections=pins)
 for name,param,value in re.findall(r'\bdefparam\s+(\\[^\s]+|\w+)\s*\.\s*(\w+)\s*=\s*([^;]+);',text):
  key=(vname(name),param);require(key not in parameters,'duplicate parameter')
  parameters[key]=value.strip()
 for lhs,rhs in re.findall(r'\bassign\s+([^;=]+)=([^;]+);',text):
  a,b=expr(lhs,symbols),expr(rhs,symbols);require(a==b,'alias differs from mapped JSON '+lhs)
  aliases.append(dict(lhs=lhs.strip(),rhs=rhs.strip(),bits=a))
 return cells,parameters,aliases

def serialize(helper,json_module):
 symbols={name:data['bits'] for name,data in json_module['netnames'].items()}
 require(all(data.get('offset',0)==0 and data.get('upto',0)==0 for data in json_module['netnames'].values()),'unexpected vector direction/offset')
 old_cells,old_params,aliases=parsed(helper,symbols)
 expected={name:cell for name,cell in json_module['cells'].items() if cell['type']!='$scopeinfo'}
 require(set(old_cells)==set(expected),'Verilog/JSON cell set mismatch')
 for name,cell in expected.items():
  require(old_cells[name]==dict(type=cell['type'],connections=cell['connections']),'Verilog/JSON pins '+name)
  for param,value in cell['parameters'].items():require(number(old_params[(name,param)])==int(value,2),'Verilog/JSON parameter '+name)
 require(set(old_params)=={(name,param) for name,c in expected.items() for param in c['parameters']},'unexpected Verilog parameter')
 names={};used=set(expected)
 for i,name in enumerate(sorted(expected)):
  safe=name if IDENT.fullmatch(name) else 'utw_cell_'+str(i)
  require(safe==name or safe not in used,'safe cell-name collision');names[name]=safe
 require(len(set(names.values()))==len(names),'cell mapping not bijective')
 references={};output_aliases=[];normalized_symbols={};lines=['module neo_usb_reply_witness (',',\n'.join('  '+name for name in json_module['ports']),');']
 for name,port in json_module['ports'].items():
  width=len(port['bits']);lines.append(port['direction']+' '+(f'[{width-1}:0] ' if width>1 else '')+name+';')
  normalized_symbols[name]=port['bits']
  for i,bit in enumerate(port['bits']):
   reference=name+(f'[{i}]' if width>1 else '')
   if bit in references:output_aliases.append((reference,references[bit]))
   else:references[bit]=reference
 bits={b for cell in expected.values() for values in cell['connections'].values() for b in values}
 require(all(type(bit) is int for bit in bits),'literal bit without existing VCC/GND driver')
 for bit in sorted(bits-set(references)):
  name='utw_net_'+str(bit);references[bit]=name;normalized_symbols[name]=[bit];lines.append('wire '+name+';')
 for name,cell in sorted(expected.items()):
  require(all(len(values)==1 for values in cell['connections'].values()),'vector primitive pin')
  lines.append(cell['type']+' '+names[name]+' (')
  lines.append(',\n'.join('  .'+pin+'('+references[bits[0]]+')' for pin,bits in cell['connections'].items()));lines.append(');')
  for param in cell['parameters']:lines.append('defparam '+names[name]+'.'+param+' = '+old_params[(name,param)]+';')
 for dest,source in output_aliases:lines.append('assign '+dest+' = '+source+';')
 lines.append('endmodule');normalized='\n'.join(lines)
 new_cells,new_params,new_aliases=parsed(normalized,normalized_symbols)
 require(len(new_cells)==len(old_cells),'serialization changed cell count')
 for old,new in names.items():
  require(new_cells[new]==old_cells[old],'serialized primitive pins changed '+old)
  for (cell,param),value in old_params.items():
   if cell==old:require(new_params[(new,param)]==value,'serialized parameter changed '+old)
 require(len(new_params)==len(old_params),'parameter set changed')
 require(not re.search(r'\\|\bassign\s+[^;]*[:,{}]',normalized),'escaped identifier/vector assign remains')
 proof=dict(passed=True,cells=len(old_cells),parameters=len(old_params),original_alias_statements=len(aliases),
  normalized_alias_statements=len(new_aliases),cell_name_mapping=names,bit_references={str(k):v for k,v in references.items()},
  primitive_pins_and_parameters_equivalent=True,alias_bit_graph_equivalent=True,algorithm_changed=False,
  synthesis_executed=False,normalized_symbols=normalized_symbols)
 return normalized,proof

def parent_guard():
 previous.check()
 require(sha(PARENT/'console_neo.vg')==PARENT_SHA,'R22 netlist changed')
 require(sha(PARENT/'build.log')==LOG_SHA,'R22 error log changed')
 record=json.loads((PARENT/'route_result.json').read_text())
 require(record['returncode']==1 and record['bitstream_sha256'] is None,'not the expected parse failure')
 log=(PARENT/'build.log').read_text()
 require('PA2060' in log and 'PA2000' in log and not re.search(r'Placement|Routing progress|Bitstream generation',log),'failure not limited to parsing')

def transformed():
 parent_guard();original=(PARENT/'console_neo.vg').read_text();old_helper=block(original,'neo_usb_reply_witness')
 data=json.loads((FROZEN/'mapping_02/helper.json').read_text())['modules']['neo_usb_reply_witness']
 helper,proof=serialize(old_helper,data)
 old=block(original,'usb_idle_trace');new=old
 matches=list(re.finditer(r'neo_usb_reply_witness utw_observer \(.*?\);',old,re.S))
 require(len(matches)==1,'observer instance not unique');old_instance=matches[0][0];new_instance=old_instance
 replacements={
  '.receive_index(receive_index)':'.receive_index(receive_index[4:0])',
  '.reply(reply)':'.reply(reply[31:0])',
  '.completed_count(snapshot_count)':'.completed_count(snapshot_count[31:0])',
  '.address(address)':'.address(address[7:0])',
  '.read_data(utw_read_data)':'.read_data(utw_read_data[31:0])'}
 for before,after in replacements.items():require(new_instance.count(before)==1,'binding not unique '+before);new_instance=new_instance.replace(before,after,1)
 new=old.replace(old_instance,new_instance,1)
 # Five range selections denote the exact same complete vectors.
 undone=new.replace(new_instance,old_instance,1)
 require(undone==old,'observer changed beyond explicit vector selections')
 result=original.replace(old,new,1).replace(old_helper,helper,1)
 require(result.replace(new,old,1).replace(helper,old_helper,1)==original,'full reversal failed')
 modules=set(re.findall(r'^module (\w+)',original,re.M))
 require(all(block(original,n)==block(result,n) for n in modules-{'usb_idle_trace','neo_usb_reply_witness'}),'unrelated module changed')
 proof.update(observer_replacements=replacements,unchanged_modules=len(modules)-2,parent_recovered_byte_identical=True)
 return result,helper,new,proof

def prepare():
 net,helper,observer,proof=transformed();contract=before_build('neo',candidate=True)
 OUT.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',OUT/'source')
 for name in ['sources.json','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
  dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,dest)
 (OUT/'console_neo.vg').write_text(net);(OUT/'helper_normalized.v').write_text(helper+'\n');(OUT/'observer_normalized.v').write_text(observer+'\n')
 (OUT/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)))
 save(OUT/'serialization_proof.json',proof)
 expected=json.loads((PARENT/'postroute_expected.json').read_text())
 expected['helper_cells']={proof['cell_name_mapping'][name]:cell for name,cell in expected['helper_cells'].items()}
 save(OUT/'postroute_expected.json',expected)
 require(previous.manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text()),'source copy changed')
 record_build(OUT,contract)
 inputs=['console_neo.vg','helper_normalized.v','observer_normalized.v','serialization_proof.json','postroute_expected.json','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc']
 save(OUT/'format_assembly.json',dict(passed=True,candidate=True,hardware_access=False,Gowin_executed=False,global_synthesis=False,
  parent=str(PARENT),parent_sha256=PARENT_SHA,parent_error_log_sha256=LOG_SHA,netlist_sha256=sha(OUT/'console_neo.vg'),
  builder_sha256=sha(Path(__file__)),algorithm_changed=False,source_RTL_changed=False,full_pnr_required=True,
  identical_CST_SDC_options=True,inputs={name:sha(OUT/name) for name in inputs},local_regressions=contract['local_regressions'],
  pending=['Helper/integration simulation and root review before launch.','Actual Gowin reader acceptance, P&R, timing and hardware unqualified.']))
 print(json.dumps(dict(prepared=True,path=str(OUT),netlist_sha256=sha(OUT/'console_neo.vg'),format_assembly_sha256=sha(OUT/'format_assembly.json'),cells=proof['cells'])))

def check(require_tests=True):
 parent_guard();record=json.loads((OUT/'format_assembly.json').read_text());require(record['builder_sha256']==sha(Path(__file__)),'formatter changed')
 for name,digest in record['inputs'].items():require(sha(OUT/name)==digest,'formatted input changed '+name)
 require(previous.manifest(OUT/'source')==json.loads((OUT/'sources.json').read_text()),'formatted sources changed')
 validation=None
 if require_tests:
  validation=json.loads((HERE/'validation.json').read_text());proof=Path(validation['proof'])
  require(sha(proof)==validation['sha256'],'test proof changed');result=json.loads(proof.read_text());require(result['passed'],'format tests failed')
  require(result['netlist_sha256']==record['netlist_sha256'],'tests target wrong netlist')
  for name,digest in result['inputs'].items():require(sha(Path(name))==digest,'test input changed '+name)
 guard=before_build('neo',candidate=True)
 return dict(passed=True,netlist_sha256=record['netlist_sha256'],format_assembly_sha256=sha(OUT/'format_assembly.json'),validation=validation,local_regressions=guard['local_regressions'],hardware_access=False,Gowin_executed=False)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);g=parser.add_mutually_exclusive_group(required=True)
 g.add_argument('--prepare-only',action='store_true');g.add_argument('--check-only',action='store_true');args=parser.parse_args()
 if args.prepare_only:prepare()
 else:print(json.dumps(check()))
