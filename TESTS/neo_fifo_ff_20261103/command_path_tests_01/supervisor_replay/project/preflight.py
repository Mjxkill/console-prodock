"""Tool and input integrity only; not an application test."""
import hashlib,json,subprocess
from pathlib import Path
r=Path(__file__).resolve().parent
for f in json.loads((r/'INPUTS.json').read_text())['files']:
 p=r/f['path']
 if hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:raise SystemExit('INPUT_CHANGED '+f['path'])
p=subprocess.run(['/usr/bin/verilator','--version'],capture_output=True,text=True)
print(p.stdout,end='');raise SystemExit(p.returncode)
