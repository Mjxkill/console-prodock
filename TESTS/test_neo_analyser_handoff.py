"""An analyser-to-console handoff requires a completed, still-halted test."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/neo'))
import load_linux


class AnalyserHandoffTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        elf=b'known executable fixture'
        (self.root/'ddr_diag.elf').write_bytes(elf)
        digest=hashlib.sha256(elf).hexdigest()
        override=patch.object(load_linux,'ANALYSER_DDR_DIAGNOSTIC_SHA256',digest)
        override.start();self.addCleanup(override.stop)
        self.record=dict(passed=True,cpu_left_halted=True,flash_changed=False,sd_changed=False,
            bitstream_sha256=load_linux.ANALYSER_L31R8_SHA256,diagnostic_sha256=digest,
            checks=123,expected_checks=123,writes=45,expected_writes=45,
            status=2,errors=0,stages_completed=9)
        self.r=[0]*512
        self.r[:3]=[0x44445254,1,2]
        self.r[10:12]=[123,45]
        self.r[18:20]=[9,0x40000000]
        for i in range(9):self.r[35+i*4]=0x444f4e45
        self.save()

    def save(self):
        (self.root/'result.json').write_text(json.dumps(self.record))
        (self.root/'results.bin').write_bytes(struct.pack('<512I',*self.r))

    def commands(self):
        return '\n'.join(load_linux.analyser_diagnostic_commands(self.root))

    def test_modified_executable_or_incomplete_record_rejected(self):
        for key,value in [('passed',False),('cpu_left_halted',False),('sd_changed',True),
                          ('flash_changed',True),('bitstream_sha256','0'*64),
                          ('diagnostic_sha256','0'*64),('expected_checks',124)]:
            with self.subTest(key=key):
                old=self.record[key];self.record[key]=value;self.save()
                with self.assertRaises(RuntimeError):self.commands()
                self.record[key]=old;self.save()
        (self.root/'ddr_diag.elf').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):self.commands()

    def test_raw_failure_running_trap_or_missing_stage_rejected(self):
        for index,value in [(1,2),(2,1),(6,1),(8,1),(15,7),(18,8),(35,0),(10,124)]:
            with self.subTest(index=index):
                old=self.r[index];self.r[index]=value;self.save()
                with self.assertRaises(RuntimeError):self.commands()
                self.r[index]=old;self.save()
        (self.root/'results.bin').write_bytes(b'truncated')
        with self.assertRaises(RuntimeError):self.commands()

    def run_guard(self,state='halted',pc='0xa000086a',priv=3,satp=0,fail_verify=0):
        # Interpret the actual guard: unknown halt/resume/write commands would
        # fail, and a running CPU must be refused before memory verification.
        preamble=f'''
set state {state}
set pc {pc}
set priv {priv}
set satp {satp}
set verifies 0
set fail_verify {fail_verify}
proc init {{}} {{}}
proc poll {{}} {{}}
proc nds.cpu {{arg}} {{return $::state}}
proc reg {{name}} {{return [list $name value [set ::$name]]}}
proc riscv {{args}} {{}}
proc verify_image {{args}} {{
    incr ::verifies
    if {{$::verifies == $::fail_verify}} {{error "memory mismatch"}}
}}
proc echo {{message}} {{puts $message}}
proc shutdown {{}} {{}}
'''
        script=preamble+'\nset failed [catch {\n'+self.commands()+'''
} reason]
puts "GUARD_RESULT $failed $reason"
puts "VERIFIES $verifies"
'''
        return subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True).stdout

    def test_known_terminal_loop_verifies_code_and_results(self):
        for pc in ('0xa000086a','0xa000086c','0xa000086e'):
            output=self.run_guard(pc=pc)
            self.assertIn('NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED',output)
            self.assertIn('GUARD_RESULT 0',output)
            self.assertIn('VERIFIES 2',output)

    def test_running_os_unknown_pc_privilege_or_translation_rejected(self):
        for options in ({'state':'running'},{'state':'reset'},{'pc':'0xc0001000'},
                        {'priv':1},{'satp':'0x80001000'}):
            output=self.run_guard(**options)
            self.assertIn('GUARD_RESULT 1',output)
            self.assertIn('VERIFIES 0',output)
            self.assertNotIn('NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED',output)

    def test_changed_live_code_or_results_reject_handoff(self):
        for index in (1,2):
            output=self.run_guard(fail_verify=index)
            self.assertIn('GUARD_RESULT 1',output)
            self.assertNotIn('NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED',output)


if __name__=='__main__':unittest.main()
