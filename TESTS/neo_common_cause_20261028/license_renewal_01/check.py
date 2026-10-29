#!/usr/bin/env python3
"""Run only a new Gowin project creation to check renewed licence acceptance."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from gowin_toolchain import IDE, environment

attempt = sys.argv[1]
if attempt not in ('sandbox', 'host'):
    raise SystemExit('Unknown attempt')
log = OUT / (attempt + '.log')
with log.open('x') as stream:
    run = subprocess.run([str(IDE / 'bin/gw_sh'), str(OUT / 'probe.tcl')],
                         cwd=OUT, env=environment(), stdout=stream, stderr=stream,
                         timeout=60)
text = log.read_text(errors='replace')
passed = run.returncode == 0 and 'NEO_LICENSE_RENEWAL_TCL_OK' in text
result = dict(passed=passed, returncode=run.returncode, hardware_access=False,
              synthesis=False, placement_routing=False, tool=str(IDE / 'bin/gw_sh'),
              tool_sha256=hashlib.sha256((IDE / 'bin/gw_sh').read_bytes()).hexdigest(),
              log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
(OUT / (attempt + '.json')).write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
if not passed:
    print(text[-2000:])
raise SystemExit(0 if passed else 1)
