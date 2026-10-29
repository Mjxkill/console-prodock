"""Decode saved diagnostic text only; hardware identity belongs to root's acquisition guard."""
import argparse,json,math,re
from pathlib import Path
def need(ok,message):
 if not ok:raise ValueError(message)
def records(text,label):
 result=[]
 for line in text.splitlines():
  if not line.startswith(label+' '):continue
  row={}
  for part in line.split()[1:]:
   need(part.count('=')==1,'bad field '+label);key,value=part.split('=');need(key not in row,'duplicate '+key)
   if key=='phase':row[key]=value;continue
   need(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value) is not None,'invalid numeric '+key)
   number=float(value) if any(c in value for c in '.eE') else int(value);need(math.isfinite(number),'nonfinite '+key);row[key]=number
  result.append(row)
 return result
def one(text,label):
 values=records(text,label);need(len(values)==1,'missing/duplicate '+label);return values[0]
def parse(text,*,hardware,mode,memory_actions=None,table_actions=None):
 need(len(text.encode())<=1048576,'oversize log');need(mode in range(6),'bad mode')
 g=one(text,'LUMA3D_GRAPHICS_READY');r=one(text,'LUMA3D_RESULT');f=one(text,'LUMA3D_FESTIVAL');m=one(text,'LUMA3D_FESTIVAL_METRICS')
 phases=records(text,'LUMA3D_FESTIVAL_PHASE');assets=records(text,'LUMA3D_SCENE_ASSETS')
 need(phases and assets,'missing measured stages');need(all(x['hardware']==int(hardware) for x in [g,r,f,m]+phases+assets),'wrong declared origin')
 need(g['base_art_loaded']==1 and g['scene_resources_pending']==1,'wrong initialization semantics')
 need(f['active']==1 and f['mode']==mode,'wrong final scene');need(not r['benchmark'] and not r['warmup'],'unexpected benchmark')
 need(m['invalid']==m['publication_invalid']==0,'invalid measurement')
 names=[p['phase'] for p in phases];need(len(set(names))==len(names),'duplicate phase')
 need(set(names)<={'entry','deal','reveal','hide','pair','wait','table_active','table_wait','garden'},'unknown phase')
 need(sum(p['frames'] for p in phases)==m['frames']==r['frames'] and r['frames']>0,'frame partition')
 need(sum(p['commands'] for p in phases)==r['commands'] and sum(p['batches'] for p in phases)==r['batches'],'command partition')
 need(sum(p['cpu_bytes'] for p in phases)==m['cpu_bytes'],'publication partition')
 need(len(assets)==1 and assets[0]['frame']==0 and assets[0]['mode']==mode and assets[0]['asset_generation']==1,'not a fresh single scene')
 need(assets[0]['atlas_bytes']==(1048576 if mode==5 else 786432),'atlas volume')
 need(0<assets[0]['published_bytes']<=m['cpu_bytes'],'asset bytes')
 need(0<=assets[0]['atlas_publish_seconds']<=assets[0]['preparation_seconds']+.000001,'asset durations')
 sample=None
 if memory_actions is not None:
  need(mode==5 and 1<=memory_actions<=128,'invalid requested Memory window');sample=one(text,'LUMA3D_MEMORY_SAMPLE')
  need(sample['hardware']==int(hardware) and sample['requested_actions']==memory_actions,'wrong Memory sample')
  need(sample['complete']==1 and sample['invalid']==sample['publication_invalid']==0 and sample['tail']>=2 and sample['tail_pages']==3,'unfinished Memory pages')
  need(0<sample['actions']<=memory_actions and sample['actions']==sample['transition_actions']==sample['settled_actions'] and sample['skipped_actions']==0,'unpresented action')
  need(sample['frames']==r['frames'],'sample frame count')
  if memory_actions==24:need(set(names)=={'entry','deal','reveal','hide','pair','wait'},'missing complete-round phase')
 elif mode<4 and (table_actions is not None or records(text,'LUMA3D_FESTIVAL_SAMPLE')):
  sample=one(text,'LUMA3D_FESTIVAL_SAMPLE');need(sample['hardware']==int(hardware) and sample['kind']==mode,'wrong table sample')
  if table_actions is not None:need(sample['requested_actions']==table_actions,'wrong table action limit')
  need(sample['complete']==1 and sample['stable_tail']>=2 and sample['actions']==sample['completed_actions'] and sample['unseen_actions']==0 and sample['actions']>0,'incomplete table actions')
  need(sum(p['frames'] for p in phases if p['phase']=='table_active')==sample['active_frames'] and sample['frames']==r['frames'],'table active partition')
 result=dict(hardware=hardware,mode=mode,frames=r['frames'],cpu_bytes=m['cpu_bytes'],commands=r['commands'],batches=r['batches'],source_identity_must_be_verified_separately=True,phases=[],assets=[]) 
 for p in phases:
  need(p['frames']>0 and all(p[k]>=0 for k in ('commands','batches','cpu_bytes','cpu_publish_seconds','simulation_seconds','preparation_seconds','submit_seconds','present_seconds','max_interval_ms')),'negative measurement')
  need(p['completion_seconds']>0 and p['cpu_publish_seconds']<=p['preparation_seconds']+.000001 and p['preparation_seconds']<=p['completion_seconds']+.000001,'invalid duration subset')
  need(p['max_interval_ms']<=p['completion_seconds']*1000+.000001,'invalid maximum')
  need(p['rate_valid']==int(hardware),'invalid rate origin')
  if hardware:
   # Both values printed at finite precision: allow their rounding intervals.
   low=p['frames']/(p['completion_seconds']+.0000000005)-.0000005
   high=p['frames']/max(1e-15,p['completion_seconds']-.0000000005)+.0000005
   need(low<=p['rate']<=high,'inconsistent completion rate')
  else:need(p['rate']==0,'host rate must be suppressed')
  item={k:p[k] for k in ('phase','frames','commands','batches','cpu_bytes')}
  if hardware:
   item.update({k:p[k] for k in ('cpu_publish_seconds','completion_seconds','simulation_seconds','preparation_seconds','submit_seconds','present_seconds','max_interval_ms')})
   if (sample is not None and p['phase'] in ('deal','reveal','hide','pair','table_active')) or p['phase']=='garden':item['completion_rate']=p['rate']
  result['phases'].append(item)
 for a in assets:
  item={k:a[k] for k in ('mode','frame','asset_generation','published_bytes','atlas_bytes')}
  if hardware:item.update({k:a[k] for k in ('preparation_seconds','atlas_publish_seconds')})
  result['assets'].append(item)
 if sample is not None:result['actions']=sample['actions']
 result['scope']='Measured completion intervals only after independent board identity verification' if hardware else 'Host command/byte/coverage counts only; all host durations and rates omitted'
 return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--log',type=Path,required=True);ap.add_argument('--origin',choices=['host','hardware'],required=True);ap.add_argument('--mode',type=int,required=True);ap.add_argument('--memory-actions',type=int);ap.add_argument('--table-actions',type=int);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 result=parse(a.log.read_text(),hardware=a.origin=='hardware',mode=a.mode,memory_actions=a.memory_actions,table_actions=a.table_actions)
 with a.out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
 print(json.dumps(dict(parsed=True,hardware=result['hardware'],frames=result['frames'])))
if __name__=='__main__':main()
