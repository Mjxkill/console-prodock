"""Recovery must prove a stopped loader, never infer that a Linux shell is idle."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/neo'))
from load_linux import recovery_commands, stop_after_preflight, check_program_status,gpu_error_guard_before,gpu_error_guard_after,unexamined_preflight


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.result=dict(passed=False,sd_written=False,flash_written=False,
                         load_error='verify failed',recovery_state='parked_before_resume')
        (self.root/'console.log').write_text('')
        (self.root/'openocd.log').write_text('NEO_MEMORY_PREFLIGHT_BEGIN\nverify failed\n')

    def commands(self):
        (self.root/'result.json').write_text(json.dumps(self.result))
        return '\n'.join(recovery_commands(self.root))

    def test_legacy_ilm_failure_needs_live_privilege_pc_and_instruction(self):
        (self.root/'console.log').write_text('LINUX FAIL compact transport\n')
        self.result.pop('recovery_state')
        command=self.commands()
        for fragment in ('reg priv','0xa00001e8','0xa001'):
            self.assertIn(fragment,command)
        self.assertNotIn('resume ',command)

    def test_preflight_failure_needs_live_parking_code_and_pc(self):
        command=self.commands()
        for fragment in ('reg priv','0x80000000','0x80000004','0x10500073','0xffdff06f'):
            self.assertIn(fragment,command)
        self.assertNotIn('resume ',command)

    def test_resumed_or_unknown_state_is_rejected(self):
        for log in ('NEO_MEMORY_PREFLIGHT_BEGIN\nNEO_LAUNCH_BEGIN\n','unclassified error\n'):
            (self.root/'openocd.log').write_text(log)
            with self.assertRaises(RuntimeError):self.commands()

    def test_successful_boot_or_storage_write_is_rejected(self):
        for field in ('passed','sd_written','flash_written'):
            self.result[field]=True
            with self.assertRaises(RuntimeError):self.commands()
            self.result[field]=False

    def test_missing_error_or_recovery_marker_is_rejected(self):
        for field in ('load_error','recovery_state'):
            old=self.result.pop(field)
            with self.assertRaises(RuntimeError):self.commands()
            self.result[field]=old

    def test_completed_preflight_is_distinct_from_a_running_linux(self):
        self.result.update(passed=True, run_mode='preflight_only', cpu_left_halted=True,
                           load_error=None, recovery_state='parked_after_preflight')
        log='NEO_MEMORY_PREFLIGHT_BEGIN\nNEO_PREFLIGHT_ONLY_COMPLETE\n'
        (self.root/'openocd.log').write_text(log)
        self.assertIn('Boot parking fingerprint differs', self.commands())
        for tail in ('NEO_PAYLOAD_BEGIN\n', 'NEO_LAUNCH_BEGIN\n'):
            (self.root/'openocd.log').write_text(log+tail)
            with self.assertRaises(RuntimeError): self.commands()
        (self.root/'openocd.log').write_text(log)
        self.result['cpu_left_halted']=False
        with self.assertRaises(RuntimeError): self.commands()

    def test_preflight_script_cannot_resume_or_load_the_payload(self):
        script=('init\nhalt\necho NEO_MEMORY_PREFLIGHT_BEGIN\n'
                'echo NEO_GPU_PREFLIGHT_OK\necho NEO_PAYLOAD_BEGIN\n'
                'load_image {linux.bin} 0x10000000 bin\nresume 0xa000000c\nshutdown\n')
        stopped=stop_after_preflight(script)
        self.assertNotIn('linux.bin', stopped)
        self.assertNotIn('resume ', stopped)
        self.assertTrue(stopped.endswith('echo NEO_PREFLIGHT_ONLY_COMPLETE\nshutdown\n'))
        for bad in (script.replace('echo NEO_PAYLOAD_BEGIN\n', ''),
                    script.replace('halt\n', 'halt\nresume 0xa000000c\n')):
            with self.assertRaises(RuntimeError): stop_after_preflight(bad)

    def test_configuration_status_requires_done_without_error_flags(self):
        log='after program sram: displayReadReg 00042020\n'
        report=check_program_status(log)
        self.assertTrue(report['done'])
        self.assertFalse(report['sram_readback_verified'])
        for bit in (0,1,2,3,19,21):
            with self.assertRaises(RuntimeError):
                check_program_status(f'after program sram: displayReadReg {0x42020|(1<<bit):08x}\n')
        for bad in ('DONE\n',log+log,log+'FAIL\n',log.replace('00042020','00040020')):
            with self.assertRaises(RuntimeError):check_program_status(bad)

    def test_completed_but_rejected_command_fails_tcl_guard(self):
        # Execute the actual OpenOCD Tcl guard against mocked MMIO, including
        # nonzero prior counters and counter wrap, rather than inspecting text.
        setup='proc read_memory {address width count} {global memory; return [list $memory($address)]}\n'
        setup+='foreach address {0xe900100c 0xe900101c 0xe9001024 0xe9001034 0xe900104c} {set memory($address) 7}\n'
        before='\n'.join(gpu_error_guard_before())+'\n'
        after='\n'.join(gpu_error_guard_after())+'\n'
        for address in (None,'0xe900100c','0xe900101c','0xe9001024','0xe9001034','0xe900104c'):
            mutation='' if address is None else f'set memory({address}) 8\n'
            script=setup+'if {[catch {\n'+before+mutation+after+'} message]} {puts $message; exit 3}\nputs PASS\n'
            result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=False)
            self.assertEqual(result.returncode,0 if address is None else 3,result.stdout+result.stderr)
        script=setup+'set memory(0xe9001034) 4294967295\nif {[catch {\n'+before+'set memory(0xe9001034) 0\n'+after+'} message]} {puts $message; exit 3}\n'
        result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=False)
        self.assertEqual(result.returncode,3,result.stdout+result.stderr)

    def test_unexamined_recovery_needs_quiescence_programming_and_no_execution(self):
        self.result.update(run_mode='preflight_only',bitstream_sha256='a'*64)
        (self.root/'result.json').write_text(json.dumps(self.result))
        files={
            'recovery.log':'NEO_FAILED_LAUNCHER_CONFIRMED\n',
            'qualification_used.json':json.dumps(dict(bitstream_sha256='a'*64)),
            'load.tcl':'init\nhalt\necho NEO_PREFLIGHT_ONLY_COMPLETE\nshutdown\n',
            'openocd.log':'JTAG scan chain interrogation failed: all zeroes\nTarget not examined yet\n',
            'program.log':'after program sram: displayReadReg 00042020\n'}
        files['program_status.json']=json.dumps(check_program_status(files['program.log']))
        for name,value in files.items():(self.root/name).write_text(value)
        self.assertFalse(unexamined_preflight(self.root)['live_cpu_observation'])
        for name,changed in [('recovery.log',''),('program.log','missing\n'),
                             ('load.tcl',files['load.tcl']+'resume 0xa0000000\n'),
                             ('openocd.log',files['openocd.log']+'NEO_MEMORY_PREFLIGHT_BEGIN\n'),
                             ('qualification_used.json',json.dumps(dict(bitstream_sha256='b'*64)))]:
            with self.subTest(name=name):
                (self.root/name).write_text(changed)
                with self.assertRaises(RuntimeError):unexamined_preflight(self.root)
                (self.root/name).write_text(files[name])


if __name__=='__main__':unittest.main()
