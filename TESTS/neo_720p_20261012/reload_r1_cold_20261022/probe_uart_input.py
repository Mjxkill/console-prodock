#!/usr/bin/env python3
"""Compare individual printable host bytes with Neo AE350 UART2 RBR via JTAG.

Requires current halted parking after fallback_bars. No CPU program, DDR,
scanout, flash or SD write. Initializes UART2 to 115200 (APB80M divider43).
Avoids debugger escape bytes. Never enters the BL616 command menu.
"""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import serial

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/neo'))
from console import UART

prior=json.loads((HERE/'fallback_bars/result.json').read_text())
assert prior['complete'] and prior['cpu_left_halted'] and not prior['linux_running']
assert prior['bitstream_sha256']=='426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d'
out=HERE/'uart_direct';out.mkdir(exist_ok=False)
pattern=bytes(range(32,127))+b'oOoOuUuUjJjJxxxxxxxxUUUUUUUUUUUUU'
(out/'sent.bin').write_bytes(pattern)
script=out/'probe.tcl'
script.write_text('''init
halt
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected parking privilege"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "Wrong parking PC"}
if {[lindex [read_memory 0x80000000 32 1] 0]!=0x10500073} {error "Wrong boot ROM"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500 || [lindex [read_memory 0xe9000008 32 1] 0]!=0} {error "Not the fallback display state"}
echo "UART_BEFORE [read_memory 0xf030002c 32 3]"
write_memory 0xf030002c 32 {0x83}
write_memory 0xf0300020 32 {43}
write_memory 0xf0300024 32 {0}
write_memory 0xf030002c 32 {3}
write_memory 0xf0300028 32 {7}
write_memory 0xf0300024 32 {0}
echo UART_DIRECT_READY
''' + f'for {{set i 0}} {{$i<{len(pattern)}}} {{incr i}} {{\n' + '''    set received 0
    for {set j 0} {$j<400} {incr j} {
        set status [lindex [read_memory 0xf0300034 32 1] 0]
        if {$status & 1} {set received 1;break}
        sleep 5
    }
    if {!$received} {error "UART receive timeout at $i"}
    set value [lindex [read_memory 0xf0300020 32 1] 0]
    echo "UART_DIRECT_RX $i $status $value"
}
echo UART_DIRECT_COMPLETE
shutdown
''')
report=dict(passed=False,bitstream_sha256=prior['bitstream_sha256'],samples=[],
    expected_count=len(pattern),cpu_left_halted=True,sd_written=False,flash_written=False,
    scanout_modified=False,uart_route='preserved',host_baud=2000000,uart_divider=43,
    script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
try:
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as port, (out/'openocd.log').open('w') as log:
            proc=subprocess.Popen(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            timer=threading.Timer(120,proc.kill);timer.start()
            try:
                for line in proc.stdout:
                    log.write(line);log.flush()
                    if line.strip()=='UART_DIRECT_READY':port.write(pattern[:1])
                    m=re.match(r'UART_DIRECT_RX (\d+) (\S+) (\S+)',line)
                    if m:
                        i=int(m[1]);status=int(m[2],0);value=int(m[3],0)
                        assert i==len(report['samples'])
                        report['samples'].append(dict(index=i,expected=pattern[i],received=value,
                            xor=pattern[i]^value,status=status,error_flags=status&0x1e))
                        if (i+1)%16==0:print(f'Received {i+1}/{len(pattern)}',flush=True)
                        if i+1<len(pattern):
                            time.sleep(.02);port.write(pattern[i+1:i+2])
                rc=proc.wait(timeout=5)
            finally:
                timer.cancel()
                if proc.poll() is None:proc.kill();proc.wait(timeout=5)
            report['returncode']=rc
    report['mismatches']=[v for v in report['samples'] if v['xor'] or v['error_flags']]
    report['passed']=rc==0 and len(report['samples'])==len(pattern) and not report['mismatches']
except Exception as e:
    report['error']=str(e)
finally:
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2))
raise SystemExit(0 if report['passed'] else 1)
