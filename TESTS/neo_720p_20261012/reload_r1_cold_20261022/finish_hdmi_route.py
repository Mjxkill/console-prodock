#!/usr/bin/env python3
"""Wait for this single reviewed route, then save qualification; no hardware."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUILD=ROOT/'tang/impl/console_neo_n56r7_hdmi_pg0'
EXPECTED='db370e7750e785abed97128a62d88403f90b91c972a28aaea1746b5f76c42e77'
deadline=time.monotonic()+7200
print('Waiting for the reviewed N56r7 route; no board access.',flush=True)
while not (BUILD/'route_result.json').is_file():
    if time.monotonic()>deadline:
        raise SystemExit('Route still incomplete after two hours; no qualification attempted')
    time.sleep(15)
route=json.loads((BUILD/'route_result.json').read_text())
assert route['manifest_sha256']==EXPECTED
if route['status']!='ROUTED_NOT_QUALIFIED':
    raise SystemExit('Route failed; no qualification or hardware action')
results=[]
for label,command in [
    ('qualification',[sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(BUILD)]),
    ('hdmi_pg0_audit',[sys.executable,str(HERE/'audit_console_hdmi_pg0.py')]),
]:
    with (BUILD/(label+'_automatic.log')).open('x') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    results.append(dict(check=label,returncode=result.returncode))
    print(json.dumps(results[-1]),flush=True)
with (BUILD/'automatic_checks.json').open('x') as log:
    json.dump(dict(checks=results,hardware_access=False,
                   note='Review full reports before any board experiment.'),log,indent=2)
raise SystemExit(0 if all(r['returncode']==0 for r in results) else 1)
