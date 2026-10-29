#!/usr/bin/env python3
"""Quick actual assembled mapping check after declaration-only formatting."""
import json
from pathlib import Path
import re
import check_assembled as test
import format_r21r1 as fmt
import build_memory_capture as b

def main():
 out=b.HERE/'formatted_test_01';out.mkdir()
 assembly=fmt.OUT/'format_assembly.json';data=json.loads(assembly.read_text());assert data['passed']
 for name,h in data['inputs'].items():assert b.sha(fmt.OUT/name)==h,name
 prior=b.HERE/'assembled_test_01/result.json';p=json.loads(prior.read_text());assert p['passed']
 names=p['tests']['copy']['modules']
 net=fmt.OUT/'console_neo.vg';modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',net.read_text(),re.M|re.S)}
 mapped=out/'mapped.v';mapped.write_text('\n\n'.join(modules[n] for n in names))
 files=[b.HERE/'assembled_test_01/copy/tb.sv',mapped,b.HERE/'assembled_test_01/copy/primitives.v']
 result=dict(passed=False,hardware_access=False,routing_started=False,netlist_sha256=b.sha(net),
  inputs={str(f):b.sha(f) for f in [Path(__file__),b.HERE/'check_assembled.py',assembly,prior,net,*files]},
  scope='Declaration-order-only candidate; actual assembled COPY/helper normal and CE-missing cases. Full prior helper/wiring proofs preserved by exact cell/port/assign equality.')
 try:
  result['runs']=test.run(out,files,[('normal',['+fault=0']),('missing_ce',['+fault=1'])],'PASS MAPPED COPY OBSERVER')
  for name,h in result['inputs'].items():assert b.sha(Path(name))==h,name
  result['passed']=True
 except Exception as e:result['error']=repr(e)
 finally:
  result['logs']={p.name:b.sha(p) for p in out.glob('*.log')}
  b.save(out/'result.json',result);print(json.dumps(result),flush=True)
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
