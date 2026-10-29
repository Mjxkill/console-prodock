#!/usr/bin/env python3
"""Exercise the exact frozen debug RTL, not a software model of its mapping."""
import hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
rtl=ROOT/'tang/impl/console_neo_n56r22r1_utw1_reports/source/tang/boards/neo/neo_gpu_debug.v'
ivl=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
vvp=ivl.with_name('vvp')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
commands=[
 [str(ivl),'-B','/tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl','-g2012','-o',str(HERE/'tb_snapshot_counter.vvp'),str(HERE/'tb_snapshot_counter.v'),str(rtl)],
 [str(vvp),str(HERE/'tb_snapshot_counter.vvp')],
]
for i,cmd in enumerate(commands):
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
 (HERE/f'rtl_{i}.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError(p.stderr+p.stdout)
assert 'PASS exact RTL' in p.stdout
result=dict(passed=True,hardware_access=False,commands=commands,inputs={str(p):sha(p) for p in [rtl,HERE/'tb_snapshot_counter.v',ivl,vvp,Path(__file__)]},logs={str(p):sha(p) for p in [HERE/'rtl_0.log',HERE/'rtl_1.log']})
(HERE/'rtl_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(passed=True,hardware_access=False)))
