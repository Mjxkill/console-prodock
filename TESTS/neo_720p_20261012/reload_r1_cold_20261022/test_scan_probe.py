#!/usr/bin/env python3
"""Offline checks of real snapshot decoding and Tcl capture guards; no board."""
import json
from pathlib import Path
import re
import subprocess

import probe_scan_observer as probe

HERE = Path(__file__).resolve().parent
OUT = HERE/'scan_probe_checks'

MOCK = r'''
set sequence 4294967295
set word_reads 0
proc echo {value} {puts $value}
proc sleep {ms} {}
proc write_memory {address width words} {
    global sequence mode
    if {$address!=0xe9006004 || $width!=32 || $words ne {1}} {error "Unexpected snapshot command"}
    if {$mode ne "stale_sequence"} {set sequence [expr {($sequence+1)&0xffffffff}]}
}
proc read_memory {address width count} {
    global sequence word_reads mode
    if {$address==0xe9006000} {
        if {$mode eq "wrong_id"} {return {0}}
        return {0x4e474442}
    }
    if {$address==0xe9006004} {
        if {$mode eq "changed_status" && $word_reads>=2} {return {2}}
        return {6}
    }
    if {$address==0xe900600c} {
        if {$mode eq "changed_sequence" && $word_reads>=2} {return [list [expr {$sequence+1}]]}
        return [list $sequence]
    }
    if {$address==0xe9006020} {
        incr word_reads
        set words {0x00610163 0x1700000 0x00a1004f 403284 403282 403280 0x5c0000 0x53434e01}
        if {$mode eq "changed_words" && $word_reads>=2} {lset words 3 403285}
        if {$mode eq "wrong_signature"} {lset words 7 0}
        return $words
    }
    if {$address==0xe9000000 && $count==32} {return [lrepeat 32 0]}
    error "Unexpected read address"
}
'''


def main():
    OUT.mkdir(exist_ok=False)
    cases = []
    actual = (HERE/'scan_observer_sim/run.log').read_text()
    m = re.search(r'BLOCKED queue=(\d+) arb=(\d+) returns=(\d+) flags=([0-9a-f]+) rgb=([0-9a-f]+)', actual)
    assert m
    words = [int(m[4], 16), 0, int(m[5], 16), int(m[1]), int(m[2]), int(m[3]), 0, 0x53434e01]
    decoded = probe.decode(words)
    assert decoded['rgb_state_name'] == 'PIPE'
    assert (decoded['line'], decoded['issued'], decoded['position'], decoded['last']) == (1, 4, 0, 79)
    assert decoded['flags']['line_pending']
    assert decoded['queued_not_accepted_by_arbiter'] == 2
    assert decoded['arbiter_accepted_not_returned'] == 2
    cases.append(dict(name='decode_recorded_rtl_stall', passed=True, decoded=decoded,
        limits='Line base, last address and handshake word are synthetic; only recorded fields are asserted.'))
    words[3:6] = [1, 0xffffffff, 0xfffffffd]
    wrapped = probe.decode(words)
    assert wrapped['queued_not_accepted_by_arbiter'] == wrapped['arbiter_accepted_not_returned'] == 2
    cases.append(dict(name='unsigned_counter_wrap', passed=True))
    order = ['reset_up', 'data_valid', 'arb_ready', 'arb_valid', 'scan_ready', 'scan_valid']
    for bit, name in enumerate(order):
        words[7] = 0x53434e00 | (1 << bit)
        flags = probe.decode(words)['handshake_flags']
        assert flags[name] and sum(flags.values()) == 1
    cases.append(dict(name='handshake_wire_order', passed=True))
    for bad in ([0]*7, [0]*9, [0]*7+[-1], [0]*7+[1 << 32]):
        try:
            probe.decode(bad)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Malformed snapshot accepted')
    cases.append(dict(name='malformed_snapshot_rejected', passed=True))
    expected_errors = {
        'stable': None,
        'changed_words': 'Snapshot changed while being read',
        'changed_sequence': 'Snapshot changed while being read',
        'changed_status': 'Snapshot changed while being read',
        'stale_sequence': 'Snapshot handshake failed',
        'wrong_signature': 'Scanout snapshot signature differs',
        'wrong_id': 'Observer ID missing',
    }
    for name, error in expected_errors.items():
        script = OUT/(name+'.tcl')
        script.write_text('set mode '+name+'\n'+MOCK+probe.SNAPSHOT+'''
if {[catch {snapshot TEST} reason]} {puts stderr $reason; exit 1}
exit 0
''')
        result = subprocess.run(['/usr/bin/tclsh', str(script)], capture_output=True, text=True, timeout=5)
        (OUT/(name+'.log')).write_text(result.stdout+result.stderr)
        if error is None:
            assert result.returncode == 0 and 'SNAP_TEST ' in result.stdout and 'SCAN_TEST ' in result.stdout
        else:
            assert result.returncode == 1 and error in result.stderr, (name, result)
        cases.append(dict(name='tcl_'+name, passed=True, returncode=result.returncode, expected_error=error))
    files = [Path(__file__), Path(probe.__file__), HERE/'scan_observer_sim/run.log']
    files += list(OUT.glob('*.tcl'))+list(OUT.glob('*.log'))
    record = dict(passed=True, cases=cases, hardware_access=False,
        sources_sha256={str(p): probe.sha(p) for p in files},
        limits='Host decoder and mocked OpenOCD reads only; no hardware, JTAG electrical test or routed timing validation.')
    (OUT/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(cases), hardware_access=False)))


if __name__ == '__main__':
    main()
