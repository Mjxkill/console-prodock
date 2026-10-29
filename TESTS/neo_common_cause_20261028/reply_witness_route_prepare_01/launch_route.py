#!/usr/bin/env python3
"""Root-only explicit launch after review. Full P&R; no board access."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import prepare_route as p
from gowin_toolchain import IDE,environment

def review_guard(path):
 review=json.loads(path.read_text())
 p.require(review.get('passed') is True,'root review not passed')
 p.require(review.get('purpose')=='UTW1 full PNR','wrong root review purpose')
 p.require(review.get('netlist_sha256')==p.NET_SHA,'wrong reviewed netlist')
 p.require(review.get('preparation_sha256')==p.sha(p.OUT/'preparation.json'),'wrong reviewed preparation')
 p.require(review.get('launcher_sha256')==p.sha(Path(__file__)),'launcher changed since root review')
 return review

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=Path,required=True)
 parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
 check=p.check();review_path=args.review.resolve(strict=True);review_guard(review_path)
 if args.check_only:
  print(json.dumps(dict(passed=True,launch_requested=False,Gowin_executed=False,**{k:v for k,v in check.items() if k not in ['passed','Gowin_executed']})));return
 tool=IDE/'bin/gw_sh';p.require(p.sha(tool)==p.TOOL_SHA,'Gowin changed')
 with (p.OUT/'route.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  p.require(not (p.OUT/'route_launch.json').exists() and not (p.OUT/'build.log').exists(),'route already launched; use a new reviewed build for retry')
  p.record_build(p.OUT,p.before_build('neo',candidate=True))
  started=time.time();rc=None;error=None
  try:
   with (p.OUT/'build.log').open('x') as log:
    child=subprocess.Popen([str(tool),'build.tcl'],cwd=p.OUT,env=environment(),stdout=log,stderr=log)
    p.save(p.OUT/'route_launch.json',dict(candidate=True,board='neo',hardware_access=False,loaded=False,
     pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=p.sha(tool),netlist_sha256=p.NET_SHA,
     preparation_sha256=p.sha(p.OUT/'preparation.json'),launcher_sha256=p.sha(Path(__file__)),
     root_review=str(review_path),root_review_sha256=p.sha(review_path),incremental=False,
     qualification='NOT_QUALIFIED'))
    print('UTW1_FULL_PNR_STARTED pid='+str(child.pid),flush=True);rc=child.wait()
  except BaseException as exc:
   error=repr(exc);raise
  finally:
   log=p.OUT/'build.log';text=log.read_text(errors='replace') if log.exists() else ''
   ok=rc==0 and error is None and 'Bitstream generation completed' in text and not re.search(r'^\s*ERROR',text,re.M) and (p.OUT/'impl/pnr/console_neo.fs').is_file()
   p.save(p.OUT/'route_result.json',dict(returncode=rc,error=error,
    status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED_OR_INTERRUPTED',
    started_unix=started,finished_unix=time.time(),hardware_access=False,loaded=False,
    log_sha256=p.sha(log) if log.exists() else None,netlist_sha256=p.sha(p.OUT/'console_neo.vg'),
    bitstream_sha256=p.sha(p.OUT/'impl/pnr/console_neo.fs') if ok else None,
    caveat='If this wrapper is interrupted, inspect the recorded PID; never kill unrelated Gowin processes.'))
  if not ok:raise SystemExit('UTW1 route failed; evidence retained, no board access')
  print('UTW1 routed; post-route structural/timing review and hardware remain pending',flush=True)

if __name__=='__main__':main()
