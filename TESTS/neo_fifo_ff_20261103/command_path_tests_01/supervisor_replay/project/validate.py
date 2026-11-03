"""Require useful deliverables, never infer simulation PASS from formatting."""
import json
from pathlib import Path
r=Path(__file__).resolve().parent/'owned'
for name,minimum in [('REPORT.md',800),('TEST_RECORD.md',400),('bench.sv',500),('run.py',100)]:
 p=r/name
 if not p.exists() or p.stat().st_size<minimum:raise SystemExit('MISSING_OR_EMPTY '+name)
for p in r.iterdir():
 if p.suffix in ('.py','.sv','.v','.c','.h') and len(p.read_text().splitlines())>1000:raise SystemExit('LINE_LIMIT '+p.name)
x=json.loads((r/'RESULTS.json').read_text())
if not isinstance(x,dict) or not isinstance(x.get('cases'),list) or not x['cases']:raise SystemExit('RESULTS cases required')
if not isinstance(x.get('limits'),list) or not x['limits']:raise SystemExit('RESULTS limits required')
print('STRUCTURE_ONLY_PASS; supervisor must examine real simulations and mutants')
