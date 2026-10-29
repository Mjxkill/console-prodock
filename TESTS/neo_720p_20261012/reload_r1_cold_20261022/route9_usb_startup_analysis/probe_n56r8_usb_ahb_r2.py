#!/usr/bin/env python3
"""Exact N56r8 parked-CPU USB observer trial. Never programs or resumes CPU.

Only MMIO writes: E900200C = 1 (clear/arm), 2 (snapshot), 4 (disarm).
All command handshakes and the OpenOCD process are bounded. A failed or busy
observer is not reset. --check-only reads local files only.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import read_ep0_startup as ep0

HERE, ROOT = ep0.HERE, ep0.ROOT
ANCHOR = HERE.parent / 'r9_led_compare_trial'
ANCHOR_SHA = {
    'result.json': 'ecad218c26fa6bec6adc48ce4ea5b61f5f88b1780972897989f14cb456c6e188',
    'restored.log': '027d439db7cbbce9a66feb33d94c0b8813ce0cca18aa28015d75f75edad31033',
    'camera_observations.json': 'fa26c3b871189dc3e59909a67acd2571e2d31b453ce7a4a10d2e7b44ff77cca4'}
CFG = ROOT / 'tools/neo/ae350_espprog.cfg'
CFG_SHA = 'aa317f61c5093b8c230d96ba70b56cda65448f4b295a70b4e67cf09cd5ef9b67'
EP0_SHA = '40037e3a8901b9742f26c55e82ba0161264f08ad3fd6996f4ec7936220e412aa'

GUARD = '''init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected M-mode parking, no Linux"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU is not parked"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Not Neo geometry"}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback bars changed"}
echo N56R8_PARKING_BARS_CONFIRMED
'''
PROCEDURES = '''
proc info_usb {} {
    set words [read_memory 0xe9002000 32 3]
    echo "AHB_INFO $words"
    if {[lindex $words 0]!=0x55544e41} {error "UTNA ID absent"}
    if {[lindex $words 1]!=0} {error "UTNA busy or rejected; no reset permitted"}
    return [lindex $words 2]
}
proc command_usb {value name} {
    set before [info_usb]
    if {$value!=1 && $value!=2 && $value!=4} {error "Forbidden observer command"}
    echo "AHB_WRITE $value"
    write_memory 0xe900200c 32 [list $value]
    set completed 0
    for {set i 0} {$i<40} {incr i} {
        sleep 5
        set words [read_memory 0xe9002004 32 2]
        if {([lindex $words 0]&2)!=0} {error "UTNA command rejected"}
        if {[lindex $words 0]==0 && [lindex $words 1]==(($before+1)&0xffffffff)} {
            set completed 1
            break
        }
    }
    if {!$completed} {error "UTNA snapshot timeout"}
    set bank [read_memory 0xe9002040 32 32]
    echo "AHB_RAW_${name}_FIRST $bank"
    set repeated [read_memory 0xe9002040 32 32]
    echo "AHB_RAW_${name}_SECOND $repeated"
    if {$bank ne $repeated || [info_usb]!=(($before+1)&0xffffffff)} {error "UTNA snapshot changed"}
    if {[lindex $bank 0]!=0x55544e41 || [lindex $bank 1]!=1 || [lindex $bank 2]!=$value} {error "UTNA snapshot identity differs"}
    echo "AHB_BANK_$name [expr {($before+1)&0xffffffff}] $bank"
}
'''
TRIAL = GUARD + PROCEDURES + '''
info_usb
set armed_maybe 1
set failed [catch {
    command_usb 1 ARM
    sleep 1000
    command_usb 2 SAMPLE
} reason]
# Disarm only an idle, identified observer; never clear errors or force reset.
set cleanup_failed [catch {command_usb 4 DISARM} cleanup_reason]
if {$cleanup_failed} {echo "AHB_DISARM_FAILED $cleanup_reason"; error $cleanup_reason}
echo AHB_DISARM_CONFIRMED
if {$failed} {error $reason}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Bars changed after observer"}
echo AHB_TRIAL_COMPLETE
shutdown
'''
CLEANUP = GUARD + PROCEDURES + '''
command_usb 4 CLEANUP
echo AHB_DISARM_CONFIRMED
shutdown
'''
READ_ONLY = GUARD + '''
echo "AHB_READ_ONLY [read_memory 0xe9002000 32 3]"
echo AHB_READ_ONLY_COMPLETE
shutdown
'''


def preflight():
    ep0.require(ep0.sha(Path(ep0.__file__)) == EP0_SHA, 'EP0 proof helper changed')
    ep0.local_preflight()
    ep0.require(ep0.sha(CFG) == CFG_SHA, 'OpenOCD target changed')
    for name, digest in ANCHOR_SHA.items():
        ep0.require(ep0.sha(ANCHOR/name) == digest, 'Fresh fallback anchor changed: '+name)
    previous = json.loads((ANCHOR/'result.json').read_text())
    camera = json.loads((ANCHOR/'camera_observations.json').read_text())
    ep0.require(previous['fallback_restored'] and previous['cpu_left_halted'] and
        previous['fallback']['frame_delta'] > 0 and camera['fallback_restored'] and
        camera['combined_visual_comparison_complete'], 'Invalid restored N56r8 anchor')
    source = ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4/source/tang/rtl/usb/usb_idle_trace.v'
    manifest = json.loads((source.parents[4]/'sources.json').read_text())
    ep0.require(ep0.sha(source) == manifest['tang/rtl/usb/usb_idle_trace.v'], 'Observer RTL changed')
    assert re.findall(r'^\s*write_memory (0x[0-9a-f]+) 32 (.+)$', TRIAL, re.M) == [
        ('0xe900200c', '[list $value]')]
    for forbidden in ('resume', 'load_image', 'reset halt', 'reset run'):
        ep0.require(not re.search(r'^\s*'+forbidden+r'\b', TRIAL, re.M), 'Unsafe Tcl command')
    return dict(anchor_sha256=ANCHOR_SHA, cfg_sha256=CFG_SHA,
                observer_source_sha256=ep0.sha(source), bitstream_sha256=ep0.BUILD_SHA['n56r8'])


def identity(sysroot=Path('/sys/bus/usb/devices')):
    devices = []
    for path in sysroot.iterdir():
        item = dict(path=str(path))
        for name in ('idVendor', 'idProduct', 'product', 'serial', 'busnum', 'devnum'):
            try: item[name] = (path/name).read_text().strip()
            except OSError: pass
        devices.append(item)
    neo = [d for d in devices if d.get('serial') == '2025041420']
    esp = [d for d in devices if d.get('product') == 'Dual RS232-HS']
    ep0.require(len(neo) == len(esp) == 1, 'Neo/ESP identity missing or ambiguous')
    ep0.require(neo[0]['path'] != esp[0]['path'], 'Neo and ESP alias')
    for d in neo+esp:
        ep0.require(d.get('idVendor') == '0403' and d.get('idProduct') == '6010', 'Wrong Neo/ESP VID/PID')
    return dict(neo=neo[0], esp=esp[0])


def run(code, out, name):
    script = out/(name+'.tcl'); script.write_text(code)
    command = ['/usr/local/bin/openocd', '-f', str(CFG), '-c',
        'adapter speed 100; gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)]
    with (out/(name+'.log')).open('x') as log:
        child = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
        try:
            rc = child.wait(timeout=30)
        except BaseException:
            # Kill/reap only our session before any recovery OpenOCD process.
            handlers = {s:signal.signal(s, signal.SIG_IGN) for s in
                        (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
            try:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
            finally:
                for sig, handler in handlers.items(): signal.signal(sig, handler)
            raise
    ep0.require(rc == 0, f'OpenOCD exit {rc}; see {name}.log')
    return (out/(name+'.log')).read_text()


def parse(log):
    parsed = {}
    for name, seq, text in re.findall(r'^AHB_BANK_(ARM|SAMPLE|DISARM) (\d+) (.+)$', log, re.M):
        ep0.require(name not in parsed, 'Duplicate snapshot')
        words = [int(w, 0) for w in text.split()]
        ep0.require(len(words) == 32 and all(0 <= w <= 0xffffffff for w in words), 'Invalid snapshot length/word')
        ep0.require(words[:2] == [0x55544e41, 1] and words[2] == {'ARM':1,'SAMPLE':2,'DISARM':4}[name], 'Wrong snapshot identity')
        parsed[name] = dict(sequence=int(seq), words=words)
    ep0.require(set(parsed) == {'ARM', 'SAMPLE', 'DISARM'}, 'Missing observer snapshots')
    ep0.require(parsed['SAMPLE']['sequence'] == (parsed['ARM']['sequence']+1)&0xffffffff and
                parsed['DISARM']['sequence'] == (parsed['SAMPLE']['sequence']+1)&0xffffffff, 'Snapshot sequence mismatch')
    ep0.require(re.search(r'^AHB_DISARM_CONFIRMED\r?$', log, re.M) and
        re.search(r'^AHB_TRIAL_COMPLETE\r?$', log, re.M) and
        re.search(r'^N56R8_PARKING_BARS_CONFIRMED\r?$', log, re.M), 'Trial completion missing')
    words = parsed['SAMPLE']['words']
    fields = ('ticks','in2','in3','nak2','nak3','data2','data3','missing2','missing3',
        'bad_response','rx_error_cycles','bad_in_tokens','bus_resets','sofs','tx_stall_cycles',
        'last_token','last_response')
    return dict(snapshots=parsed, sample=dict(zip(fields, words[3:20])),
        sample_armed=bool(words[31] & 1024), target_address=words[31] & 127,
        disarm_command_acknowledged=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--read-only', action='store_true', help='First observation: ID/status/count only, no writes')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    checked = preflight()
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, **checked)))
        return 0
    if not args.out: parser.error('--out required')
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, scope='N56r8 passive USB AHB observer, parked CPU',
        script_sha256=ep0.sha(Path(__file__)), preflight=checked, functional_qualification=False,
        allowed_write_addresses=[] if args.read_only else ['0xe900200c'], read_only=args.read_only,
        cpu_resume_requested=False, gpu_commands_sent=False,
        ddr_written=False, sd_written=False, flash_written=False, bitstream_programmed=False)
    def interrupted(signum, frame): raise KeyboardInterrupt('Signal '+str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP): signal.signal(sig, interrupted)
    try:
        with ep0.LOCK.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            preflight()
            original = identity(); report['usb_identity'] = original
            try:
                log = run(READ_ONLY if args.read_only else TRIAL, args.out, 'trial')
                if args.read_only:
                    match = re.findall(r'^AHB_READ_ONLY (.+)$', log, re.M)
                    ep0.require(len(match) == 1 and re.search(r'^AHB_READ_ONLY_COMPLETE\r?$', log, re.M), 'Read-only observation incomplete')
                    words = [int(w, 0) for w in match[0].split()]
                    ep0.require(len(words) == 3 and all(0 <= w <= 0xffffffff for w in words), 'Invalid ID/status/count')
                    report.update(observer_header=words, observer_present=words[0] == 0x55544e41,
                                  observer_idle=words[1] == 0, passed=True, cpu_left_halted=True)
                else:
                    report.update(parse(log), passed=True, cpu_left_halted=True)
            except BaseException as error:
                report['error'] = repr(error)
                logpath = args.out/'trial.log'
                log = logpath.read_text() if logpath.exists() else ''
                # No retry if ID/status failed before any observer mutation.
                if not args.read_only and re.search(r'^AHB_WRITE [124]\r?$', log, re.M) and not re.search(r'^AHB_DISARM_CONFIRMED\r?$', log, re.M):
                    try:
                        ep0.require(identity() == original, 'USB probes changed before cleanup')
                        cleanup = run(CLEANUP, args.out, 'cleanup')
                        ep0.require(re.search(r'^AHB_DISARM_CONFIRMED\r?$', cleanup, re.M), 'Disarm unconfirmed')
                        report['cleanup_disarm_confirmed'] = True
                    except BaseException as cleanup_error:
                        report['cleanup_error'] = repr(cleanup_error)
            report['cpu_left_halted'] = bool(re.search(r'^CPU_HALTED\r?$',
                (args.out/'trial.log').read_text(), re.M))
    except BaseException as error:
        report.setdefault('error', repr(error))
    for path in args.out.iterdir():
        if path.is_file(): report.setdefault('evidence_sha256', {})[path.name] = ep0.sha(path)
    (args.out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
