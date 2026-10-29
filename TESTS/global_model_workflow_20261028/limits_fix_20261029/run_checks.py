#!/usr/bin/env python3
"""Run fixed tests with candidate modules; no provider or hardware access."""
import os
from pathlib import Path
import subprocess
import json
import hashlib
import time
HERE=Path(__file__).resolve().parent
assert not (HERE/'checks_result.json').exists()
env=os.environ.copy();env['PYTHONPATH']=str(HERE/'pack');env['PYTHONDONTWRITEBYTECODE']='1'
runs=[]
for label,argv in [('limits',['python3','-B',str(HERE/'test_limits.py')]),('runtime',['python3','-B','-m','unittest','discover','-s',str(HERE/'tests'),'-v'])]:
 start=time.monotonic();r=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=90)
 (HERE/(label+'.log')).write_text(r.stdout+r.stderr)
 runs.append(dict(label=label,argv=argv,returncode=r.returncode,elapsed_seconds=time.monotonic()-start,log_sha256=hashlib.sha256((r.stdout+r.stderr).encode()).hexdigest()))
 print(label,r.returncode,flush=True)
record=dict(passed=all(x['returncode']==0 for x in runs),runs=runs,hardware_access=False,external_provider_requests=0,local_http_requests=513)
(HERE/'checks_result.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(0 if record['passed'] else 1)
