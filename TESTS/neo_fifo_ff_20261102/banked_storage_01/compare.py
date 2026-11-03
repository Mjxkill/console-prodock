#!/usr/bin/env python3
"""Mapped helper counts/fanouts/controls only; no routability or STA inference."""
import argparse,collections,hashlib,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
RECIPE=HERE.parent/'build_review_01/recipe.py'
BASE=HERE.parent/'build_review_01/stage_02/helper/neo_command_ff128.vg'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect(path):
 spec=importlib.util.spec_from_file_location('banked_read_recipe',RECIPE);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
 a=r.modules_api();mods=a.modules(path.read_text());cells=a.instances(mods['neo_command_ff128'])
 counts=collections.Counter(c['kind'] for c in cells.values());fan=collections.Counter();edges={};controls={p:collections.Counter() for p in ['CLK','RESET','CE']}
 for name,c in cells.items():
  kind=c['kind'];p=c['ports']
  if kind.startswith('LUT'):
   inputs=[p['I'+str(i)] for i in range(int(kind[3:]))];edges[p['F']]=inputs
  elif kind.startswith('DFF'):
   inputs=[p[x] for x in ['D','CLK','CE','RESET']]
   for pin in controls:controls[pin][''.join(p[pin])]+=1
  elif kind=='GSR':
   if p!={'GSRI':('VCC',)}:raise ValueError('Nonconstant global reset')
   inputs=[]
  elif kind in ['VCC','GND']:inputs=[]
  else:raise ValueError('Unexpected primitive '+kind)
  fan.update(inputs)
 cache={};active=set()
 def depth(node):
  if node not in edges:return 0
  if node in cache:return cache[node]
  if node in active:raise ValueError('Combinational cycle')
  active.add(node);d=1+max(map(depth,edges[node]));active.remove(node);cache[node]=d;return d
 for n in edges:depth(n)
 return {'sha256':sha(path),'counts':dict(counts),'ff_total':sum(v for k,v in counts.items() if k.startswith('DFF')),
  'lut_total':sum(v for k,v in counts.items() if k.startswith('LUT')),'max_lut_depth':max(cache.values()),
  'input_fanouts':{''.join(k):v for k,v in fan.items() if k[0] in ['ADB','ADA','DI','CLKA','CLKB','CEB','RESET']},
  'top_fanouts':[{'net':''.join(k),'sinks':v}for k,v in fan.most_common(24)],
  'ff_control_uses':{k:dict(v) for k,v in controls.items()},'ram_count':0,
  'limits':'Mapped primitive pins only, not physical net replication/placement/fanout/STA; array names tokenized escaped-safe.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('candidate',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();start=time.monotonic()
 b,n=inspect(BASE),inspect(a.candidate)
 if n['ff_total']!=4128:raise ValueError('Storage/output FF count changed')
 result={'analysis_complete':True,'base':b,'candidate':n,'lut_delta_per_helper':n['lut_total']-b['lut_total'],'ff_delta_per_helper':n['ff_total']-b['ff_total'],
  'ADB_read_address_fanouts':{f'ADB[{i}]':{'before':b['input_fanouts'].get(f'ADB[{i}]',0),'after':n['input_fanouts'].get(f'ADB[{i}]',0)} for i in range(5,12)},
  'physical_CLS_usage':None,'timing_qualified':False,'routability_qualified':False,'elapsed_seconds':time.monotonic()-start}
 a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['base','candidate']},indent=2))
if __name__=='__main__':main()
