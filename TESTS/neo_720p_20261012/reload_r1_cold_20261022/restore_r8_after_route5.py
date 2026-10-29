#!/usr/bin/env python3
"""Restore the previously visible R8 bars after the exact failed R5 trial.

R5 never reached CPU examination or framebuffer writes. Its prior live
parking guard, successful SRAM load, exact script and error log are required.
This is a narrow recovery, not permission to replace an arbitrary running OS.
"""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time

import probe_scan_observer as p

PRIOR = p.HERE / 'r9_route5_rgb_trial'
OUT = p.HERE / 'r8_restored_after_route5'
MARKER = PRIOR / 'restoration_consumed.json'
R5 = 'b85a1a41e22e1b9a0b24be45a5c18cdce9d84a996305238c4ceb933415a854ea'
R8 = '51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35'
SCRIPT = '253ab86a1e7ffea939223d42a2b28e413c6045a4e636fc4c1887296ddcee8708'


def preflight():
    r = json.loads((PRIOR / 'result.json').read_text())
    p.require(r['bitstream_sha256'] == R5 and r['fpga_reloaded'] and not r['trial_completed']
              and not r['linux_started'] and not r['sd_written'] and not r['flash_written']
              and not r['cpu_left_halted'], 'Not the unexamined R5 trial')
    p.require(r['script_sha256'] == p.sha(p.HERE / 'probe_route5_scan_reset.py') == SCRIPT,
              'Trial script drift')
    p.require(r['helpers_sha256'] == p.sha(Path(p.__file__)), 'Trial helper drift')
    p.require(p.check_program_status((PRIOR / 'program.log').read_text()) == r['program_status'],
              'Previous programming status changed')
    guard = (PRIOR / 'guard.log').read_text()
    snapshot = re.search(r'^SNAP_GUARD (.+)$', guard, re.M)
    p.require('CPU_HALTED' in guard and snapshot
              and [int(w, 0) for w in snapshot[1].split()] == [1, 0, 79, 0, 0, 0, 0, 0x53434e15],
              'No preceding live route2 parking/snapshot guard')
    log = (PRIOR / 'reset.log').read_text()
    p.require("DMI operation didn't complete" in log and 'CPU_HALTED' not in log
              and 'SNAP_START' not in log and not (PRIOR / 'rgb.tcl').exists(),
              'Failure was not confined to CPU examination')
    script = (PRIOR / 'reset.tcl').read_text()
    p.require(script.startswith(p.GUARD + p.SNAPSHOT) and not re.search(r'^\s*resume\b', script, re.M),
              'Unexpected post-program commands')
    p.require(not MARKER.exists(), 'Recovery already consumed')
    q, bit = p.check_fpga(p.ROOT / 'tang/impl/console_neo_n56r8_hdmi_sg4', R8)
    return q, bit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    q, bit = preflight()
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, bitstream_sha256=R8)))
        return 0
    OUT.mkdir(exist_ok=False)
    result = dict(passed=False, complete=False, bitstream_sha256=R8,
                  previous_bitstream_sha256=R5, cpu_left_halted=False,
                  linux_running=False, sd_written=False, flash_written=False,
                  qualification_status=q['status'], visual_confirmation='pending',
                  prior_cpu_unexamined=True, script_sha256=p.sha(Path(__file__)),
                  prior_sha256={str(f): p.sha(f) for f in PRIOR.iterdir() if f.is_file()})
    try:
        devices = [d for d in Path('/sys/bus/usb/devices').iterdir()
                   if (d / 'serial').exists() and (d / 'serial').read_text().strip() == '2025041420']
        p.require(len(devices) == 1, 'Neo programmer not uniquely identified')
        dev = devices[0]
        p.require((dev / 'idVendor').read_text().strip() == '0403'
                  and (dev / 'idProduct').read_text().strip() == '6010', 'Wrong programmer')
        busdev = ':'.join((dev / n).read_text().strip() for n in ('busnum', 'devnum'))
        result['programmer_busdev'] = busdev
        with (p.ROOT / 'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            preflight()
            with MARKER.open('x') as f:
                json.dump(dict(out=str(OUT), bitstream_sha256=R8, time=time.time()), f)
            with (OUT / 'program.log').open('x') as log:
                subprocess.run([str(Path.home() / '.local/bin/openFPGALoader'), '--busdev-num', busdev,
                                '-b', 'tangconsole', '-m', '--verbose', '--freq', '6000000', str(bit)],
                               stdout=log, stderr=log, timeout=120, check=True)
            result['program_status'] = p.check_program_status((OUT / 'program.log').read_text())
            script = OUT / 'after.tcl'
            script.write_text(p.GUARD + '''
sleep 100
echo "FALLBACK_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "FALLBACK_1 [read_memory 0xe9000000 32 32]"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback differs"}
echo R8_BARS_RESTORED
shutdown
''')
            with (OUT / 'after.log').open('x') as log:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(p.ROOT / 'tools/neo/ae350_espprog.cfg'),
                                '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                                '-f', str(script)], stdout=log, stderr=log, timeout=30, check=True)
            result['complete'] = 'R8_BARS_RESTORED' in (OUT / 'after.log').read_text()
            result['passed'] = result['complete']
    except Exception as e:
        result['error'] = str(e)
    finally:
        if (OUT / 'after.log').exists():
            result['cpu_left_halted'] = 'CPU_HALTED' in (OUT / 'after.log').read_text()
        result['scope'] = 'Restore internal bars only; framebuffer and full GPU remain unqualified'
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
