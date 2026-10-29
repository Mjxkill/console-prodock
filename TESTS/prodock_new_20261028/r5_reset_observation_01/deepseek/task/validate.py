import json
from pathlib import Path
p=Path(__file__).resolve().parent
f=json.loads((p/'owned/findings.json').read_text())
assert len(f.get('edges',[]))>=30
cs={b:json.loads((p/f'context/{b}_cone.json').read_text())['cells'] for b in ['g22','r5']}
seen=set()
for e in f['edges']:
 assert e['build'] in cs
 assert cs[e['build']][e['cell']]['ports'][e['pin']]==e['net'],e
 seen.add(e['build'])
assert seen=={'g22','r5'}
assert len(f.get('domains',[]))>=4 and len(f.get('observations',[]))>=3 and len(f.get('limitations',[]))>=2
assert len((p/'owned/REPORT.md').read_text())>1500
print('PASS exact primitive references and report shape; causal claims require independent review')
