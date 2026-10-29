#!/usr/bin/env python3
"""Run the exact Tcl locally against a fake MMIO bank; never opens hardware."""
from pathlib import Path
import subprocess
import unittest

import probe_n56r8_usb_ahb as probe

HARNESS = r'''
set sequence 0
set armed 0
set bank [lrepeat 32 0]
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc reg {name} {
    if {$name eq "pc"} {return [list pc x 0x80000000]}
    if {$name eq "priv"} {return [list priv x 3]}
    return [list $name x 0]
}
proc read_memory {address bits count} {
    global identifier status sequence bank
    switch -- $address {
        0x80000000 {return {0x10500073 0xffdff06f}}
        0xe9000070 {return {0x02d00500}}
        0xe9000060 {return {0x1ff8f800}}
        0xe9000008 - 0xe900000c {return {0}}
        0xe9002000 {return [list $identifier $status $sequence]}
        0xe9002004 {return [list $status $sequence]}
        0xe9002040 {return $bank}
        default {error "unexpected read $address"}
    }
}
proc write_memory {address bits values} {
    global sequence bank armed
    if {$address ne "0xe900200c" || $bits!=32 || [llength $values]!=1} {error "unexpected write"}
    set value [lindex $values 0]
    puts "MOCK_WRITE $address $value"
    set sequence [expr {($sequence+1)&0xffffffff}]
    set bank [lrepeat 32 0]
    lset bank 0 0x55544e41
    lset bank 1 1
    lset bank 2 $value
    lset bank 3 60000000
    lset bank 31 [expr {$armed<<10}]
    if {$value==1} {set armed 1}
    if {$value==4} {set armed 0}
}
proc sleep {ms} {}
proc echo {message} {puts $message}
proc shutdown {} {}
'''


def run(code, identifier='0x55544e41', status=0):
    script = HARNESS + f'\nset identifier {identifier}\nset status {status}\n'
    script += 'set rc [catch {\n' + code + '\n} reason]\nputs "MOCK_RC $rc $reason"\n'
    return subprocess.run(['tclsh'], input=script, text=True, capture_output=True,
                          check=True, timeout=3).stdout


class TestAHB(unittest.TestCase):
    def test_read_only_even_with_missing_id(self):
        for identifier, status in [('0', 0), ('0x55544e41', 0), ('0x55544e41', 3)]:
            text = run(probe.READ_ONLY, identifier, status)
            self.assertIn('AHB_READ_ONLY_COMPLETE', text)
            self.assertNotIn('MOCK_WRITE', text)

    def test_refuses_absent_busy_rejected_before_writes(self):
        for identifier, status in [('0', 0), ('0x55544e41', 1), ('0x55544e41', 2)]:
            text = run(probe.TRIAL, identifier, status)
            self.assertIn('MOCK_RC 1', text)
            self.assertNotIn('MOCK_WRITE', text)

    def test_exact_trial_disarms_and_parses(self):
        text = run(probe.TRIAL)
        self.assertEqual([line for line in text.splitlines() if line.startswith('MOCK_WRITE')],
                         ['MOCK_WRITE 0xe900200c 1', 'MOCK_WRITE 0xe900200c 2',
                          'MOCK_WRITE 0xe900200c 4'])
        parsed = probe.parse(text)
        self.assertTrue(parsed['sample_armed'])
        self.assertEqual(parsed['sample']['ticks'], 60000000)
        self.assertEqual(parsed['target_address'], 0)
        with self.assertRaises(ValueError):
            probe.parse(text.replace('AHB_TRIAL_COMPLETE', 'MISSING'))


if __name__ == '__main__':
    unittest.main()
