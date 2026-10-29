#!/usr/bin/env python3
"""R1 Neo-only SRAM reload and isolated RGB565 scanout, CPU left halted.

Requires this session's verified RAM-only Linux mount and sync replies.
No Linux/SD/flash writes; framebuffer is seeded and verified via CPU JTAG.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/neo'))
from load_linux import check_fpga, check_program_status

SHA = '426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d'
BUILD = ROOT / 'tang/impl/console_neo_n56r1'
BASE = 0x01700000

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    require(not any(c in str(out) for c in '{}\\\n\r'), 'Unsafe path')
    out.mkdir(exist_ok=False)
    report = dict(passed=False, cpu_left_halted=False, sd_written=False,
                  flash_written=False, bitstream_sha256=SHA,
                  qualification_status='FAIL', hypothesis='isolate RGB reader from layer composer')
    try:
        for name, command in [('mounts', 'mount'), ('sync', 'sync')]:
            record = HERE / name / 'result.json'
            r = json.loads(record.read_text())
            require(time.time() - record.stat().st_mtime < 1200, 'Stale Linux quiescence')
            require(r['executed'] and r['echo_verified'] and r['command'] == command,
                    'Unverified quiescence command')
            require('prodock# ' in r['output'], 'Command did not finish')
            if name == 'mounts':
                require(not re.search(r'^/dev/|\stype (?:ext[234]|vfat|f2fs)\b', r['output'], re.M),
                        'Block filesystem still mounted')
                require('rootfs on / type rootfs' in r['output'], 'Expected RAM rootfs')
        qualification, bitstream = check_fpga(BUILD, SHA)
        report['qualification_status'] = qualification['status']
        devices = [d for d in Path('/sys/bus/usb/devices').iterdir()
                   if (d / 'serial').exists() and (d / 'serial').read_text().strip() == '2025041420']
        require(len(devices) == 1, 'Neo programmer not unique')
        device = devices[0]
        require((device / 'idVendor').read_text().strip() == '0403'
                and (device / 'idProduct').read_text().strip() == '6010', 'Wrong programmer')
        busdev = ':'.join((device / n).read_text().strip() for n in ['busnum', 'devnum'])
        report['programmer_busdev'] = busdev
        colors = [0xffff, 0xffe0, 0x07ff, 0x07e0, 0xf81f, 0xf800, 0x001f, 0x4208]
        pixels = [0xffff if x < 8 or x >= 1272 or y < 8 or y >= 712 else
                  0xf800 if 540 <= x < 740 and 300 <= y < 420 else colors[x // 160]
                  for y in range(720) for x in range(1280)]
        frame = struct.pack('<921600H', *pixels)
        (out / 'framebuffer.bin').write_bytes(frame)
        report['framebuffer_sha256'] = hashlib.sha256(frame).hexdigest()
        report['expected_fetch_sum'] = sum(struct.unpack('<460800I', frame)) & 0xffffffff
        def openocd(name, code, timeout=90):
            script = out / (name + '.tcl')
            script.write_text(code)
            with (out / (name + '.log')).open('w') as log:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                                '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                                '-f', str(script)], stdout=log, stderr=subprocess.STDOUT,
                               timeout=timeout, check=True)
            return (out / (name + '.log')).read_text()
        with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            openocd('halt_linux', '''init
halt
set failed [catch {
    if {[lindex [reg satp] 2]==0} {error "Expected Linux"}
    riscv set_enable_virt2phys off
    if {[lindex [read_memory 0x08192802 16 1] 0]!=0x0073 || [lindex [read_memory 0x08192804 16 1] 0]!=0x1050 || [lindex [read_memory 0x0947d028 32 1] 0]!=3} {error "Wrong Linux fingerprint"}
    if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong board geometry"}
    echo "QUIESCED_LINUX_PC [reg pc]"
} reason]
if {$failed} {resume; error $reason}
echo LINUX_LEFT_HALTED
shutdown
''')
            report['cpu_left_halted'] = True
            with (out / 'program.log').open('w') as log:
                subprocess.run([str(Path.home() / '.local/bin/openFPGALoader'), '--busdev-num', busdev,
                                '-b', 'tangconsole', '-m', '--verbose', '--freq', '6000000', str(bitstream)],
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
            report['program_status'] = check_program_status((out / 'program.log').read_text())
            report['cpu_left_halted'] = False
            code = '''riscv expose_csrs 1994,1996,2000
init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Unexpected CPU after reload"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU not parked"}
if {[lindex [read_memory 0x80000000 32 2] 0]!=0x10500073} {error "Parking ROM differs"}
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong geometry"}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
echo "SCAN_DISABLED [read_memory 0xe9000000 32 32]"
'''
            code += f'load_image {{{out / "framebuffer.bin"}}} {BASE:#x} bin\n'
            code += f'verify_image {{{out / "framebuffer.bin"}}} {BASE:#x} bin\n'
            code += f'write_memory 0xe9000004 32 {{{BASE:#x}}}\n'
            code += '''write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 100
echo "SCAN_RGB0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "SCAN_RGB1 [read_memory 0xe9000000 32 32]"
echo SCANOUT_TRIAL_COMPLETE
shutdown
'''
            try:
                log = openocd('rgb', code)
            finally:
                report['cpu_left_halted'] = (out / 'rgb.log').exists() and 'CPU_HALTED' in (out / 'rgb.log').read_text()
            samples = {name: [int(w, 0) for w in words.split()] for name, words in
                       re.findall(r'^SCAN_(DISABLED|RGB0|RGB1) (.+)$', log, re.M)}
            report['samples'] = samples
            first, last = samples['RGB0'], samples['RGB1']
            report['frame_delta'] = (last[6] - first[6]) & 0xffffffff
            report['fetch_frame_delta'] = (last[9] - first[9]) & 0xffffffff
            report['underflow_delta'] = (last[7] - first[7]) & 0xffffffff
            report['passed'] = (len(last) == 32 and last[3] == 0 and last[5] == 1
                                and report['frame_delta'] > 0 and report['fetch_frame_delta'] > 0
                                and report['underflow_delta'] == 0
                                and last[8] == report['expected_fetch_sum'])
    except Exception as error:
        report['error'] = str(error)
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
