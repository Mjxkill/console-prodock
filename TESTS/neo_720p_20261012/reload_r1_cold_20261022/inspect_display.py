#!/usr/bin/env python3
"""Observe the freshly booted R1 CPU, display counters and UART; resume Linux."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
prior=json.loads((HERE/'linux/result.json').read_text())
if not prior['passed'] or prior['bitstream_sha256']!='426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d':
    raise ValueError('Expected the verified cold R1 Linux launch')
out=a.out.resolve();out.mkdir(exist_ok=False)
if any(c in str(out) for c in '{}\\\n\r'):raise ValueError('Invalid path')
tcl=out/'probe.tcl'
tcl.write_text('''init
halt
set failed [catch {
    echo "LINUX_CONTEXT [reg pc] [reg priv] [reg satp]"
    if {[lindex [reg satp] 2]==0} {error "Expected Linux address space"}
    riscv set_enable_virt2phys off
    if {[lindex [read_memory 0x08192802 16 1] 0]!=0x0073 || [lindex [read_memory 0x08192804 16 1] 0]!=0x1050 || [lindex [read_memory 0x0947d028 32 1] 0]!=3} {error "Linux fingerprint differs"}
    if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong display geometry"}
    for {set i 0} {$i<3} {incr i} {
        echo "DISPLAY_SAMPLE $i [read_memory 0xe9000000 32 32]"
        echo "GPU_SAMPLE $i [read_memory 0xe9001000 32 20]"
        echo "UART_SAMPLE $i [read_memory 0xf030002c 32 3]"
        resume
        sleep 100
        halt
        echo "CPU_SAMPLE $i [reg pc] [reg priv]"
    }
''' + f'dump_image {{{out/"kernel_log.bin"}}} 0x09484744 32768\n' + '''} reason]
resume
echo LINUX_RESUMED
if {$failed} {error $reason}
echo DISPLAY_OBSERVATION_COMPLETE
shutdown
''')
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (out/'openocd.log').open('w') as log:
        done=subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(tcl)],
            stdout=log,stderr=subprocess.STDOUT,timeout=30)
text=(out/'openocd.log').read_text()
result=dict(complete=done.returncode==0 and 'DISPLAY_OBSERVATION_COMPLETE' in text,
            linux_resumed='LINUX_RESUMED' in text,returncode=done.returncode,
            probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            kernel_log_sha256=hashlib.sha256((out/'kernel_log.bin').read_bytes()).hexdigest() if (out/'kernel_log.bin').exists() else None)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(text)
if not result['complete']:raise SystemExit('Display observation incomplete')
