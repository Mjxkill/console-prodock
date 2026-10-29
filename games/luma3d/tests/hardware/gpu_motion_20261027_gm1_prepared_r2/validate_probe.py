#!/usr/bin/env python3
import argparse,hashlib,json,subprocess
from pathlib import Path
from probe_metrics import parse
C=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();q=a.probe.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);m=json.loads((q/'manifest.json').read_text());records=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for variant in ('baseline','candidate'):
 f=q/(variant+'-host');assert sha(f)==next(x['elf_sha256'] for x in m['records'] if x['variant']==variant and x['target']=='host')
 for wide in (False,True):
  for kind in (1,3,4,5,6):
   cmd=[f,'--host','--kind',str(kind),'--frames','360']+(['--720p'] if wide else [])
   r=subprocess.run(cmd,capture_output=True,timeout=120);name=f'{variant}_{kind}_{1280 if wide else 800}';(o/(name+'.log')).write_bytes(r.stdout+r.stderr);r.check_returncode()
   value=parse(r.stdout,kind);records.append(dict(variant=variant,kind=kind,width=1280 if wide else 800,result=value));print(name,flush=True)
 for args in [[],['--host','--kind','2','--frames','1'],['--host','--kind','3','--frames','64','--fixture'],['--host','--kind','3','--wall','1'],['--save','/tmp/forbidden.save']]:
  r=subprocess.run([f,*args],capture_output=True,timeout=5);assert r.returncode==2
for width in (800,1280):
 for kind in (1,3,4,5,6):
  rows=[x for x in records if x['width']==width and x['kind']==kind];assert len(rows)==2
  for before,after in zip(rows[0]['result']['phases'],rows[1]['result']['phases']):assert before['state_crc32']==after['state_crc32'],(kind,before['name'])
  if kind in (1,3,5):
   resting=rows[1]['result']['phases'][1];assert resting['commands']==resting['batches']==resting['ui_bytes']==resting['rasters']==0
# Negative normalization/index/warmup tests use a real record, not invented PASS logs.
raw=(o/'candidate_4_800.log').read_bytes();negative=[]
for label,bad in [('wrong_kind',raw.replace(b'kind=4',b'kind=3',1)),('wrong_count',raw.replace(b'frames=360 ',b'frames=1 ',1)),('wrong_units',raw.replace(b'p95_upper_ms=4 ',b'p95_upper_ms=3 ',1)),('lost_done',raw.replace(b'GPU_DONE',b'IGNORED_DONE'))]:
 try:parse(bad,4)
 except (AssertionError,KeyError,ValueError):negative.append(label)
 else:raise AssertionError('Negative accepted: '+label)
(o/'result.json').write_text(json.dumps(dict(passed=True,hardware=False,probe_manifest_sha256=sha(q/'manifest.json'),parser_sha256=sha(C/'probe_metrics.py'),runner_sha256=sha(Path(__file__)),records=records,negative_cases=negative,scope='Fixed-state windows, native two profiles, exact logical codecs; host time not hardware FPS.'),indent=2)+'\n');print('GPU_PROBE_VALIDATION_PASS')
