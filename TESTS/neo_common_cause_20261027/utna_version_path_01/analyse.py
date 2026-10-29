"""Offline exact R19 routed cone/constant evaluation; never invokes Gowin or IO."""
import bisect,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUILD=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
PNR=BUILD/'impl/pnr'
CAPTURE=HERE.parent/'utna_snapshot_prepared_01/snapshot_20261027_232521'
PREFIX='u_usb_idle_trace/'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
vo=(PNR/'console_neo.vo').read_text();newlines=[m.start() for m in re.finditer('\n',vo)]
cells={}
for m in re.finditer(r'^([A-Z][A-Z0-9_]*)\s+(\\\S+|\w+)\s+\((.*?)\);',vo,re.M|re.S):
 name=m[2].lstrip('\\')
 if not name.startswith(PREFIX):continue
 ports={k:re.sub(r'\s+','',v).replace('\\','') for k,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',m[3],re.M)}
 cells[name]=dict(kind=m[1],name=name,ports=ports,line=bisect.bisect_left(newlines,m.start())+1,text=m[0],parameters={})
for name,param,value in re.findall(r'^defparam \\(\S+)\s*\.(\w+)\s*=([^;]+);',vo,re.M):
 if name in cells:cells[name]['parameters'][param]=value
assert cells[PREFIX+'bank_bank_0_0_s']['ports']['DI']=='{u_usb_idle_trace/reply[3:0]}'
(HERE/'routed_cells.json').write_text(json.dumps(cells,indent=2)+'\n')
drivers={c['ports']['F']:c for c in cells.values() if 'F' in c['ports']}
used=set();truth=[]
for const in (0,1):
 for index in (0,1,2):
  cache={'GND':0,'VCC':1}
  def ev(net):
   if net in cache:return cache[net]
   match=re.fullmatch(PREFIX+r'send_index\[(\d+)\]',net)
   if match:return (index>>int(match[1]))&1
   match=re.fullmatch(PREFIX+r'snapshot\[(\d+)\]',net)
   if match:return const if int(match[1])==32 else int(int(match[1])==65)
   c=drivers[net];assert c['kind'].startswith('LUT'),c
   used.add(c['name']);count=int(c['kind'][3:])
   address=sum(ev(c['ports']['I'+str(i)])<<i for i in range(count))
   value=(int(c['parameters']['INIT'].split("'h")[1],16)>>address)&1;cache[net]=value;return value
  value=sum(ev(PREFIX+'n'+str(181-bit)+'_37')<<bit for bit in range(32))
  expected=([0,0,2] if not const else [0x55544e41,1,2])[index]
  assert value==expected,(const,index,value,expected)
  truth.append(dict(snapshot32=const,send_index=index,fifo_input_hex=f'{value:08x}'))
(HERE/'constant_mux_truth.json').write_text(json.dumps(dict(passed=True,hardware_access=False,method='Evaluate LUT INIT from routed .vo; stable Boolean inputs, no delay simulation',rows=truth),indent=2)+'\n')
# Curated bit0/bit1 output cones, plus bank data/reset-validity controls.
selected=set()
def backward(net):
 c=drivers.get(net)
 if not c or c['name'] in selected:return
 selected.add(c['name'])
 for pin,value in c['ports'].items():
  if pin.startswith('I'):backward(value)
for net in (PREFIX+'n181_37',PREFIX+'n180_37',PREFIX+'bank_245',PREFIX+'bank_ER_RS_mem',PREFIX+'bank_ER_RS_151',PREFIX+'n1170_3',PREFIX+'n5312_3'):
 backward(net)
for name,c in cells.items():
 if (name.endswith(('/snapshot_32_s0','/snapshot_65_s0','/bank_bank_0_0_s','/bank_ER_RS_bank_ER_RS_0_0_s','/bank_ER_init_s','/bank_ER_init_s1','/receive_index_0_s0','/receive_index_1_s0'))
     or '/u_replies/' in name and c['kind']=='SDPB'):
  selected.add(name)
  for pin in ('WRE','CE','RESET','CLEAR'):
   if pin in c['ports']:backward(c['ports'][pin])
# Data bit0 read mux and its validity mask, stopping at physical sequential cells.
for name,c in cells.items():
 if c['kind'].startswith('DFF') and c['ports'].get('Q')=='usb_trace_hrdata[0]':
  selected.add(name);backward(c['ports']['D'])
selected_text=[]
for name in sorted(selected,key=lambda n:cells[n]['line']):
 c=cells[name];selected_text.append(f"// .vo line {c['line']}\n"+c['text']+'\n'+'\n'.join(f'defparam \\{name} .{k}={v};' for k,v in c['parameters'].items()))
(HERE/'selected_routed_cells.txt').write_text('\n\n'.join(selected_text)+'\n')
# Preserve exact SDF cell and interconnect lines. No inferred zero for missing arcs.
sdf=(PNR/'console_neo.sdf').read_text();sdf_parts=[];arcs=[]
for part in sdf.split('\n  (CELL\n')[1:]:
 match=re.search(r'\(INSTANCE ([^\s)]+)\)',part)
 if match and match[1].replace('\\','') in selected:
  sdf_parts.append('  (CELL\n'+part.split('\n  (CELL\n',1)[0])
for lineno,line in enumerate(sdf.splitlines(),1):
 if '(INTERCONNECT ' not in line:continue
 match=re.fullmatch(r'\s*\(INTERCONNECT (\S+) (\S+) (.+)\)\s*',line)
 assert match,line
 source,dest=match[1].replace('\\',''),match[2].replace('\\','')
 sn,sp=source.rsplit('/',1);dn,dp=dest.rsplit('/',1)
 if dn in selected and (sn in selected or dp in ('CLK','CLKA','CLKB','CE','CEA','CEB','RESET','WRE','CLEAR','D')):
  arcs.append(dict(line=lineno,source=source,destination=dest,delay=match[3],raw=line.strip()))
(HERE/'selected_sdf_arcs.json').write_text(json.dumps(arcs,indent=2)+'\n')
# Limit review packet: full raw SDF cells can be bulky, retain selected cones separately.
(HERE/'selected_sdf_cells.txt').write_text('\n'.join(sdf_parts)+'\n')
tr=(PNR/'console_neo.timing_paths').read_text();timing=[p for p in tr.split('=====') if PREFIX in p]
(HERE/'reported_sta_paths.txt').write_text('\n=====\n'.join(timing)+'\n')
capture=json.loads((CAPTURE/'result.json').read_text())
assert capture['observation']['capture_complete'] and not capture['observation']['protocol_passed']
assert capture['left_startup_verified'] and capture['last_programmed_sha256']=='1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
for name,digest in capture['files'].items():assert sha(CAPTURE/name)==digest,name
proofs=[PNR/('console_neo'+x) for x in ('.vo','.sdf','.tr','.timing_paths','.fs')]+[CAPTURE/'result.json',CAPTURE/'r19_snapshot.log',Path(__file__)]
result=dict(hardware_access=False,Gowin_executed=False,input_sha256={str(p):sha(p) for p in proofs},routed_cells=len(cells),selected_cells=len(selected),selected_sdf_arcs=len(arcs),reported_usb_sta_paths=len(timing),truth=truth,
            limits=['Boolean evaluation, not SDF simulation.','SDF interconnect delays alone are not setup/hold slack.','Existing timing report covers only selected reported paths, not every observer path.','Captured ID excludes a permanently low shared constant FF in the Boolean design; it does not exclude a transient or word-dependent fault.'])
(HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(cells=len(cells),selected=len(selected),arcs=len(arcs),sta_paths=len(timing),hardware_access=False)))
