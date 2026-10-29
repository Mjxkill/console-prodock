#!/usr/bin/env python3
"""Exact r2 Tcl logging and rejection tests, entirely simulated."""
import subprocess
import unittest

import probe_n56r8_usb_ahb_r2 as probe
from test_usb_ahb import HARNESS


def run(corrupt_index=None):
    script = HARNESS + '\nset identifier 0x55544e41\nset status 0\n'
    if corrupt_index is not None:
        script += '''
rename write_memory write_memory_original
proc write_memory {address bits values} {
    global bank
    write_memory_original $address $bits $values
    if {[lindex $values 0]==1} {lset bank INDEX 0}
}
'''.replace('INDEX', str(corrupt_index))
    script += 'set rc [catch {\n' + probe.TRIAL + '\n} reason]\nputs "MOCK_RC $rc $reason"\n'
    return subprocess.run(['tclsh'], input=script, text=True, capture_output=True,
                          check=True, timeout=3).stdout


class TestR2(unittest.TestCase):
    def test_success_raw_reads_precede_validation_markers(self):
        text = run()
        for name in ('ARM', 'SAMPLE', 'DISARM'):
            self.assertLess(text.index('AHB_RAW_'+name+'_FIRST'), text.index('AHB_RAW_'+name+'_SECOND'))
            self.assertLess(text.index('AHB_RAW_'+name+'_SECOND'), text.index('AHB_BANK_'+name))
        self.assertTrue(probe.parse(text)['disarm_command_acknowledged'])

    def test_each_bad_header_word_logged_and_rejected_then_disarmed(self):
        for word in range(3):
            with self.subTest(word=word):
                text = run(word)
                for suffix in ('FIRST', 'SECOND'):
                    line = next(x for x in text.splitlines() if x.startswith('AHB_RAW_ARM_'+suffix+' '))
                    words = line.split()[1:]
                    self.assertEqual(len(words), 32)
                    self.assertEqual(int(words[word], 0), 0)
                self.assertIn('MOCK_RC 1 UTNA snapshot identity differs', text)
                self.assertIn('AHB_DISARM_CONFIRMED', text)
                self.assertNotIn('AHB_BANK_ARM', text)
                self.assertNotIn('AHB_TRIAL_COMPLETE', text)
                self.assertNotIn('MOCK_WRITE 0xe900200c 2', text)
                self.assertEqual(text.count('MOCK_WRITE'), 2)


if __name__ == '__main__':
    unittest.main()
