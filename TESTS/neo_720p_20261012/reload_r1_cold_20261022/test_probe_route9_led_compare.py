#!/usr/bin/env python3
"""Local rejection/recovery tests; never opens USB/JTAG or modifies an anchor."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import probe_route9_led_compare as trial


def restored_log():
    return (trial.ANCHOR/'restored.log').read_text()


class TestLEDCompare(unittest.TestCase):
    def test_usb_exact_identity(self):
        neo = dict(path='/fake/neo', serial='2025041420', product='USB Debugger',
                   idVendor='0403', idProduct='6010', busnum='3', devnum='28')
        esp = dict(path='/fake/esp', product='Dual RS232-HS', idVendor='0403',
                   idProduct='6010', busnum='3', devnum='7')
        self.assertEqual(trial.select_devices([neo, esp])['programmer_busdev'], '3:28')
        variants = [[esp], [neo], [neo, esp, dict(esp, path='/fake/esp2')],
                    [dict(neo, serial='wrong'), esp], [dict(neo, idProduct='0000'), esp],
                    [neo, dict(esp, idVendor='0000')], [dict(neo, devnum='x'), esp]]
        for devices in variants:
            with self.subTest(devices=devices), self.assertRaises(RuntimeError):
                trial.select_devices(devices)

    def test_exact_preflight_and_no_hardware_check_only(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'never-created'
            argv = ['trial', '--bitstream-sha256', trial.BIT_SHA, '--out', str(out), '--check-only']
            with patch.object(sys, 'argv', argv), patch.object(trial, 'usb_identity', side_effect=AssertionError('USB accessed')), \
                 patch.object(trial.subprocess, 'Popen', side_effect=AssertionError('Child started')), \
                 contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(trial.main(), 0)
            data = json.loads(printed.getvalue())
            self.assertTrue(data['passed']); self.assertFalse(data['hardware_access'])
            self.assertEqual(data['qualification_status'], 'FAIL')
            self.assertEqual(data['led_proof']['r9']['function'], 'led_n = !ddr_init')
            self.assertFalse(out.exists())

    def test_preflight_rejects_identity_and_anchor_mutations(self):
        with self.assertRaises(RuntimeError): trial.preflight('0'*64)
        actual_record = trial.record
        variants = [
            (trial.BUILD/'qualification.json', 'status', 'PASS'),
            (trial.BUILD/'qualification.json', 'timing_checks_ns', dict(trial.TIMING, recovery=0)),
            (trial.ANCHOR/'result.json', 'fallback_restored', False),
            (trial.ANCHOR/'result.json', 'cpu_left_halted', False),
            (trial.ANCHOR/'result.json', 'fallback_frame_delta', 0),
            (trial.ANCHOR/'result.json', 'linux_started', True),
            (trial.ANCHOR/'visual_confirmation_fallback.json', 'bitstream_sha256', trial.BIT_SHA)]
        for target, key, value in variants:
            def changed(path):
                data = actual_record(path)
                if path == target: data[key] = value
                return data
            with self.subTest(target=target, key=key), patch.object(trial, 'record', side_effect=changed), self.assertRaises(RuntimeError):
                trial.preflight(trial.BIT_SHA)
        actual_sha = trial.p.sha
        for filename in trial.ANCHOR_SHA:
            def changed_sha(path):
                return '0'*64 if path == trial.ANCHOR/filename else actual_sha(path)
            with self.subTest(filename=filename), patch.object(trial.p, 'sha', side_effect=changed_sha), self.assertRaises(RuntimeError):
                trial.preflight(trial.BIT_SHA)
        with tempfile.TemporaryDirectory() as directory:
            consumed = Path(directory)/'consumed'; consumed.write_text('{}')
            with patch.object(trial, 'CONSUMED', consumed), self.assertRaises(RuntimeError):
                trial.preflight(trial.BIT_SHA)

    def test_observation_requires_new_token_and_explicit_user(self):
        token = 'new-token'
        answers = [dict(phase='r9', token='old', observer='user', value='on', note='LED'),
                   dict(phase='r9', token=token, observer='script', value='on', note='guess'),
                   dict(phase='r9', token=token, observer='user', value='off', note='User sees V13 off')]
        source = io.StringIO('\n'.join(map(json.dumps, answers))+'\n')
        with patch.object(trial.uuid, 'uuid4', return_value=type('UUID', (), dict(hex=token))()), \
             patch.object(sys, 'stdin', source), contextlib.redirect_stdout(io.StringIO()) as printed:
            answer = trial.led_answer('r9')
        self.assertEqual(answer['value'], 'off'); self.assertNotIn('ddr_init', answer)
        self.assertEqual(printed.getvalue().count('LED_OBSERVATION_REJECTED'), 2)
        with patch.object(sys, 'stdin', io.StringIO()), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(EOFError):
            trial.led_answer('r9')

    def test_sequence_and_failure_restoration(self):
        for failure in (None, 'program_r9', 'r9_answer', 'r9_dmi', 'restored_log', 'baseline_answer', 'final_answer'):
            events = []
            report = dict(passed=False, trial_completed=False, observations={}, cpu_left_halted=False)
            class FakeHardware:
                def observe(self, name, code):
                    events.append(name)
                    if name.startswith('guard'): return 'CPU_HALTED\nR8_PARKING_CONFIRMED\n'
                    if failure == 'restored_log': return restored_log().replace('0x1ff8f800', '0x0')
                    return restored_log()
                def program(self, name, path, digest):
                    events.append(name)
                    if failure == 'program_r9' and name == 'program_r9': raise RuntimeError('program status rejected')
                def dmi_after_led(self):
                    events.append('dmi')
                    if failure == 'r9_dmi': raise KeyboardInterrupt('interrupt DMI')
                    return dict(attempted=True, complete=False, timed_out=True)
            def answer(phase):
                events.append('answer_'+phase)
                if (phase, failure) in (('r9','r9_answer'), ('n56r8_before','baseline_answer'), ('n56r8_after','final_answer')):
                    raise EOFError('cancelled')
                return dict(value='on', note='explicit fixture user observation')
            with self.subTest(failure=failure):
                ok = trial.conduct(FakeHardware(), dict(bit=Path('r9'), fallback=Path('r8')), report,
                                   lambda:events.append('consume'), answer=answer)
                self.assertEqual(ok, failure is None)
                self.assertEqual(report['passed'], failure is None)
                if failure is None:
                    self.assertLess(events.index('answer_n56r8_before'), events.index('guard_after_led'))
                    self.assertLess(events.index('guard_after_led'), events.index('consume'))
                    self.assertLess(events.index('answer_r9'), events.index('dmi'))
                    self.assertLess(events.index('dmi'), events.index('restore_n56r8'))
                    self.assertTrue(report['r9_dmi']['timed_out'])
                    self.assertTrue(report['fallback_restored'])
                    self.assertTrue(report['protocol_passed']); self.assertTrue(report['baseline_led_valid'])
                elif failure == 'baseline_answer':
                    self.assertNotIn('consume', events); self.assertNotIn('program_r9', events)
                    self.assertNotIn('error_restore_n56r8', events)
                elif failure == 'restored_log':
                    self.assertIn('cleanup_error', report); self.assertFalse(report.get('fallback_restored', False))
                else:
                    self.assertTrue(report['fallback_restored']); self.assertTrue(report['cpu_left_halted'])
                if failure == 'r9_answer': self.assertNotIn('dmi', events)
                if failure == 'final_answer': self.assertNotIn('error_restore_n56r8', events)

    def test_invalid_baseline_or_stale_live_guard_never_loads_r9(self):
        for value, stale_guard in [('off',False), ('blinking',False), ('unclear',False), ('on',True)]:
            events=[]; report=dict(passed=False,trial_completed=False,observations={})
            class FakeHardware:
                def observe(self,name,code):
                    events.append(name)
                    return 'CHANGED\n' if name=='guard_after_led' and stale_guard else 'CPU_HALTED\nR8_PARKING_CONFIRMED\n'
                def program(self,*args): raise AssertionError('Must not program')
                def dmi_after_led(self): raise AssertionError('Must not probe R9')
            with self.subTest(value=value,stale_guard=stale_guard):
                ok=trial.conduct(FakeHardware(),{},report,lambda:events.append('consume'),
                    answer=lambda phase:dict(value=value,note='fixture user'))
                self.assertFalse(ok);self.assertFalse(report['protocol_passed'])
                self.assertFalse(report['baseline_led_valid']);self.assertFalse(report['led_comparison_conclusive'])
                self.assertIsNone(report['r9_ddr_init_from_led']);self.assertNotIn('consume',events)
                self.assertEqual(events,['guard','guard_after_led'])

    def test_final_baseline_and_r9_stability_gate_interpretation(self):
        for after in ('on','off','blinking','unclear'):
            for r9 in ('on','off','blinking','unclear'):
                report=dict(passed=False,trial_completed=False,observations={})
                class FakeHardware:
                    def observe(self,name,code):
                        return 'CPU_HALTED\nR8_PARKING_CONFIRMED\n' if name.startswith('guard') else restored_log()
                    def program(self,*args): pass
                    def dmi_after_led(self): return dict(complete=False,timed_out=True)
                answers={'n56r8_before':'on','r9':r9,'n56r8_after':after}
                with self.subTest(after=after,r9=r9):
                    self.assertTrue(trial.conduct(FakeHardware(),dict(bit=Path('r9'),fallback=Path('r8')),report,
                        lambda:None,answer=lambda phase:dict(value=answers[phase],note='fixture user')))
                    self.assertTrue(report['trial_completed']);self.assertTrue(report['protocol_passed'])
                    self.assertEqual(report['baseline_led_valid'],after=='on')
                    conclusive=after=='on' and r9 in ('on','off')
                    self.assertEqual(report['led_comparison_conclusive'],conclusive)
                    self.assertEqual(report['r9_ddr_init_from_led'],(1 if r9=='on' else 0) if conclusive else None)

    def test_dmi_timeout_is_data_and_commands_have_no_gpu_ddr_write(self):
        for code in (trial.GUARD, trial.RESTORED, trial.DMI_AFTER_LED):
            self.assertNotRegex(code, r'write_memory|load_image|resume|reg\s+\w+\s+(?:0x|\d)')
        self.assertNotIn('read_memory', trial.DMI_AFTER_LED)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory); (out/'r9_dmi.log').write_text('DMI timed out\n')
            hw = trial.Hardware(out, {})
            with patch.object(hw, 'observe', side_effect=subprocess.TimeoutExpired(['fake'], 30)):
                data = hw.dmi_after_led()
            self.assertTrue(data['timed_out']); self.assertFalse(data['complete']); self.assertFalse(data['cpu_halted'])
            (out/'r9_dmi.log').write_text('LED_DMI_CPU_HALTED\npc (/32): 0x80000000\nLED_DMI_COMPLETE\n')
            with patch.object(hw, 'observe', return_value='unused'):
                data = hw.dmi_after_led()
            self.assertTrue(data['complete']); self.assertEqual(data['pc'], 0x80000000)

    def test_fallback_requires_two_valid_progressing_samples(self):
        log = restored_log()
        self.assertEqual(trial.fallback_samples(log)['frame_delta'], 62)
        for wrong in (log.replace('FALLBACK_1', 'FALLBACK_0'), log.replace('0x1ff8f800', '0x0'),
                      log.replace('0xc5', '0x87'), log.replace('R8_BARS_RESTORED', 'MISSING')):
            with self.assertRaises(RuntimeError): trial.fallback_samples(wrong)

    def test_child_group_reaped_before_return(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); writes=path/'writes'
            writer='import time\nfrom pathlib import Path\np=Path('+repr(str(writes))+')\nwhile True:\n with p.open("ab") as f:f.write(b"x")\n time.sleep(.01)\n'
            launcher='import subprocess,sys,time\nsubprocess.Popen([sys.executable,"-c",'+repr(writer)+'])\ntime.sleep(.1)\n'
            with self.assertRaises(subprocess.TimeoutExpired):
                trial.run_child([sys.executable, '-c', launcher+'time.sleep(10)'], path/'child.log', .3)
            size=writes.stat().st_size; time.sleep(.1)
            self.assertEqual(writes.stat().st_size,size)


if __name__ == '__main__': unittest.main()
