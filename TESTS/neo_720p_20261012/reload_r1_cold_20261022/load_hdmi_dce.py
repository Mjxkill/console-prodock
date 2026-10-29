#!/usr/bin/env python3
"""Load the timing-clean 720p HDMI-only DCE probe after live parking check."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_program_status
build=HERE/'hdmi_bars_dce'
record=json.loads((build/'result.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert record['complete'] and record['variant']=='dce'
for name,digest in record['source_sha256'].items():assert sha(build/name)==digest
for name in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
    assert sha(build/name)==record[name+'_sha256']
report=(build/'impl/pnr/probe.tr').read_text()
margins={}
for i,kind in enumerate(['Setup','Hold','Recovery','Removal'],1):
    table=re.search(r'^3\.1\.'+str(i)+' '+kind+r' Paths Table.*?(?=^3\.|\Z)',report,re.M|re.S)[0]
    values=[float(v) for v in re.findall(r'^\s+\d+\s+(-?\d+\.\d+)\s+',table,re.M)]
    assert values and min(values)>0
    margins[kind]=min(values)
assert '<Numbers of Setup Violated Endpoints>:0' in report
assert '<Numbers of Hold Violated Endpoints>:0' in report
out=HERE/'hdmi_dce_trial';out.mkdir(exist_ok=False)
script=out/'guard.tcl'
script.write_text('''init
halt
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Unexpected running OS"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU not parked"}
riscv set_enable_virt2phys off
set code [read_memory 0x80000000 32 2]
echo "PARKING_CODE $code"
if {[lindex $code 0]!=0x10500073 || [lindex $code 1]!=0xffdff06f} {error "Unknown ROM parking code"}
echo PARKING_CONFIRMED
shutdown
''')
devices=[d for d in Path('/sys/bus/usb/devices').iterdir()
         if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
assert len(devices)==1
device=devices[0]
assert (device/'idVendor').read_text().strip()=='0403' and (device/'idProduct').read_text().strip()=='6010'
busdev=':'.join((device/n).read_text().strip() for n in ['busnum','devnum'])
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (out/'guard.log').open('w') as log:
        subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
            stdout=log,stderr=log,timeout=30,check=True)
    assert 'PARKING_CONFIRMED' in (out/'guard.log').read_text()
    with (out/'program.log').open('w') as log:
        subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
            '-b','tangconsole','-m','--verbose','--freq','6000000',str(build/'impl/pnr/probe.fs')],
            stdout=log,stderr=log,timeout=120,check=True)
    status=check_program_status((out/'program.log').read_text())
result=dict(programmed=True,program_status=status,bitstream_sha256=sha(build/'impl/pnr/probe.fs'),
    timing_minima_ns=margins,visual_confirmation='pending',linux_running=False,
    cpu_present_in_probe=False,ddr_used=False,sd_written=False,flash_written=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
