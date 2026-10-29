#!/usr/bin/env python3
"""Route reviewed declaration-only R21r1; preserves the R21 parser failure."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import build_memory_capture as b
import format_r21r1 as fmt

ASSEMBLY_SHA='f277336a53483a67bb9f2a134e3452f40c25028b2f536ce9ea5fda1a7cfd22fa'
NETLIST_SHA='3f49d84ccb8b2001e5afa156b36849705652003fbf4e2a741847dc23f1713338'

def main():
 p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True);a=p.parse_args();a.review=a.review.resolve()
 b.prepared_guard()
 assembly=fmt.OUT/'format_assembly.json';assert b.sha(assembly)==ASSEMBLY_SHA
 data=json.loads(assembly.read_text());assert data['passed'] and data['netlist_sha256']==NETLIST_SHA
 assert data['builder_sha256']==b.sha(b.HERE/'format_r21r1.py')
 for name,h in data['inputs'].items():assert b.sha(fmt.OUT/name)==h,name
 for path,h in data['proof_sha256'].items():assert b.sha(Path(path))==h,path
 assert b.manifest(fmt.OUT/'source')==json.loads((fmt.OUT/'sources.json').read_text())
 proof=b.HERE/'formatted_test_01/result.json';test=json.loads(proof.read_text())
 assert test['passed'] and test['netlist_sha256']==NETLIST_SHA
 for path,h in test['inputs'].items():assert b.sha(Path(path))==h,path
 review=json.loads(a.review.read_text());assert review['passed'] and review['netlist_sha256']==NETLIST_SHA
 assert review.get('format_assembly_sha256',review.get('assembly_sha256'))==ASSEMBLY_SHA
 tool=b.ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/gw_sh';assert b.sha(tool)==b.sha(b.IDE/'bin/gw_sh')
 with (fmt.OUT/'route.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert not (fmt.OUT/'route_launch.json').exists() and not (fmt.OUT/'build.log').exists()
  b.record_build(fmt.OUT,b.before_build('neo',candidate=True));started=time.time()
  with (fmt.OUT/'build.log').open('x') as log:
   child=subprocess.Popen([str(tool),'build.tcl'],cwd=fmt.OUT,env=b.environment(),stdout=log,stderr=log)
   b.save(fmt.OUT/'route_launch.json',dict(candidate=True,hardware_access=False,loaded=False,pid=child.pid,
    started_unix=started,tool=str(tool),tool_sha256=b.sha(tool),netlist_sha256=NETLIST_SHA,
    format_assembly_sha256=ASSEMBLY_SHA,wrapper_sha256=b.sha(Path(__file__)),
    independent_review=str(a.review),independent_review_sha256=b.sha(a.review),
    formatted_mapped_proof_sha256=b.sha(proof),inherited_proof_sha256=data['proof_sha256'],
    prior_parser_failure_preserved=True))
   print('R21R1_ROUTE_STARTED pid='+str(child.pid),flush=True);rc=child.wait()
  text=(fmt.OUT/'build.log').read_text()
  ok=rc==0 and 'Bitstream generation completed' in text and not re.search(r'^ERROR',text,re.M)
  b.save(fmt.OUT/'route_result.json',dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',
    started_unix=started,finished_unix=time.time(),hardware_access=False,loaded=False,
    log_sha256=b.sha(fmt.OUT/'build.log'),netlist_sha256=b.sha(fmt.OUT/'console_neo.vg')))
  if not ok:raise SystemExit('R21r1 route failed; evidence retained, no board access')
  print('R21r1 routed; timing/observer review and hardware remain pending',flush=True)

if __name__=='__main__':main()
