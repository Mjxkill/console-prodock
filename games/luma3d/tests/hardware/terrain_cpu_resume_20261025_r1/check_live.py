#!/usr/bin/env python3
"""Bounded resumption check; clear interrupted shell line, never stop a game."""
import fcntl,json,sys,time
from pathlib import Path
sys.path.insert(0,'/tmp/terrain_cpu_20261025_to3')
import serial
from prodock_order import identity,display,PORT,RELEASE,Transport
from check_linux import command
out=Path('/tmp/terrain_cpu_resume_20261025_r1');out.mkdir(exist_ok=False)
r=dict(passed=False,scope='Resumption after user stop; shell line cancelled, art3 unchanged')
try:
 with open('/tmp/prodock-diagnostic.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
   uart.write(b'\x03');uart.flush();time.sleep(.3);(out/'cancel_line.log').write_bytes(uart.read(16000))
   tx=Transport(uart,command,out)
   r['identity']=identity(tx,'resumed_art3')
   assert r['identity']==dict(pid=791,start_ticks=3876152)
   raw=tx.run('kernel_display','uname -r; prodockctl display');assert RELEASE in raw
   r['before']=display(raw);time.sleep(3)
   r['after']=display(tx.run('display_after','prodockctl display'))
   assert (r['after']['presents']-r['before']['presents'])&0xffffffff
   r['passed']=True
finally:
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
