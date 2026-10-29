#!/usr/bin/env python3
"""Root executes --run only after external review; no board operations."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import prepare_reports as p
from gowin_toolchain import IDE,environment

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 actions=parser.add_mutually_exclusive_group(required=True)
 actions.add_argument('--run',action='store_true');actions.add_argument('--check-only',action='store_true')
 parser.add_argument('--review',type=Path,required=True);args=parser.parse_args()
 checked=p.check();review_path=args.review.resolve(strict=True);review=json.loads(review_path.read_text())
 p.require(review.get('passed') is True and review.get('purpose')=='UTW1 syntax and reports full PNR','root review not approved for this operation')
 for key in ['netlist_sha256','format_assembly_sha256','reports_assembly_sha256']:
  p.require(review.get(key)==checked[key],'wrong reviewed '+key)
 p.require(review.get('launcher_sha256')==p.sha(Path(__file__)),'launcher changed since root review')
 p.require(p.sha(IDE/'bin/gw_sh')==p.previous.TOOL_SHA,'Gowin tool changed')
 if args.check_only:print(json.dumps(checked));return
 with (p.OUT/'route.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  p.require(not (p.OUT/'route_launch.json').exists() and not (p.OUT/'build.log').exists(),'existing route; preserve evidence and use a new reviewed build')
  p.record_build(p.OUT,p.before_build('neo',candidate=True));started=time.time();rc=None;error=None
  try:
   with (p.OUT/'build.log').open('x') as log:
    child=subprocess.Popen([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=p.OUT,env=environment(),stdout=log,stderr=log)
    p.save(p.OUT/'route_launch.json',dict(candidate=True,hardware_access=False,loaded=False,pid=child.pid,started_unix=started,
     tool=str(IDE/'bin/gw_sh'),tool_sha256=p.previous.TOOL_SHA,netlist_sha256=checked['netlist_sha256'],
     format_assembly_sha256=checked['format_assembly_sha256'],reports_assembly_sha256=checked['reports_assembly_sha256'],launcher_sha256=p.sha(Path(__file__)),
     root_review=str(review_path),root_review_sha256=p.sha(review_path),validation=checked['validation'],
     parent_parse_failure_preserved=True,incremental=False))
    print('UTW1_REPORTS_FULL_PNR_STARTED pid='+str(child.pid),flush=True);rc=child.wait()
  except BaseException as exc:error=repr(exc);raise
  finally:
   log=p.OUT/'build.log';text=log.read_text(errors='replace') if log.exists() else ''
   ok=rc==0 and error is None and 'Bitstream generation completed' in text and not re.search(r'^\s*ERROR',text,re.M) and (p.OUT/'impl/pnr/console_neo.fs').is_file()
   p.save(p.OUT/'route_result.json',dict(returncode=rc,error=error,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED_OR_INTERRUPTED',
    started_unix=started,finished_unix=time.time(),hardware_access=False,loaded=False,
    log_sha256=p.sha(log) if log.exists() else None,netlist_sha256=p.sha(p.OUT/'console_neo.vg'),
    bitstream_sha256=p.sha(p.OUT/'impl/pnr/console_neo.fs') if ok else None,
    caveat='If wrapper interrupted, inspect its recorded PID; do not kill unrelated Gowin processes.'))
  if not ok:raise SystemExit('R22r1 failed; evidence retained; no board access')
  print('R22r1 routed; structural/timing audit and hardware remain unqualified',flush=True)

if __name__=='__main__':main()
