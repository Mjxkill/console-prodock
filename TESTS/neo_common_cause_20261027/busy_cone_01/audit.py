from pathlib import Path
import re,sys,hashlib,json
R=Path('/home/michael/console');O=Path(__file__).parent
sys.path.insert(0,str(R/'tools'));from gowin_toolchain import PRIMITIVES

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'\s+','',s).replace('\\','')
lib=PRIMITIVES.read_text();directions={}
for name,body in re.findall(r'^module\s+(\w+)\b(.*?)^endmodule',lib,re.M|re.S):
 out=set()
 for decl in re.findall(r'^\s*output\s+([^;]+);',body,re.M):
  decl=re.sub(r'\[[^]]*\]','',decl);out|=set(re.findall(r'\b[A-Za-z_]\w*\b',decl))-{'wire','reg','logic','signed','unsigned'}
 directions.setdefault(name,set()).update(out)
assert {'COUT','SUM'}<=directions['ALU']
result={}
for label,build,base in [('neo_r21r2','console_neo_n56r21r2_resetqual_coupled','console_neo'),('neo_r19','console_neo_n56r19_capture_ce_local','console_neo'),('prodock_g22r0','gpu_geometry_g22r0','console_gpu_geometry_g22r0')]:
 p=R/'tang/impl'/build/'impl/pnr'/f'{base}.vo';s=p.read_text();cells={};offset={}
 for m in re.finditer(r'^(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',s,re.M|re.S):
  kind,name,ports=m.groups()
  if kind=='module':continue
  name=norm(name);cells[name]=(kind,{pin:norm(v) for pin,v in re.findall(r'\.(\w+)\(([^()]*)\)',ports)});offset[name]=m.start()
 params={norm(n):norm(v) for n,v in re.findall(r'^defparam\s+(.+?)\s*=\s*([^;]+);',s,re.M)}
 drives={}
 for name,(kind,ports) in cells.items():
  for pin in directions.get(kind,set()):
   if pin in ports:drives.setdefault(ports[pin],[]).append((name,pin))
 endpoint='u_accel/busy_sync_0_s0';assert endpoint in cells
 cone={};leaves={};unknown={}
 def descend(net,stack=()):
  if net in ['GND','VCC']:return
  assert len(stack)<100,stack
  ds=drives.get(net,[])
  if len(ds)!=1:unknown[net]=ds;return
  name,port=ds[0];kind,pins=cells[name]
  if name in cone or name in leaves:return
  datum={'kind':kind,'output':port,'ports':pins,'params':{k.split('.')[-1]:v for k,v in params.items() if k.startswith(name+'.')},'line':s.count('\n',0,offset[name])+1}
  if kind.startswith('DFF') or kind in ['GND','VCC']:
   leaves[name]=datum;return
  assert kind in directions,kind
  cone[name]=datum
  for pin,wire in pins.items():
   if pin not in directions[kind]:descend(wire,stack+(name,))
 descend(cells[endpoint][1]['D'])
 consumers={}
 for name in [endpoint,'u_accel/busy_sync_1_s0']:
  q=cells[name][1]['Q'];consumers[name]=[{'cell':n,'kind':k,'pin':pin} for n,(k,ports) in cells.items() for pin,net in ports.items() if net==q and pin not in directions.get(k,set())]
 timing=[];tr=p.with_suffix('.tr');txt=tr.read_text()
 for m in re.finditer(r'Path Summary:\n(.*?)(?=Path Summary:|\Z)',txt,re.S):
  block=m[1]
  if re.search(r'^To\s*:\s*u_accel/busy_sync_0_s0\s*$',block,re.M):
   timing.append({'line':txt.count('\n',0,m.start())+1,'fields':{k:re.search(r'^'+re.escape(k)+r'\s*:\s*(.*)$',block,re.M)[1].strip() for k in ['Slack','Data Arrival Time','Data Required Time','From','To','Launch Clk','Latch Clk']}})
   (O/(label+'_path.txt')).write_text('Path Summary:\n'+block)
 result[label]={'vo_path':str(p.relative_to(R)),'vo_sha256':sha(p),'tr_sha256':sha(tr),'endpoint':{'kind':cells[endpoint][0],'ports':cells[endpoint][1]},'comb_cells':cone,'leaf_ff':leaves,'unknown':unknown,'consumers':consumers,'timing_paths':timing}
 assert not unknown,(label,unknown)
 print(label,'comb',len(cone),'leaf',len(leaves),'clocks',sorted({x['ports'].get('CLK') for x in leaves.values()}),'paths',timing)
(O/'result.json').write_text(json.dumps({'hardware_access':False,'new_simulation':False,'primitive_library':str(PRIMITIVES),'primitive_library_sha256':sha(PRIMITIVES),'tool_sha256':sha(Path(__file__)),'results':result},indent=2)+'\n')
