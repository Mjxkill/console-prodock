"""Strict parser shared by local proofs and the future hardware controller."""
import math,re
def fields(line):
 out=dict((k.decode(),v.decode()) for k,v in re.findall(rb'(\w+)=(\S+)',line))
 for k,v in list(out.items()):
  if k in ('name','state_crc32','saves'):continue
  out[k]=float(v);assert math.isfinite(out[k]) and out[k]>=0,(k,v)
 return out
def parse(raw,kind,frames=360,fixture=False,hardware=False):
 assert b'LUMA3D_SAVE ' not in raw
 marker=re.findall(rb'^GPU_PROBE ([^\r\n]+)',raw,re.M);assert len(marker)==1
 marker=fields(marker[0]);assert marker['kind']==kind and marker['replay_steps']>0 and marker['replay_without_render']==1 and marker['saves']=='disabled'
 assert marker['hardware']==int(hardware) and marker['fixture']==int(fixture) and marker['fixed_frames']==frames and marker['wall_seconds']==0
 phases=[fields(x) for x in re.findall(rb'^GPU_PHASE ([^\r\n]+)',raw,re.M)]
 assert [x['name'] for x in phases]==(['entry'] if fixture else ['entry','rest','moving'])
 counters=[fields(x) for x in re.findall(rb'^GPU_COUNTERS ([^\r\n]+)',raw,re.M)];assert len(counters)==len(phases)
 tops=[fields(x) for x in re.findall(rb'^GPU_TOP ([^\r\n]+)',raw,re.M)];first=0
 for i,p in enumerate(phases):
  n=frames if fixture else [2,12,frames][i];assert p['frames']==n and p['kind']==kind and p['hardware']==int(hardware)
  assert p['wall']>0 and p['frame_sum']>0 and abs(p['wall']-p['frame_sum'])<.1
  assert 0<p['max_frame']<=p['frame_sum']+.000002 and first<=p['max_index']<first+n
  assert sum(p[k] for k in ('simulation','preparation','submit','present'))<=p['frame_sum']+.002
  assert p['static_publish']+p['dynamic_publish']<=p['preparation']+.002
  assert p['queue_overflows']==0 and p['exited']==0 and re.fullmatch('[0-9a-f]{8}',p['state_crc32'])
  for key in ('p95_upper_ms','p99_upper_ms'):assert (p[key]==0 and p['overflow']>0) or (4<=p[key]<=1020 and p[key]%4==0)
  if p['p95_upper_ms'] and p['p99_upper_ms']:assert p['p95_upper_ms']<=p['p99_upper_ms']
  rows=[x for x in tops if x['name']==p['name']];assert len(rows)==min(8,n)
  assert [x['rank'] for x in rows]==list(range(len(rows))) and len({x['index'] for x in rows})==len(rows)
  assert rows[0]['index']==p['max_index'] and abs(rows[0]['total']-p['max_frame'])<.000002
  for j,x in enumerate(rows):
   assert first<=x['index']<first+n and x['page']==int(x['index'])%2
   assert sum(x[k] for k in ('simulation','preparation','submit','present'))<=x['total']+.00001
   assert x['mesh_publish']<=x['preparation']+.00001
   if j:assert rows[j-1]['total']>=x['total']
  d=counters[i];assert d['name']==p['name'] and d['hardware']==int(hardware)
  if hardware:assert d['presents']==n
  else:assert all(v==0 for k,v in d.items() if k not in ('name','hardware'))
  p['fps']=p['frames']/p['wall'];first+=n
 done=re.findall(rb'^GPU_DONE ([^\r\n]+)',raw,re.M);assert len(done)==1;done=fields(done[0])
 assert done['ok']==1 and done['active']==kind+1 and done['showcase']==1 and done['hardware']==int(hardware)
 assert abs(done['simulated']-(0 if fixture and frames==1 else frames/60))<.000002
 return dict(phases=phases,counters=counters,top=tops,done=done,scope='Entry/rest/one-tick-per-frame windows; real-time showcase qualified separately')
