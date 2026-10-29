#!/usr/bin/env python3
"""Terminate only this task's exact runner; it records interruption and cleans MCP."""
import json
import os
from pathlib import Path
import signal
import time

HERE=Path(__file__).resolve().parent
matches=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal():continue
    try:
        args=(proc/'cmdline').read_bytes().split(b'\0')
        decoded=[x.decode() for x in args if x]
        if len(decoded)<3 or 'agent_runner.py' not in decoded[2]:continue
        if '--out' not in decoded:continue
        out=Path(decoded[decoded.index('--out')+1])
        if not out.is_absolute():out=Path(os.readlink(proc/'cwd'))/out
        if out!=HERE/'deepseek_02':continue
        matches.append((int(proc.name),(proc/'stat').read_text().rsplit(')',1)[1].split()[19]))
    except (OSError,ValueError,UnicodeError,IndexError):continue
if len(matches)>1:raise RuntimeError('Ambiguous runner identity')
report=dict(target='deepseek_02',matches=matches,unix=time.time(),sent=False)
if matches:
    pid,start=matches[0]
    if Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]!=start:
        raise RuntimeError('Process identity changed')
    os.kill(pid,signal.SIGTERM);report['sent']=True
(HERE/'stop_deepseek_02.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
