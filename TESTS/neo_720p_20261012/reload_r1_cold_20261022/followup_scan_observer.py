#!/usr/bin/env python3
"""Repeat coherent R9-route2 observations, then select its internal bars.

No FPGA reload, no DDR/SD/flash write. Requires the completed stopped trial.
"""
import fcntl
import json
from pathlib import Path
import re
import subprocess

import probe_scan_observer as probe


def main():
    previous = probe.HERE/'r9_route2_rgb_observer/result.json'
    prior = json.loads(previous.read_text())
    assert prior['trial_completed'] and prior['cpu_left_halted']
    assert not prior['sd_written'] and not prior['flash_written']
    assert prior['bitstream_sha256'] == probe.ROUTE2SHA
    assert prior['script_sha256'] == probe.sha(Path(probe.__file__))
    assert probe.sha(probe.BUILD/'impl/pnr/console_neo.fs') == probe.ROUTE2SHA
    out = probe.HERE/'r9_route2_followup'
    out.mkdir(exist_ok=False)
    result = dict(complete=False, cpu_left_halted=False, bitstream_sha256=probe.ROUTE2SHA,
        sd_written=False, flash_written=False, ddr_written=False, fpga_reloaded=False,
        source_result_sha256=probe.sha(previous), script_sha256=probe.sha(Path(__file__)),
        probe_sha256=probe.sha(Path(probe.__file__)))
    code = probe.GUARD+'''
if {[lindex [read_memory 0xe9000008 32 1] 0]!=3 || [lindex [read_memory 0xe9000004 32 1] 0]!=0x01700000 || [lindex [read_memory 0xe900006c 32 1] 0]!=2560} {error "Not the stopped route2 RGB trial"}
'''+probe.SNAPSHOT+'''
for {set i 0} {$i<5} {incr i} {snapshot REPEAT_$i; sleep 200}
write_memory 0xe9000008 32 {0}
write_memory 0xe900000c 32 {1}
sleep 200
snapshot BARS0
sleep 1000
snapshot BARS1
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback bars not applied"}
echo R9_FOLLOWUP_COMPLETE
shutdown
'''
    (out/'observe.tcl').write_text(code)
    try:
        with (probe.ROOT/'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            with (out/'observe.log').open('w') as log:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(probe.ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                    '-f', str(out/'observe.tcl')], stdout=log, stderr=log, timeout=45, check=True)
        text = (out/'observe.log').read_text()
        result['snapshots'] = {n: probe.decode([int(w, 0) for w in words.split()])
            for n, words in re.findall(r'^SNAP_(\w+) (.+)$', text, re.M)}
        samples = {n: [int(w, 0) for w in words.split()]
            for n, words in re.findall(r'^SCAN_(\w+) (.+)$', text, re.M)}
        result['samples'] = samples
        first, last = samples['BARS0'], samples['BARS1']
        result['frame_delta'] = (last[6]-first[6]) & 0xffffffff
        result['underflow_delta'] = (last[7]-first[7]) & 0xffffffff
        result['internal_bars_selected'] = last[2] == 0 and last[3] == 0 and last[5] == 0 and last[24] == 0x1ff8f800
        result['complete'] = 'R9_FOLLOWUP_COMPLETE' in text and result['frame_delta'] > 0 and result['internal_bars_selected']
    except Exception as error:
        result['error'] = str(error)
    finally:
        if (out/'observe.log').exists():
            result['cpu_left_halted'] = 'CPU_HALTED' in (out/'observe.log').read_text()
        result['limits'] = 'Internal-bar register/checksum confirmation only; visual result and framebuffer functionality are separate.'
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('snapshots','samples')}, indent=2))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
