from pathlib import Path
import re,json,hashlib
R=Path('/home/michael/console');O=Path(__file__).parent
paths={k:R/v for k,v in {'prodock_g22r0':'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.vo','neo_r19':'tang/impl/console_neo_n56r19_capture_ce_local/impl/pnr/console_neo.vo','neo_r21r1':'tang/impl/console_neo_n56r21r1_capture_memory/impl/pnr/console_neo.vo','neo_r21r2':'tang/impl/console_neo_n56r21r2_resetqual_coupled/impl/pnr/console_neo.vo'}.items()}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={}
for key,p in paths.items():
 counts={};bad=[];missing=[];pending={}
 with p.open() as f:
  for n,l in enumerate(f,1):
   m=re.match(r'(DFF(?:CE|PE))\s+(\\?\S+)\s+\(',l)
   if m:pending[m[2]]=(m[1],n)
   m=re.match(r'defparam\s+(\\?\S+)\s*\.INIT\s*=\s*([^;]+);',l)
   if m and m[1] in pending:
    typ,line=pending.pop(m[1]);init=m[2].strip();counter=typ+' '+init;counts[counter]=counts.get(counter,0)+1
    expected="1'b0" if typ=='DFFCE' else "1'b1"
    if init!=expected:bad.append({'name':m[1],'type':typ,'line':line,'INIT':init,'expected':expected})
 result[key]={'path':str(p.relative_to(R)),'sha256':sha(p),'counts':counts,'polarity_inconsistencies':bad,'missing_INIT':pending}
 assert not pending,(key,pending)
(O/'all_async_result.json').write_text(json.dumps({'scope':'All explicitly instantiated DFFCE and DFFPE in four routed netlists, polarity/INIT only','hardware_access':False,'new_compilation':False,'source_sha256':sha(Path(__file__)),'results':result,'limits':['Not a proof of real initialization delivery, silicon pulse width or full vendor primitive coverage.','This excludes synchronous DFFRE/DFFSE and other cell types by design.','An INIT matching polarity does not prove correct reset timing or source clock activity.']},indent=2)+'\n')
print(json.dumps({k:{'counts':v['counts'],'inconsistencies':len(v['polarity_inconsistencies'])} for k,v in result.items()},indent=2))
