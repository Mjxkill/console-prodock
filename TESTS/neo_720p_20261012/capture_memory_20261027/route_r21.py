#!/usr/bin/env python3
"""One reviewed R21 PnR; exact assembly and independent proofs; no board access."""
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import build_memory_capture as b

ASSEMBLY_SHA='bdfe9387fcca6195c4779e69536db88fbb05aa8f8ee50c7122ad443fa1afdfb4'
NETLIST_SHA='d773dca99127093b27e713f195b9ff62207c01a7810130c55d5d99499700d4cc'

def main():
 b.prepared_guard()
 assembly=b.OUT/'assembly.json';assert b.sha(assembly)==ASSEMBLY_SHA
 a=json.loads(assembly.read_text());assert a['netlist_sha256']==NETLIST_SHA
 for name,h in a['inputs'].items():assert b.sha(b.OUT/name)==h,name
 assert a['builder_sha256']==b.sha(b.HERE/'build_memory_capture.py')
 proofs=[b.HERE/'root_review_01.json',b.HERE/'assembled_test_01/result.json',b.HERE/'wiring_audit.json']
 for path in proofs:
  p=json.loads(path.read_text());assert p['passed'] and p['netlist_sha256']==NETLIST_SHA,path
  for name,h in p.get('inputs',{}).items():
   f=Path(name);f=f if f.is_absolute() else b.ROOT/f
   assert b.sha(f)==h,name
 root_review=json.loads(proofs[0].read_text());assert root_review['assembly_sha256']==ASSEMBLY_SHA
 tool=b.ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/gw_sh'
 assert b.sha(tool)==b.sha(b.IDE/'bin/gw_sh')
 with (b.OUT/'route.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert not (b.OUT/'route_launch.json').exists() and not (b.OUT/'build.log').exists()
  b.record_build(b.OUT,b.before_build('neo',candidate=True))
  started=time.time()
  with (b.OUT/'build.log').open('x') as log:
   child=subprocess.Popen([str(tool),'build.tcl'],cwd=b.OUT,env=b.environment(),stdout=log,stderr=log)
   b.save(b.OUT/'route_launch.json',dict(candidate=True,hardware_access=False,loaded=False,
    pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=b.sha(tool),
    netlist_sha256=NETLIST_SHA,assembly_sha256=ASSEMBLY_SHA,route_wrapper_sha256=b.sha(Path(__file__)),
    proof_sha256={str(p):b.sha(p) for p in proofs},
    authorization='Root explicit review and GO after wiring truth table PASS; one R21 route only',
    same_SDC_CST_DDR_PLL=True))
   print('R21_ROUTE_STARTED pid='+str(child.pid),flush=True)
   rc=child.wait()
  text=(b.OUT/'build.log').read_text()
  ok=rc==0 and 'Bitstream generation completed' in text and not re.search(r'^ERROR',text,re.M)
  b.save(b.OUT/'route_result.json',dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',
    started_unix=started,finished_unix=time.time(),hardware_access=False,loaded=False,
    log_sha256=b.sha(b.OUT/'build.log'),netlist_sha256=b.sha(b.OUT/'console_neo.vg')))
  if not ok:raise SystemExit('R21 routing failed; logs retained, no hardware access')
  print('R21 routed; timing/observer physical audit and root hardware review still required',flush=True)

if __name__=='__main__':main()
