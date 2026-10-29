from pathlib import Path
import json,re,hashlib
R=Path('/home/michael/console');O=Path(__file__).parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths={
 'prodock_g22r0':R/'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.vo',
 'neo_r19':R/'tang/impl/console_neo_n56r19_capture_ce_local/impl/pnr/console_neo.vo',
 'neo_r21r1':R/'tang/impl/console_neo_n56r21r1_capture_memory/impl/pnr/console_neo.vo',
 'neo_r21r2':R/'tang/impl/console_neo_n56r21r2_resetqual_coupled/impl/pnr/console_neo.vo'}
patterns=[r'^pixel_up_',r'^ae350_rst_sync_',r'^u_gpu/prst_',r'^u_gpu/u_frames/',r'^u_gpu/u_display_checksum/',r'^u_usb_(?:ref|phy|controller)_start/']
keep=re.compile('|'.join(patterns));out={}
for name,p in paths.items():
 cells={};lines=p.read_text().splitlines();i=0
 while i<len(lines):
  line=lines[i];m=re.match(r'(DFF\w*)\s+(\\?\S+)\s+\(',line)
  if m and keep.search(m[2].lstrip('\\')):
   start=i;txt=[];i+=1
   while i<len(lines) and lines[i].strip()!=');':txt.append(lines[i]);i+=1
   params=[];i+=1
   while i<len(lines) and lines[i].startswith('defparam '):params.append(lines[i]);i+=1
   ports={a:''.join(b.split()) for a,b in re.findall(r'\.(\w+)\((.*?)\)', '\n'.join(txt))};init=re.findall(r'\.INIT\s*=\s*([^;]+);','\n'.join(params));assert len(init)==1,(name,m[2],params)
   cells[m[2].lstrip('\\')]={'type':m[1],'line':start+1,'ports':ports,'INIT':init[0]}
  else:i+=1
 groups={}
 for prefix in ['pixel_up','ae350_rst_sync','u_gpu/prst','u_gpu/u_frames/','u_gpu/u_display_checksum/','u_usb_ref_start/','u_usb_phy_start/','u_usb_controller_start/']:
  c={k:v for k,v in cells.items() if k.startswith(prefix)}
  groups[prefix]={'count':len(c),'init_counts':{z:sum(x['INIT']==z for x in c.values()) for z in sorted({x['INIT'] for x in c.values()})},'async_reset_init_conflicts':[k for k,v in c.items() if (v['type']=='DFFCE' and v['INIT']!="1'b0") or (v['type']=='DFFPE' and v['INIT']!="1'b1")], 'non_ground_async_controls':{k:{x:v['ports'][x] for x in ['CLEAR','PRESET'] if x in v['ports'] and v['ports'][x]!='GND'} for k,v in c.items() if any(v['ports'].get(x,'GND')!='GND' for x in ['CLEAR','PRESET'])}}
 # Core expectation only, not claims about all FF primitives.
 for prefix in ['u_gpu/u_frames/','u_gpu/u_display_checksum/']:
  assert groups[prefix]['count']==71,(name,prefix,groups[prefix]['count'])
  assert groups[prefix]['init_counts']=={"1'b0":71}
  assert not groups[prefix]['non_ground_async_controls']
 if name!='prodock_g22r0':assert groups['pixel_up']['count']==3
 assert groups['u_gpu/prst']['count']==2
 assert not any(x['async_reset_init_conflicts'] for x in groups.values())
 out[name]={'source':str(p.relative_to(R)),'sha256':sha(p),'groups':groups,'cells':cells}
(O/'cells.json').write_text(json.dumps(out,indent=2)+'\n')
comparisons={}
ref=out['neo_r19']['cells']
for name in ['neo_r21r1','neo_r21r2']:
 target=out[name]['cells'];assert set(ref)==set(target)
 diffs=[]
 for k,v in ref.items():
  if (v['type'],v['INIT'])!=(target[k]['type'],target[k]['INIT']):diffs.append(k)
 comparisons[name]={'same_cell_names':True,'type_and_INIT_differences':diffs,'count':len(ref)}
logs=[R/'tang/impl/console_neo_n56r9_scan_observer/impl/gwsynthesis/console_neo.log',R/'tang/impl/console_neo_n56r21r1_capture_memory/capture_ip/neo_capture_local/synth_attempt_01.log',R/'TESTS/neo_720p_20261012/capture_memory_20261027/reset_contract_01/candidate_01/synthesis_02/synthesis.log']
logaudit=[]
for p in logs:
 if not p.exists():continue
 matches=[{'line':i,'text':l} for i,l in enumerate(p.read_text(errors='replace').splitlines(),1) if re.search(r'warn.*(initial|asynchron|ignored)',l,re.I)]
 logaudit.append({'file':str(p.relative_to(R)),'sha256':sha(p),'warnings':matches})
result={'status':'TARGETED_MAPPED_INIT_VALUES_CONSISTENT','hardware_access':False,'new_compilation':False,'tool_sha256':sha(Path(__file__)),'cells_sha256':sha(O/'cells.json'),'summary':{k:v['groups'] for k,v in out.items()},'neo_comparison':comparisons,'synthesis_logs':logaudit,'limits':['Only specified pixel/CDC/USB reset/CPU reset cells checked; not all netlist initialization.', 'G22r0 original synthesis log is absent from current archived build directories; exact routed primitives provide direct evidence instead.', 'DFFCE INIT0 and DFFPE INIT1 agree with async reset polarity; this is not proof of silicon startup pulse width or clock availability.', 'cdc_word has no runtime reset and dst_data lacks explicit RTL INIT; mapped destination FF INIT0 is tool default, while req/ack/hold initial values are explicit.', 'No physical causality established.']}
(O/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'checked_cells':{k:len(v['cells']) for k,v in out.items()},'result_sha256':sha(O/'result.json'),'neo_comparison':comparisons},indent=2))
