"""No hardware: exercise the decision boundary of unattended Neo validation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('neo_pending',ROOT/'tools/neo/validate_pending.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PendingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.build=self.base/'build';self.build.mkdir()
        self.recovery=self.base/'previous'
        self.out=self.base/'trial'
        self.digest='a'*64
        self.calls=[]
        self.qual_rc=0;self.qual_status='PASS';self.load_rc=1
        self.result={'passed':False,'bitstream_sha256':self.digest,
                     'sd_written':False,'flash_written':False,'load_error':'DDR mismatch'}

    def run_fake(self,args,log):
        self.calls.append(Path(args[1]).name)
        if self.calls[-1]=='check_neo_timing.py':
            (self.build/'qualification.json').write_text(json.dumps(
                {'status':self.qual_status,'bitstream_sha256':self.digest}))
            return self.qual_rc
        if self.calls[-1]=='load_linux.py':
            out=Path(args[args.index('--out')+1]);out.mkdir()
            if self.result is not None:
                (out/'result.json').write_text(json.dumps(self.result))
            self.assertEqual(Path(args[args.index('--recover-failed-load')+1]),self.recovery)
            return self.load_rc
        self.assertEqual(self.calls[-1],'probe_memory.py')
        self.assertIn('--gpu-cpu',args)
        return 1  # A failing memory diagnostic is still useful evidence.

    def attempt(self,known=True):
        return module.try_candidate(self.build,self.recovery,self.out,
                                    run=self.run_fake,can_recover=lambda _:known)

    def test_partial_report_waits(self):
        log=self.build/'build.log'
        self.assertEqual(module.build_state(self.build),'waiting')
        log.write_text('Bitstream generation completed\n')
        self.assertEqual(module.build_state(self.build),'waiting')
        log.write_text(f'Bitstream generation completed\nGenerate file "{self.build}/impl/pnr/console_neo.tr" completed\n')
        self.assertEqual(module.build_state(self.build),'ready')
        with log.open('a') as f:f.write('ERROR (PR0004): unrouted nets\n')
        self.assertEqual(module.build_state(self.build),'build_failed')

    def test_failed_qualification_never_loads(self):
        self.qual_rc=1
        entry,recovery=self.attempt()
        self.assertEqual(entry['state'],'qualification_failed')
        self.assertEqual(self.calls,['check_neo_timing.py'])
        self.assertEqual(recovery,self.recovery)

    def test_nonpassing_record_never_loads(self):
        self.qual_status='FAIL'
        self.assertEqual(self.attempt()[0]['state'],'qualification_failed')
        self.assertEqual(len(self.calls),1)

    def test_linux_success_stops_without_probe(self):
        self.result['passed']=True;self.load_rc=0
        entry,recovery=self.attempt()
        self.assertEqual(entry['state'],'linux_booted')
        self.assertEqual(recovery,self.out/'board')
        self.assertEqual(len(self.calls),2)

    def test_known_failure_is_probed_and_becomes_recovery(self):
        entry,recovery=self.attempt()
        self.assertEqual(entry['state'],'board_failed')
        self.assertEqual(recovery,self.out/'board')
        self.assertEqual(len(self.calls),3)

    def test_unknown_failure_stops(self):
        self.assertEqual(self.attempt(known=False)[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),2)

    def test_missing_result_stops(self):
        self.result=None
        self.assertEqual(self.attempt()[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),2)

    def test_wrong_bitstream_stops(self):
        self.result['bitstream_sha256']='b'*64
        self.assertEqual(self.attempt()[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),2)

    def test_unexpected_write_scope_stops(self):
        self.result['sd_written']=True
        self.assertEqual(self.attempt()[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),2)


class PreflightTests(unittest.TestCase):
    run_fake=PendingTests.run_fake

    def setUp(self):
        PendingTests.setUp(self)
        self.probe_passed=True
        self.probe_identity=self.digest
        self.gate_error=None
        self.diagnostic=True
        self.commands=[]

    def run_preflight(self,args,log):
        self.commands.append(args)
        if Path(args[1]).name=='load_linux.py':
            self.assertIn('--preflight-only',args)
            self.assertEqual(args[args.index('--jtag-frequency')+1],'6000000')
        if Path(args[1]).name!='probe_gpu_debug.py':
            return self.run_fake(args,log)
        self.calls.append('probe_gpu_debug.py')
        self.assertIn('--target-suite' if len(self.calls)==3 else '--control-suite',args)
        output=Path(args[args.index('--out')+1]);output.mkdir()
        (output/'result.json').write_text(json.dumps(dict(passed=self.probe_passed,
            bitstream_sha256=self.probe_identity,cpu_left_halted=True,sd_written=False,flash_written=False)))
        return 0 if self.probe_passed else 1

    def gate(self,build):
        if self.gate_error:raise RuntimeError(self.gate_error)
        return json.loads((build/'qualification.json').read_text()),self.digest if self.diagnostic else None

    def preflight(self,known=True):
        return module.try_preflight_candidate(self.build,self.recovery,self.out,
            run=self.run_preflight,can_recover=lambda _:known,gate=self.gate)

    def succeed(self):
        self.result.update(passed=True,run_mode='preflight_only',cpu_left_halted=True,load_error=None)
        self.load_rc=0

    def test_setup_diagnostic_stays_parked_and_checks_both_suites(self):
        self.qual_rc=1;self.qual_status='FAIL';self.succeed()
        entry,recovery=self.preflight()
        self.assertEqual(entry['state'],'preflight_passed')
        self.assertEqual(entry['qualification_status'],'FAIL')
        self.assertTrue(entry['cpu_left_halted'])
        self.assertEqual(recovery,self.out/'board')
        self.assertEqual(self.commands[1][-2:],['--diagnostic-bitstream',self.digest])
        self.assertEqual([x['name'] for x in entry['configuration_suites']],['target','control'])

    def test_qualified_build_also_does_not_boot_in_preflight_mode(self):
        self.diagnostic=False;self.succeed()
        self.assertEqual(self.preflight()[0]['state'],'preflight_passed')
        self.assertNotIn('--diagnostic-bitstream',self.commands[1])

    def test_loader_gate_refusal_prevents_all_hardware_calls(self):
        self.qual_rc=1;self.qual_status='FAIL';self.gate_error='Recovery slack is negative'
        self.assertEqual(self.preflight()[0]['state'],'qualification_failed')
        self.assertEqual(self.calls,['check_neo_timing.py'])

    def test_failed_preflight_does_not_run_configuration_suites(self):
        self.result['run_mode']='preflight_only'
        entry,recovery=self.preflight()
        self.assertEqual(entry['state'],'board_failed')
        self.assertEqual(recovery,self.out/'board')
        self.assertEqual(len(self.calls),2)

    def test_unproven_parking_stops_preflight_sequence(self):
        self.succeed()
        self.assertEqual(self.preflight(known=False)[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),2)

    def test_configuration_failure_stops_before_next_suite(self):
        self.succeed();self.probe_passed=False
        self.assertEqual(self.preflight()[0]['state'],'board_failed')
        self.assertEqual(len(self.calls),3)

    def test_probe_wrong_identity_stops_sequence(self):
        self.succeed();self.probe_identity='b'*64
        self.assertEqual(self.preflight()[0]['state'],'needs_inspection')
        self.assertEqual(len(self.calls),3)

    def test_stale_qualification_is_not_reused(self):
        (self.build/'qualification.json').write_text(json.dumps(
            dict(status='FAIL',bitstream_sha256=self.digest)))
        def crash(args,log):return 1
        entry,_=module.try_preflight_candidate(self.build,self.recovery,self.out,
            run=crash,gate=lambda _:self.fail('Stale gate must not execute'))
        self.assertEqual(entry['state'],'qualification_failed')


if __name__=='__main__':unittest.main()
