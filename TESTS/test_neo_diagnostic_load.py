"""Diagnostic setup exceptions must never turn into ordinary qualifications."""
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_fpga, sha
import load_linux


class DiagnosticLoadTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.build=Path(tmp.name)
        pnr=self.build/'impl/pnr';pnr.mkdir(parents=True)
        self.bit=pnr/'console_neo.fs';self.bit.write_bytes(b'FPGA test fixture')
        self.report=pnr/'console_neo.tr';self.report.write_text('timing fixture')
        self.netlist=pnr/'console_neo.vo';self.netlist.write_text('routed netlist fixture')
        self.q=dict(status='FAIL',bitstream_sha256=sha(self.bit),timing_sha256=sha(self.report),
                    minimum_slack_ns=-.209,minimum_pulse_slack_ns=.1,
                    timing_checks_ns=dict(setup=-.209,hold=.1,recovery=.3,removal=.2),
                    violated_endpoints=dict(setup=1,hold=0),ddr_profile=dict(passed=True),
                    synthesis_audits=dict(copy=dict(passed=True),scanout=dict(passed=True),
                        gpu_owner_replication=dict(passed=True,netlist_sha256=sha(self.netlist))))
        self.save()

    def save(self):
        (self.build/'qualification.json').write_text(json.dumps(self.q))

    def test_default_rejects_failure_even_after_diagnostic(self):
        with self.assertRaises(RuntimeError):check_fpga(self.build)
        accepted,_=check_fpga(self.build,self.q['bitstream_sha256'])
        self.assertEqual(accepted['status'],'FAIL')
        with self.assertRaises(RuntimeError):check_fpga(self.build)
        self.assertEqual(json.loads((self.build/'qualification.json').read_text()),self.q)

    def test_normal_pass_unchanged(self):
        self.q['status']='PASS';self.save()
        self.assertEqual(check_fpga(self.build)[0]['status'],'PASS')

    def test_exact_hash_required(self):
        with self.assertRaises(RuntimeError):check_fpga(self.build,'0'*64)
        self.bit.write_bytes(b'changed')
        with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'])

    def test_changed_timing_rejected(self):
        self.report.write_text('changed')
        with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'])

    def test_replication_audit_cannot_be_missing_failed_or_stale(self):
        original=json.loads(json.dumps(self.q))
        for change in ('missing','failed','stale'):
            self.q=json.loads(json.dumps(original))
            if change=='missing':del self.q['synthesis_audits']['gpu_owner_replication']
            elif change=='failed':self.q['synthesis_audits']['gpu_owner_replication']['passed']=False
            else:self.q['synthesis_audits']['gpu_owner_replication']['netlist_sha256']='0'*64
            self.save()
            for args in ((),(self.q['bitstream_sha256'],),(self.q['bitstream_sha256'],True)):
                with self.assertRaises(RuntimeError):check_fpga(self.build,*args)

    def test_other_failures_not_waived(self):
        for name,change in [
            ('hold',lambda q:q['violated_endpoints'].update(hold=1)),
            ('pulse',lambda q:q.update(minimum_pulse_slack_ns=-.01)),
            ('recovery',lambda q:q['timing_checks_ns'].update(recovery=-.01)),
            ('removal',lambda q:q['timing_checks_ns'].update(removal=-.01)),
            ('missing_reset_checks',lambda q:q.pop('timing_checks_ns')),
            ('mapping',lambda q:q['synthesis_audits']['copy'].update(passed=False)),
            ('profile',lambda q:q['ddr_profile'].update(passed=False)),
            ('no_setup',lambda q:q['violated_endpoints'].update(setup=0)),
        ]:
            with self.subTest(name=name):
                original=json.loads(json.dumps(self.q))
                change(self.q);self.save()
                with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'])
                self.q=original;self.save()

    def test_routing_observation_is_explicit_and_never_changes_qualification(self):
        self.q['synthesis_audits']['gpu_reset_tree']=dict(passed=False,
            errors=['Reset 4 still uses a global routing resource'])
        self.q['synthesis_audits']['gpu_wide_controls']=dict(passed=False,
            errors=['gpu_debug_state[48] still uses LW','u_gpu/mrst[1] still uses LW'])
        self.save()
        for args in [(),(None,True),(self.q['bitstream_sha256'],)]:
            with self.assertRaises(RuntimeError):check_fpga(self.build,*args)
        q,_=check_fpga(self.build,self.q['bitstream_sha256'],True)
        self.assertEqual(q['status'],'FAIL')
        self.assertEqual(json.loads((self.build/'qualification.json').read_text()),self.q)

    def test_routing_observation_cannot_bypass_logic_or_reset_timing_failure(self):
        for audit,error in [('gpu_reset_tree','Missing reset driver 4'),
                            ('gpu_wide_controls','Wide-control catalog differs from the frozen netlist'),
                            ('gpu_wide_controls','u_accel/u_v1/new_control still uses LW'),
                            ('ddr_fifo','Reset 4 still uses a global routing resource')]:
            with self.subTest(audit=audit,error=error):
                self.q['synthesis_audits'][audit]=dict(passed=False,errors=[error]);self.save()
                with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'],True)
                del self.q['synthesis_audits'][audit]
        self.q['timing_checks_ns']['recovery']=-.01;self.save()
        with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'],True)

    def test_timing_closed_routing_observation(self):
        self.q.update(minimum_slack_ns=.1,violated_endpoints=dict(setup=0,hold=0))
        self.q['timing_checks_ns']['setup']=.2
        self.q['synthesis_audits']['gpu_wide_controls']=dict(passed=False,
            errors=['gpu_debug_state[48] still uses LW'])
        self.save()
        for args in [(),(self.q['bitstream_sha256'],),(None,True)]:
            with self.assertRaises(RuntimeError):check_fpga(self.build,*args)
        accepted,_=check_fpga(self.build,self.q['bitstream_sha256'],True)
        self.assertEqual(accepted,self.q)
        for field,change in [
            ('hold',lambda:self.q['timing_checks_ns'].update(hold=-.1)),
            ('mapping',lambda:self.q['synthesis_audits']['copy'].update(passed=False)),
        ]:
            original=json.loads(json.dumps(self.q))
            with self.subTest(field=field):
                change();self.save()
                with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'],True)
            self.q=original;self.save()
        del self.q['synthesis_audits']['gpu_wide_controls'];self.save()
        with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'],True)

    def test_concurrent_loader_rejected_before_any_board_operation(self):
        (self.build/'TESTS').mkdir()
        out=self.build/'blocked_load'
        with (self.build/'TESTS/neo_board.lock').open('a') as first:
            fcntl.flock(first,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(load_linux,'ROOT',self.build), patch.object(sys,'argv',
                    ['load_linux.py','--build',str(self.build),'--out',str(out),
                     '--already-programmed','--preflight-only']):
                with self.assertRaises(BlockingIOError):load_linux.main()
        self.assertFalse(out.exists())

    def test_recovery_experiment_is_bounded_explicit_and_does_not_qualify(self):
        self.q['timing_checks_ns']['recovery']=-.086;self.save()
        args=dict(diagnostic_bitstream=self.q['bitstream_sha256'],
                  diagnostic_recovery_min_ns=-.086,preflight_only=True)
        self.assertEqual(check_fpga(self.build,**args)[0],self.q)
        self.assertEqual(json.loads((self.build/'qualification.json').read_text()),self.q)
        for change in (dict(diagnostic_recovery_min_ns=None),dict(preflight_only=False),
                       dict(diagnostic_bitstream=None),dict(diagnostic_bitstream='0'*64),
                       dict(diagnostic_recovery_min_ns=-.085),dict(diagnostic_gpu_routing=True),
                       dict(diagnostic_recovery_min_ns=float('-inf')),
                       dict(diagnostic_recovery_min_ns=float('nan'))):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                check_fpga(self.build,**(args|change))
        with self.assertRaises(RuntimeError):check_fpga(self.build)
        with self.assertRaises(RuntimeError):check_fpga(self.build,self.q['bitstream_sha256'])

    def test_recovery_experiment_preserves_other_guards(self):
        self.q['timing_checks_ns']['recovery']=-.086
        original=json.loads(json.dumps(self.q))
        changes=[
            lambda q:q['timing_checks_ns'].update(hold=-.01),
            lambda q:q['timing_checks_ns'].update(removal=-.01),
            lambda q:q.update(minimum_pulse_slack_ns=-.01),
            lambda q:q['violated_endpoints'].update(hold=1),
            lambda q:q['synthesis_audits']['copy'].update(passed=False),
            lambda q:q['synthesis_audits']['gpu_owner_replication'].update(passed=False),
            lambda q:q['ddr_profile'].update(passed=False),
        ]
        for change in changes:
            self.q=json.loads(json.dumps(original));change(self.q);self.save()
            with self.assertRaises(RuntimeError):
                check_fpga(self.build,self.q['bitstream_sha256'],
                           diagnostic_recovery_min_ns=-.086,preflight_only=True)

    def test_recovery_cli_cannot_start_linux(self):
        with patch.object(sys,'argv',['load_linux.py','--build',str(self.build),
                '--out',str(self.build/'forbidden'),
                '--diagnostic-bitstream',self.q['bitstream_sha256'],
                '--diagnostic-recovery-min-ns','-0.086']), \
                patch.object(load_linux,'load') as load:
            with self.assertRaises(SystemExit):load_linux.main()
            load.assert_not_called()

    def reference_fixture(self):
        self.q.update(minimum_slack_ns=.129,minimum_pulse_slack_ns=1.06,
                      timing_checks_ns=dict(setup=.259,hold=.129,recovery=2.175,removal=.404),
                      violated_endpoints=dict(setup=0,hold=0),
                      clock_mhz=dict(ddr3_mem_clk=300.03,ddr3_sys_clk=75.002))
        self.q['ddr_profile']['variant']='neo-fifo-registers'
        self.q['synthesis_audits']['gpu_owner_replication'].update(
            passed=False,errors=['Pinned historical model observation'])
        proof=self.build/'previous';proof.mkdir()
        (proof/'result.json').write_text(json.dumps(dict(passed=True,
            run_mode='preflight_only',cpu_left_halted=True,
            bitstream_sha256=self.q['bitstream_sha256'])))
        for name in ('openocd.log','qualification_used.json','load.tcl'):
            (proof/name).write_text('historical evidence fixture')
        pin=dict(bitstream_sha256=self.q['bitstream_sha256'],
                 owner_audit_sha256=hashlib.sha256(json.dumps(
                     self.q['synthesis_audits']['gpu_owner_replication'],
                     sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                 proof_sha256={p.name:sha(p) for p in proof.iterdir()})
        self.save()
        return pin,dict(preflight_only=True,restore_ddr59_reference=proof)

    def test_reference_restore_keeps_failure_and_requires_explicit_stopped_mode(self):
        pin,args=self.reference_fixture()
        with patch.object(load_linux,'DDR59_REFERENCE',pin):
            self.assertEqual(check_fpga(self.build,**args)[0],self.q)
            self.assertEqual(json.loads((self.build/'qualification.json').read_text()),self.q)
            with self.assertRaises(RuntimeError):check_fpga(self.build)
            for change in (dict(preflight_only=False),dict(diagnostic_gpu_routing=True),
                           dict(diagnostic_recovery_min_ns=-.1),
                           dict(diagnostic_bitstream=self.q['bitstream_sha256'])):
                with self.subTest(change=change),self.assertRaises(RuntimeError):
                    check_fpga(self.build,**(args|change))

    def test_reference_restore_rejects_other_failures_or_changed_evidence(self):
        pin,args=self.reference_fixture()
        original=json.loads(json.dumps(self.q))
        changes=[
            lambda q:q.update(status='PASS'),
            lambda q:q['timing_checks_ns'].update(setup=-.1),
            lambda q:q['timing_checks_ns'].update(recovery=-.1),
            lambda q:q['timing_checks_ns'].update(hold=-.1),
            lambda q:q['timing_checks_ns'].update(removal=-.1),
            lambda q:q.update(minimum_pulse_slack_ns=-.1),
            lambda q:q['violated_endpoints'].update(setup=1),
            lambda q:q['synthesis_audits']['copy'].update(passed=False),
            lambda q:q['synthesis_audits']['gpu_owner_replication'].update(errors=['new failure']),
            lambda q:q['ddr_profile'].update(passed=False),
            lambda q:q['clock_mhz'].update(ddr3_mem_clk=400),
        ]
        with patch.object(load_linux,'DDR59_REFERENCE',pin):
            for change in changes:
                self.q=json.loads(json.dumps(original));change(self.q);self.save()
                with self.assertRaises(RuntimeError):check_fpga(self.build,**args)
            self.q=original;self.save()
            with patch.dict(pin,bitstream_sha256='0'*64):
                with self.assertRaises(RuntimeError):check_fpga(self.build,**args)
            for path in (self.bit,self.report,self.netlist,
                         *(args['restore_ddr59_reference']/name for name in pin['proof_sha256'])):
                saved=path.read_bytes();path.write_bytes(saved+b'changed')
                with self.subTest(path=path.name),self.assertRaises(RuntimeError):
                    check_fpga(self.build,**args)
                path.write_bytes(saved)

    def test_reference_restore_cli_cannot_start_linux(self):
        with patch.object(sys,'argv',['load_linux.py','--build',str(self.build),
                '--out',str(self.build/'forbidden'),'--restore-ddr59-reference',str(self.build)]), \
                patch.object(load_linux,'load') as load:
            with self.assertRaises(SystemExit):load_linux.main()
            load.assert_not_called()


if __name__=='__main__':unittest.main()
