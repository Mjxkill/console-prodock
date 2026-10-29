#!/usr/bin/env python3
"""Return the stopped RGB-only R1 diagnostic to its built-in HDMI bars."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_fpga,check_program_status

SHA='426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d'
prior=json.loads((HERE/'rgb_only/result.json').read_text())
assert prior['bitstream_sha256']==SHA and prior['cpu_left_halted'] and not prior['sd_written']
assert prior['program_status']['done'] and prior['fetch_frame_delta']==0
_,bit=check_fpga(ROOT/'tang/impl/console_neo_n56r1',SHA)
out=HERE/'fallback_bars';out.mkdir(exist_ok=False)
devices=[d for d in Path('/sys/bus/usb/devices').iterdir()
         if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
assert len(devices)==1
d=devices[0]
assert (d/'idVendor').read_text().strip()=='0403' and (d/'idProduct').read_text().strip()=='6010'
busdev=':'.join((d/n).read_text().strip() for n in ['busnum','devnum'])
def observe(name,extra):
    script=out/(name+'.tcl')
    script.write_text('''init
if {[nds.cpu curstate] ne "halted"} {halt}
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected bare-metal parking"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "Wrong parking PC"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x80000000 32 1] 0]!=0x10500073} {error "Wrong parking ROM"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong board geometry"}
''' + extra + '\necho CPU_LEFT_HALTED\nshutdown\n')
    with (out/(name+'.log')).open('w') as log:
        subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
            stdout=log,stderr=log,timeout=30,check=True)
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    observe('guard','''if {[lindex [read_memory 0xe9000008 32 1] 0]!=3 || [lindex [read_memory 0xe9000030 32 1] 0]!=0} {error "Not the isolated RGB trial"}
echo "BEFORE [read_memory 0xe9000000 32 32]"''')
    with (out/'program.log').open('w') as log:
        subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
            '-b','tangconsole','-m','--verbose','--freq','6000000',str(bit)],
            stdout=log,stderr=log,timeout=120,check=True)
    status=check_program_status((out/'program.log').read_text())
    observe('after','''sleep 100
echo "FALLBACK_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "FALLBACK_1 [read_memory 0xe9000000 32 32]"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback display does not match"}''')
(out/'result.json').write_text(json.dumps(dict(complete=True,bitstream_sha256=SHA,
    program_status=status,cpu_left_halted=True,linux_running=False,sd_written=False,flash_written=False,
    scope='Built-in HDMI bars only; no framebuffer or GPU validation'),indent=2)+'\n')
print((out/'after.log').read_text())
