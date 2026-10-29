#!/usr/bin/env python3
"""Read-only bounded legacy-bank cone / SDF comparison, not full design equivalence."""
from pathlib import Path
import sys,re,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'reply_witness_reports_01'));import audit_reports as audit
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cone(cells,params,net):
 drivers=audit.original.drivers(cells);todo=[name for name,pin in drivers.get(net,set()) if name!='CONST'];seen={}
 while todo:
  name=todo.pop()
  if name in seen:continue
  kind,pins=cells[name];seen[name]=dict(type=kind,pins=pins,parameters={k[len(name)+1:]:v for k,v in params.items() if k.startswith(name+'.')})
  if kind.startswith('DFF') or kind in ('SDPB','DPB','SDP','DP','ROM16','RAM16SDP4'):continue
  for pin,value in pins.items():
   if pin in audit.original.OUTPUTS:continue
   for bit in audit.original.net_bits(value):todo.extend(n for n,p in drivers.get(bit,set()) if n!='CONST' and n in cells)
 return seen

def sdf_data(path,names):
 text=path.read_text();starts=list(re.finditer(r'^  \(CELL\s*$',text,re.M));cells={};nets=[]
 for i,m in enumerate(starts):
  body=text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)]
  instance=re.search(r'\(INSTANCE\s+([^\s)]+)\)',body)
  if instance:
   name=instance[1].replace('\\','')
   if name in names:cells[name]=[line.strip() for line in body.splitlines() if any(k in line for k in ['(IOPATH','(SETUP','(HOLD','(WIDTH'])]
  if '(INTERCONNECT' in body:
   for source,dest,val in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([^()]*)\)',body):
    source,dest=source.replace('\\',''),dest.replace('\\','')
    if source.rsplit('/',1)[0] in names or dest.rsplit('/',1)[0] in names:nets.append(dict(source=source,destination=dest,min_typ_max=val))
 return dict(cells=cells,interconnect=nets)

def main():
 builds=['console_neo_n56r19_capture_ce_local','console_neo_n56r22r1_utw1_reports'];data={};inputs={}
 for build in builds:
  base=ROOT/'tang/impl'/build/'impl/pnr';vo=base/'console_neo.vo';sdf=base/'console_neo.sdf';inputs[str(vo)]=sha(vo);inputs[str(sdf)]=sha(sdf)
  cells,params=audit.original.cells(vo.read_text());legacy=cone(cells,params,'u_usb_idle_trace/n558_9')
  selected=set(legacy)|{'u_usb_idle_trace/hrdata_0_s0','u_usb_idle_trace/utw_mux_0'}
  data[build]=dict(legacy_cone=legacy,hrdata0=cells['u_usb_idle_trace/hrdata_0_s0'],sdf=sdf_data(sdf,selected))
 a,b=[data[k]['legacy_cone'] for k in builds]
 diff=dict(old_only=sorted(set(a)-set(b)),new_only=sorted(set(b)-set(a)),changed=[n for n in sorted(set(a)&set(b)) if a[n]!=b[n]])
 result=dict(scope='Legacy combinational fanin of n558_9, stopping at sequential/memory cells; their immediate pins/parameters compared.',
  hardware_access=False,global_equivalence_proven=False,legacy_cone_cell_count=[len(a),len(b)],legacy_cone_identical=not any(diff.values()),diff=diff,
  builds=data,inputs=inputs,limits=['Not whole-UTNA or whole-design equivalence.','Same primitive netlist cone does not mean same routing, loading, RAM physical placement or dynamic behavior.',
   'Raw SDF arcs do not form a timing-path proof without clock relationships, transitions, conditions and constraints.','Witness taps and read mux are actual additions, not routing-only change.'])
 for name,digest in inputs.items():assert sha(Path(name))==digest
 (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(legacy_cells=result['legacy_cone_cell_count'],identical=result['legacy_cone_identical'],diff=diff,sha256=sha(HERE/'result.json'))))
if __name__=='__main__':main()
