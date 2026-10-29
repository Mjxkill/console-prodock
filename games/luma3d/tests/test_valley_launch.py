#!/usr/bin/env python3
"""Exercise the actual first-frame supervisor command without hardware."""
import ast,os,signal,subprocess,tempfile,time
from pathlib import Path
tree=ast.parse((Path(__file__).parents[1]/'tools/prodock_valley_trial.py').read_text())
cmd=next(n.args[1].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='run' and len(n.args)>1 and isinstance(n.args[0],ast.Constant) and n.args[0].value=='first_launch')
for interrupted in (False,True):
 with tempfile.TemporaryDirectory() as directory:
  p=Path(directory);program=p/'luma3d-r1'
  program.write_text('#!/bin/sh\n'+('exec sleep 10\n' if interrupted else 'echo FRAME\nexit 0\n'));program.chmod(0o700)
  sent=cmd.replace('/tmp/luma3d',str(p/'luma3d'))+"; printf '\\n__PD_RC_%s__\\n' \"$?\"\n"
  start=time.monotonic();proc=subprocess.run(['sh','-c',sent],check=True,timeout=2,capture_output=True)
  assert b'__PD_RC_0__' in proc.stdout
  assert time.monotonic()-start<2,'Console shell blocked behind the frame process'
  deadline=time.monotonic()+3
  while not (p/'luma3d-live.pid').exists() and time.monotonic()<deadline:time.sleep(.01)
  pid=int((p/'luma3d-live.pid').read_text())
  if interrupted:os.kill(pid,signal.SIGTERM)
  while not (p/'luma3d-first.exit').exists() and time.monotonic()<deadline:time.sleep(.01)
  rc=int((p/'luma3d-first.exit').read_text());assert (rc==0)==(not interrupted)
  print('Supervisor PASS:', 'interruption retained, child stopped' if interrupted else 'exit0 recorded, console available')
