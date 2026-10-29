#!/usr/bin/env python3
"""Read-only targeted routed-netlist audit. Never authorizes a board load."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import prepare_route as p

PREFIX='u_usb_idle_trace/utw_observer/'
OBS='u_usb_idle_trace/'
OUTPUTS={'Q','F','O','V','G','SUM','COUT','DO','DOA','DOB','CLKOUT',*[f'CLKOUT{i}' for i in range(7)]}

def norm(text):return re.sub(r'\s+','',text).replace('\\','')
def cells(text):
 result={}
 for kind,name,ports in re.findall(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S):
  if kind=='module':continue
  name=norm(name);p.require(name not in result,'duplicate routed cell '+name)
  result[name]=(kind,{pin:norm(net) for pin,net in re.findall(r'\.(\w+)\(([^()]*)\)',ports)})
 parameters={norm(n):norm(v) for n,v in re.findall(r'^\s*defparam\s+(.+?)\s*=\s*([^;]+);',text,re.M)}
 return result,parameters
def literal(value):
 match=re.fullmatch(r"(?:\d+)?'([bdh])([0-9a-fA-F]+)",value)
 return int(match[2],{'b':2,'d':10,'h':16}[match[1]]) if match else int(value)
def net_bits(value):
 """LSB-first expansion, including routed SDPB.DO concatenation/ranges."""
 if not value:return []
 if value.startswith('{'):
  p.require(value.endswith('}'),'bad concatenation '+value)
  body=value[1:-1];depth=0;start=0;pieces=[]
  for i,char in enumerate(body):
   if char=='{':depth+=1
   elif char=='}':depth-=1
   elif char==',' and depth==0:pieces.append(body[start:i]);start=i+1
  pieces.append(body[start:])
  return [bit for piece in reversed(pieces) for bit in net_bits(piece)]
 match=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',value)
 if match:
  left,right=int(match[2]),int(match[3]);step=1 if left>=right else -1
  return [match[1]+f'[{i}]' for i in range(right,left+step,step)]
 p.require('{' not in value and '}' not in value and ',' not in value and ':' not in value,'unsupported output expression '+value)
 return [value]
def drivers(data):
 result=defaultdict(set)
 for name,(kind,pins) in data.items():
  for pin,net in pins.items():
   if pin in OUTPUTS:
    bits=net_bits(net)
    for i,bit in enumerate(bits):
     result[bit].add(('CONST',1 if kind=='VCC' else 0) if kind in ('VCC','GND') else (name,pin if len(bits)==1 else f'{pin}[{i}]'))
 return result

def check_structure(old,new,new_params,expected):
 od,nd=drivers(old),drivers(new);errors=[];checks=[]
 hc=expected['helper_cells'];ports=expected['helper_ports'];bitdrivers=defaultdict(set)
 for port,info in ports.items():
  if info['direction']!='input':continue
  base=expected['input_connections'][port]
  for index,bit in enumerate(info['bits']):
   net=base+(f'[{index}]' if len(info['bits'])>1 else '')
   if not od.get(net):errors.append(dict(reason='unresolved original tap',port=port,index=index,net=net))
   bitdrivers[bit].update(od.get(net,set()))
 for name,cell in hc.items():
  for pin,direction in cell['port_directions'].items():
   if direction!='output':continue
   bits=cell['connections'][pin];p.require(len(bits)==1,'vector primitive output')
   bitdrivers[bits[0]].add(('CONST',int(cell['type']=='VCC')) if cell['type'] in ('VCC','GND') else (PREFIX+name,pin))
 bitdrivers['0']={('CONST',0)};bitdrivers['1']={('CONST',1)}
 required={PREFIX+n for n,c in hc.items() if c['type'] not in ('VCC','GND')}
 actual={n for n,(kind,pins) in new.items() if n.startswith(PREFIX) and kind not in ('VCC','GND')}
 for name in sorted(required-actual):errors.append(dict(cell=name,reason='missing helper cell'))
 for name in sorted(actual-required):errors.append(dict(cell=name,reason='unexpected helper cell'))
 ff=[n for n,(kind,pins) in new.items() if n.startswith(PREFIX) and kind.startswith('DFF')]
 if len(ff)!=402:errors.append(dict(reason='wrong FF count',expected=402,actual=len(ff)))
 for name,cell in hc.items():
  if cell['type'] in ('VCC','GND'):continue
  physical=PREFIX+name;found=new.get(physical)
  if found is None:continue
  kind,pins=found
  if kind!=cell['type']:errors.append(dict(cell=physical,reason='primitive type changed',expected=cell['type'],actual=kind));continue
  if set(pins)!=set(cell['connections']):errors.append(dict(cell=physical,reason='primitive port set changed'));continue
  for pin,direction in cell['port_directions'].items():
   if direction!='input':continue
   bit=cell['connections'][pin][0];want=bitdrivers.get(bit,set());got=nd.get(pins[pin],set())
   ok=bool(want) and got==want
   if not ok:errors.append(dict(cell=physical,pin=pin,reason='driver identity',expected=sorted(want),actual=sorted(got),net=pins[pin]))
   if kind=='DFFRE' and pin in ('CLK','RESET'):checks.append(dict(cell=physical,pin=pin,passed=ok,drivers=sorted(got)))
  for param,binary in cell['parameters'].items():
   key=physical+'.'+param;actual_value=new_params.get(key)
   if actual_value is None or literal(actual_value)!=int(binary,2):errors.append(dict(parameter=key,reason='parameter changed',expected_binary=binary,actual=actual_value))
  if kind=='DFFRE' and physical+'.INIT' in new_params and literal(new_params[physical+'.INIT'])!=0:
   errors.append(dict(cell=physical,reason='FF INIT changed'))
 for index in range(32):
  name=OBS+f'hrdata_{index}_s0';mux=OBS+f'utw_mux_{index}'
  before=old.get(name);after=new.get(name);added=new.get(mux)
  if not before or not after or not added:errors.append(dict(cell=name,reason='missing old read register or mux'));continue
  if before[0]!=after[0] or before[0]!='DFFRE' or added[0]!='LUT3':errors.append(dict(cell=name,reason='read primitive types'));continue
  for pin in ('CLK','RESET','CE'):
   want=od.get(before[1][pin],set());got=nd.get(after[1][pin],set())
   if not want or want!=got:errors.append(dict(cell=name,pin=pin,reason='read control changed',expected=sorted(want),actual=sorted(got)))
  if before[1]['Q']!=after[1]['Q']:errors.append(dict(cell=name,pin='Q',reason='bus output changed'))
  desired={'I0':od.get(before[1]['D'],set()),'I1':bitdrivers[ports['read_data']['bits'][index]],'I2':bitdrivers[ports['read_hit']['bits'][0]]}
  for pin,want in desired.items():
   got=nd.get(added[1].get(pin),set())
   if not want or got!=want:errors.append(dict(cell=mux,pin=pin,reason='read mux input',expected=sorted(want),actual=sorted(got)))
  if nd.get(after[1]['D'],set())!={(mux,'F')}:errors.append(dict(cell=name,pin='D',reason='read mux output not connected'))
  if literal(new_params.get(mux+'.INIT','0'))!=0xca:errors.append(dict(cell=mux,reason='wrong mux INIT'))
 # Every new-helper output may feed only the helper itself and 32 read muxes.
 # This rejects a silent observation feedback into the old control/data path.
 forbidden=[];muxnames={OBS+f'utw_mux_{i}' for i in range(32)}
 for name,(kind,pins) in new.items():
  if name.startswith(PREFIX) or name in muxnames:continue
  for pin,net in pins.items():
   if pin in OUTPUTS:continue
   sources=set().union(*(nd.get(bit,set()) for bit in net_bits(net)))
   if any(source.startswith(PREFIX) for source,port in sources if source!='CONST'):
    forbidden.append(dict(cell=name,pin=pin,sources=sorted(sources)))
 errors.extend(dict(reason='witness feedback outside read mux',**item) for item in forbidden)
 return dict(passed=not errors,helper_ff=len(ff),helper_cells=len(actual),expected_helper_cells=len(required),
  expected_memory_cells=0,clock_reset_checks=checks,errors=errors,
  scope='Primitive/parameter/driver-graph checks only; timing and hardware are separate.')

def timing_inventory(vo_text,tr_text,sdf_text,expected):
 names=[PREFIX+n for n,c in expected['helper_cells'].items() if c['type']=='DFFRE']+expected['read_registers']
 paths=[]
 for match in re.finditer(r'Path Summary:\n(.*?)(?=Path Summary:|\Z)',tr_text,re.S):
  body=match[1]
  def field(label):
   found=re.search(r'^'+re.escape(label)+r'\s*:\s*(.*?)\s*$',body,re.M);return found[1] if found else None
  source,dest=field('From'),field('To')
  if source in names or dest in names or (source and 'utw_' in source) or (dest and 'utw_' in dest):
   paths.append(dict(source=source,destination=dest,slack_ns=field('Slack'),launch=field('Launch Clk'),latch=field('Latch Clk')))
 represented={row['destination'] for row in paths}
 sdf_cells=set(norm(x) for x in re.findall(r'\(INSTANCE\s+([^\s)]+)\)',sdf_text))
 # Presence of SDF/STA entries is an inventory, not an all-path timing proof.
 return dict(target_registers=len(names),reported_paths=paths,unreported_registers=sorted(set(names)-represented),
  missing_sdf_registers=sorted(set(names)-sdf_cells),full_setup_hold_coverage_proven=False,
  required_next='Review global STA plus setup/hold paths to every witness/read D, CE, synchronous RESET and their source cones. Missing coverage remains pending/FAIL; never infer a pass from a positive subset.')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 p.check();route=json.loads((p.OUT/'route_result.json').read_text())
 p.require(route['status']=='ROUTED_NOT_QUALIFIED','route incomplete/failed')
 pnr=p.OUT/'impl/pnr';stable=[p.OUT/'console_neo.vg',p.OUT/'preparation.json',p.OUT/'postroute_expected.json',p.OUT/'route_result.json',p.PARENT/'impl/pnr/console_neo.vo']+[pnr/('console_neo'+suffix) for suffix in ['.vo','.tr','.sdf','.fs','.rpt.txt']]
 hashes={str(path):p.sha(path) for path in stable}
 old,_=cells((p.PARENT/'impl/pnr/console_neo.vo').read_text());new,params=cells((pnr/'console_neo.vo').read_text())
 expected=json.loads((p.OUT/'postroute_expected.json').read_text());structure=check_structure(old,new,params,expected)
 timing=timing_inventory((pnr/'console_neo.vo').read_text(),(pnr/'console_neo.tr').read_text(),(pnr/'console_neo.sdf').read_text(),expected)
 p.require(all(p.sha(Path(path))==digest for path,digest in hashes.items()),'route outputs changed during audit')
 args.out.mkdir(exist_ok=False)
 p.save(args.out/'result.json',dict(structure=structure,timing_inventory=timing,hardware_access=False,hardware_qualified=False,
  qualification='NOT_QUALIFIED',no_board_load_authorized=True,inputs=hashes,script_sha256=p.sha(Path(__file__))))
 print(json.dumps(dict(structure_passed=structure['passed'],helper_ff=structure['helper_ff'],timing_complete=False,hardware_qualified=False)))
 if not structure['passed']:raise SystemExit(1)

if __name__=='__main__':main()
