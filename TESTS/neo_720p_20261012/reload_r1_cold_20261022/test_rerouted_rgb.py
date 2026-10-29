#!/usr/bin/env python3
"""Load a reviewed R1 reroute from the currently confirmed CPU-free HDMI probe.

Neo only, SRAM only; no Linux or SD. Exact candidate SHA is mandatory and
check_fpga retains any FAIL timing status. This script is not qualification.
The current board must still contain this session's SG4 mini probe.
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

MINI_SHA = '29b8ca01df0786a5de37554160a7f2f61f035176d64f3359eb53be12ca2cba90'
BASE = 0x01700000

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--build', choices=['console_neo_n56r6_scan_reset', 'console_neo_n56r7_hdmi_pg0', 'console_neo_n56r8_hdmi_sg4'], required=True)
    p.add_argument('--diagnostic-bitstream', required=True)
    a = p.parse_args()
    SHA = a.diagnostic_bitstream
    BUILD = ROOT/'tang/impl'/a.build
    require(bool(re.fullmatch(r'[a-f0-9]{64}', SHA)), 'Exact SHA required')
    out = a.out.resolve()
    require(not any(c in str(out) for c in '{}\\\n\r'), 'Unsafe path')
    out.mkdir(exist_ok=False)
    report = dict(passed=False, cpu_left_halted=False, sd_written=False,
                  flash_written=False, bitstream_sha256=SHA,
                  qualification_status='not checked', hypothesis='compare R1 reroutes using same isolated RGB565 frame', previous_bitstream_sha256=MINI_SHA)
    try:
        anchor = HERE/'hdmi_sg4_trial/result.json'
        prior = json.loads(anchor.read_text())
        require(time.time()-anchor.stat().st_mtime < 7200, 'Mini-probe evidence expired')
        require(prior['programmed'] and prior['bitstream_sha256']==MINI_SHA
                and prior['visual_confirmation']=='user: Oui, la mire est visible'
                and not prior['cpu_present_in_probe'] and not prior['linux_running'],
                'Expected recently confirmed CPU-free probe')
        actual = {str(p.relative_to(BUILD/'source')): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (BUILD/'source').rglob('*') if p.is_file()}
        require(actual == json.loads((BUILD/'sources.json').read_text()), 'Candidate source drift')
        require(hashlib.sha256((BUILD/'console_neo.vg').read_bytes()).hexdigest() ==
                'c05e9b7a4bcafba8cd31e4b985b4ba37ace8ecbd0e4b999745ac60d7a5fb461d',
                'Expected exact R1 synthesis netlist')
        recorded = json.loads((BUILD/'qualification.json').read_text())
        require(recorded['bitstream_sha256'] == SHA, 'Candidate SHA differs')
        qualification, bitstream = check_fpga(BUILD, SHA if recorded['status']=='FAIL' else None)
        audit_name = {'console_neo_n56r6_scan_reset':'scan_reset_audit.json',
                      'console_neo_n56r7_hdmi_pg0':'hdmi_pg0_audit.json',
                      'console_neo_n56r8_hdmi_sg4':'hdmi_sg4_audit.json'}[a.build]
        structural = json.loads((BUILD/audit_name).read_text())
        require(structural['passed'] is True, 'Candidate structural audit failed')
        for filename, expected in structural['sha256'].items():
            path = Path(filename)
            if not path.is_absolute():
                path = ROOT/path
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                    'Stale structural audit input: '+filename)
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
            # A mini-probe anchor cannot authorize another reconfiguration once
            # this script has replaced it with a CPU-bearing candidate.
            with (HERE/'hdmi_sg4_anchor_consumed.json').open('x') as consumed:
                json.dump(dict(candidate=str(BUILD), bitstream_sha256=SHA,
                    out=str(out), time=time.time(), reason='One-shot transition from CPU-free probe'), consumed)
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
