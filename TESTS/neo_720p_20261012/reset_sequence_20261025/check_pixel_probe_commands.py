#!/usr/bin/env python3
"""Offline Tcl execution of the first-command guards; no hardware tool invoked."""
import json
import subprocess
from load_pixel_probe import GUARD_R16, TARGET
from pixel_trace import HERE, sha

MOCK = r'''
set writes {}
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc sleep {args} {}
proc echo {s} {puts $s}
proc get_reg {args} {return [dict create pc 0x80000004 priv 3 satp 0]}
proc write_memory {addr width words} {
    if {$addr!=0xe9001010 || $width!=32 || [llength $words]!=1} {error "Unexpected write"}
    lappend ::writes [lindex $words 0]
    puts "MOCK_WRITE [lindex $words 0]"
}
proc read_memory {addr width count} {
    if {$width!=32} {error "Unexpected width"}
    switch -- [format %x $addr] {
        80000000 {return {0x10500073 0xffdff06f}}
        e9000000 {return {0x47505531}}
        e9000070 {return {0x02d00500}}
        e9000008 - e900000c {return {0}}
        e9000060 {return {0x1ff8f800}}
        e9005000 {return {0x4e474442}}
        e9005040 {return {0}}
        e9005018 {
            if {[llength $::writes]==0} {return {0 0}}
            if {$::mode eq "rejected"} {return {0x16000000 0}}
            return {0x16000000 0x16000000}
        }
        e9001000 {
            if {$count!=26} {error "Expected full GPU counters"}
            set gpu [lrepeat 26 0]
            lset gpu 0 0x424c5432
            if {$::mode eq "wrong_id"} {lset gpu 0 0}
            if {$::mode eq "stale"} {lset gpu 2 7}
            if {$::mode eq "pre_error"} {lset gpu 13 1}
            if {[llength $::writes]==8} {
                if {$::mode eq "timeout"} {lset gpu 1 1} else {lset gpu 2 1}
                if {$::mode eq "rejected"} {lset gpu 13 1}
            }
            return $gpu
        }
        default {error "Unexpected address $addr"}
    }
}
'''


def main():
    out=HERE/'pixel_probe_commands_check_01';out.mkdir(exist_ok=False)
    checks=[]
    for name, success, expected_writes in [('accepted',True,8),('rejected',True,8),
        ('wrong_id',False,0),('stale',False,0),('pre_error',False,0),('timeout',False,8)]:
        code='set mode '+name+'\n'+MOCK+GUARD_R16+TARGET
        code+='''if {[llength $writes]!=8} {error "Wrong packet size"}
set expected {0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0}
foreach a $writes b $expected {if {$a!=$b} {error "Wrong packet contents"}}
echo OFFLINE_COMMAND_CHECK_PASS
'''
        script=out/(name+'.tcl');script.write_text(code)
        r=subprocess.run(['/usr/bin/tclsh',str(script)],capture_output=True,text=True,timeout=5)
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        assert (r.returncode==0)==success, (name,r.stderr)
        assert r.stdout.count('MOCK_WRITE ')==expected_writes
        if success: assert 'OFFLINE_COMMAND_CHECK_PASS' in r.stdout
        checks.append(dict(name=name,passed=True,expected_success=success,writes=expected_writes))
    result=dict(passed=True,hardware_access=False,checks=checks,
        inputs={str(p):sha(p) for p in (HERE/'load_pixel_probe.py',HERE/'framebuffer_trial.py',Path(__file__))})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(checks),hardware_access=False)))


if __name__=='__main__':
    from pathlib import Path
    main()
