"""Read-only bank validity cone and SDF path sums, no hardware or Gowin."""
import json,re,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PNR=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local/impl/pnr'
cells=json.loads((HERE/'routed_cells.json').read_text());p='u_usb_idle_trace/'
drivers={}
for c in cells.values():
 for op in ('F','O','Q'):
  if op in c['ports']:drivers[c['ports'][op]]=c
selected=set()
def cone(net):
 c=drivers.get(net)
 if not c or c['name'] in selected:return
 selected.add(c['name'])
 if c['kind'].startswith(('DFF','RAM','SDP')):return
 for pin,value in c['ports'].items():
  if pin.startswith(('I','S')):cone(value)
for c in cells.values():
 if '/bank_ER_RS_bank_ER_RS_' in c['name']:
  selected.add(c['name'])
  cone(c['ports']['DI']);cone(c['ports']['WRE'])
for net in (p+'bank_ER_init_71',p+'bank_ER_RS_149',p+'bank_245'):cone(net)
selected_text=[]
for name in sorted(selected,key=lambda n:cells[n]['line']):
 c=cells[name];selected_text.append(f"// .vo line {c['line']}\n"+c['text']+'\n'+'\n'.join(f'defparam \\{name} .{k}={v};' for k,v in c['parameters'].items()))
(HERE/'bank_validity_supplement.txt').write_text('\n\n'.join(selected_text)+'\n')
# Exact SDF arcs in the two selected data paths; retain per-corner sums.
edges=collections.defaultdict(list)
def delays(text):
 vectors=[tuple(float(x) for x in s.split(':')) for s in re.findall(r'\(([-+\d.eE:]+)\)',text)]
 assert vectors and all(len(v)==3 for v in vectors),text
 return tuple(max(v[i] for v in vectors) for i in range(3))
for a in json.loads((HERE/'selected_sdf_arcs.json').read_text()):
 edges[a['source']].append((a['destination'],delays(a['delay']),'INTERCONNECT'))
for part in (HERE/'selected_sdf_cells.txt').read_text().split('  (CELL\n')[1:]:
 name=re.search(r'\(INSTANCE ([^\s)]+)\)',part)[1].replace('\\','')
 if cells[name]['kind'].startswith(('DFF','RAM','SDP')):continue
 for line in part.splitlines():
  if '(IOPATH ' not in line:continue
  m=re.fullmatch(r'\s*\(IOPATH (\S+) (\S+)\s*(.+)\)\s*',line);assert m,line
  edges[name+'/'+m[1]].append((name+'/'+m[2],delays(m[3]),'IOPATH'))
paths=[]
for ff,bit in [('snapshot_32_s0',0),('snapshot_65_s0',1)]:
 start=p+ff+'/Q';target=p+'u_replies/g_inferred_storage.mem_g_inferred_storage.mem_0_0_s/DI['+str(bit)+']'
 found=[]
 def visit(node,steps,active):
  if node==target:found.append(steps);return
  if node in active:return
  for dest,delay,kind in edges[node]:visit(dest,steps+[dict(source=node,destination=dest,delay_ns=delay,kind=kind)],active|{node})
 visit(start,[],set());assert len(found)==1,(ff,len(found))
 path=found[0];summed=[round(sum(step['delay_ns'][i] for step in path),3) for i in range(3)]
 paths.append(dict(source=start,destination=target,steps=path,sum_min_typ_max_ns=summed,not_sta_slack=True))
report=dict(hardware_access=False,Gowin_executed=False,paths=paths,
 limits=['Q-to-DI interconnect plus combinational cell propagation sums only; no clk-to-Q, setup/hold, clock skew, uncertainty or slew-sensitive analysis.',
         'Existing reported STA observer path is a HOLD rd_bin[4] to SDPB with +0.231ns slack; no complete reported setup for these two exact paths.',
         'Bank validity supplement was extracted after Fable packet freeze; it is independent evidence, not claimed to have been in that packet.'])
(HERE/'data_path_sums.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(validity_cells=len(selected),paths=[dict(source=x['source'],destination=x['destination'],sum=x['sum_min_typ_max_ns']) for x in paths])))
