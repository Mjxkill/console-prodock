"""Local fixtures and owned child-process guards; never open a board port."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

import persistent as live
import policy as p

ANCHOR = dict(pid=5000, start_ticks=88888)


def proof():
    return dict(passed=True, hardware=True, manifest_sha256=p.MEASURE_SHA, restored_gm1=True, functional_passed=True,
                windows=[dict(window=dict(mode=k), measurement=dict(hardware=True, mode=k), display=dict(errors=0, uf=0, invalid=0, fault=0)) for k in [0, 1, 2, 3, 5, 4]],
                recovery=dict(identity=ANCHOR.copy(), save=dict(sha256=p.SAVE_SHA)))


def proc_fixture(program=p.PROGRAM, argv=p.ARGS, pid=5000, ticks=88888, state='S'):
    fields = [state] + ['0']*19
    fields[19] = str(ticks)
    body = ('\0'.join(['/tmp/'+program, *argv])+'\0').encode()
    raw = f'{pid} ({program}) {" ".join(fields)}\n'.encode()
    for at in range(0, len(body), 16):
        raw += f'{at:07o} '.encode() + b' '.join(f'{x:03o}'.encode() for x in body[at:at+16]) + b'\n'
    raw += f'{len(body):07o}\nlrwxrwxrwx 1 0 0 0 /proc/{pid}/exe -> /tmp/{program}\n'.encode()
    return raw


class Backend:
    def __init__(self, fail=None):
        self.fail = fail
        self.stopping = False
        self.recovered = 0
    def initial(self):
        if self.fail == 'initial':
            raise ValueError('identity invalid')
        return {}
    def stop_baseline(self):
        self.stopping = True
        if self.fail == 'stop':
            raise InterruptedError('during stop')
    def launch(self):
        if self.fail == 'launch':
            raise InterruptedError('during launch')
        return dict(pid=6000, start_ticks=99999)
    def progress(self, *args):
        if self.fail == 'gpu':
            raise ValueError('GPU errors')
        return dict(presents_delta=40)
    def saved(self, *args):
        if self.fail == 'save':
            raise ValueError('protected save changed')
        return dict(sha256=p.SAVE_SHA)
    def recover(self):
        self.recovered += 1
        return dict(identity=dict(pid=7000, start_ticks=111111), save=dict(sha256=p.SAVE_SHA))


class Tests(unittest.TestCase):
    def test_measurement_proof_uses_new_identity(self):
        self.assertEqual(p.measurement_proof(proof()), ANCHOR)
        self.assertNotEqual(ANCHOR['pid'], 3158)
        for key, value in [('passed', False), ('hardware', False), ('manifest_sha256', '0'*64), ('restored_gm1', False), ('windows', []), ('error', 'failure')]:
            row = proof()
            row[key] = value
            with self.assertRaises(ValueError):
                p.measurement_proof(row)

    def test_complete_argv_and_executable_link(self):
        raw = proc_fixture()
        self.assertEqual(p.parse_identity(raw, p.PROGRAM, p.ARGS), ANCHOR)
        for wrong in [proc_fixture(argv=['--showcase']), proc_fixture(state='Z'), raw.replace(b'/exe -> /tmp/luma3d-fm4a', b'/exe -> /tmp/foreign'), raw.replace(b'0000020', b'0000040', 1)]:
            with self.assertRaises(ValueError):
                p.parse_identity(wrong, p.PROGRAM, p.ARGS)

    def test_success_leaves_new_demo_without_restoration(self):
        backend = Backend()
        done = Mock()
        result = live.execute(backend, ANCHOR, done)
        self.assertTrue(result['passed'] and result['left_running'])
        self.assertEqual(backend.recovered, 0)
        self.assertEqual(result['argv'], p.ARGS)
        done.assert_called_once()

    def test_error_before_switch_never_starts_fallback(self):
        backend = Backend('initial')
        result = live.execute(backend, ANCHOR)
        self.assertFalse(result['passed'])
        self.assertTrue(result['no_game_switch_attempted'])
        self.assertEqual(backend.recovered, 0)

    def test_switch_failures_restore_and_remain_failures(self):
        for point in ['stop', 'launch', 'gpu', 'save']:
            with self.subTest(point=point):
                backend = Backend(point)
                result = live.execute(backend, ANCHOR)
                self.assertFalse(result['passed'] or result['left_running'])
                self.assertEqual(backend.recovered, 1)
                self.assertIn('recovery', result)

    def test_uncertain_recovery_never_becomes_success(self):
        backend = Backend('launch')
        backend.recover = Mock(side_effect=ValueError('Unpublished PID'))
        result = live.execute(backend, ANCHOR)
        self.assertTrue(result['manual_review_required'])
        self.assertFalse(result['passed'])

    def test_actual_recovery_refuses_unpublished_candidate(self):
        channel = types.SimpleNamespace(shell=True, launch_attempted=True, run=Mock())
        hw = live.Hardware(channel, ANCHOR)
        with patch.object(hw, 'identity', side_effect=ValueError('unpublished')):
            with self.assertRaises(ValueError):
                hw.recover()
        channel.run.assert_not_called()

    def test_actual_recovery_refuses_reused_candidate_pid(self):
        channel = types.SimpleNamespace(shell=True, launch_attempted=True, run=Mock())
        hw = live.Hardware(channel, ANCHOR)
        hw.candidate = dict(pid=6000, start_ticks=100)
        with patch.object(hw, 'identity', return_value=dict(pid=6000, start_ticks=101)), patch.object(hw, 'stop') as stop:
            with self.assertRaises(ValueError):
                hw.recover()
            stop.assert_not_called()
        channel.run.assert_not_called()

    def test_restore_only_after_candidate_stopped(self):
        channel = types.SimpleNamespace(shell=True, launch_attempted=True, run=Mock())
        hw = live.Hardware(channel, ANCHOR)
        candidate = dict(pid=6000, start_ticks=100)
        restored = dict(pid=7000, start_ticks=200)
        events = []
        with patch.object(hw, 'identity', side_effect=[candidate, None, restored, restored]), patch.object(hw, 'stop', side_effect=lambda *args: events.append('stop')), patch.object(hw, 'raw_verify', side_effect=lambda *args: events.append('crc')), patch.object(hw, 'progress', return_value={}), patch.object(hw, 'saved', return_value={'sha256': p.SAVE_SHA}):
            result = hw.recover()
        self.assertEqual(events, ['stop', 'crc'])
        self.assertEqual(result['identity'], restored)
        self.assertEqual(sum(label == 'restore_gm1' for label, cmd in (x.args for x in channel.run.call_args_list)), 1)

    def test_interruption_between_success_fields_and_handoff_is_not_success(self):
        backend = Backend()
        terminal = Mock(side_effect=[InterruptedError('late signal'), None])
        result = live.execute(backend, ANCHOR, terminal)
        self.assertFalse(result['passed'] or result['left_running'])
        self.assertEqual(backend.recovered, 1)

    def test_review_binds_measurement_and_restored_anchor(self):
        r=dict(host=p.HOST, port=p.PORT, manifest_sha256='a'*64, proof_sha256='b'*64, expected_identity=ANCHOR, fpga_sha256=p.FPGA_SHA, save_sha256=p.SAVE_SHA, reviewed_unix=100, same_g22r0_since_measurement=True, same_helper_and_elf_since_measurement=True, ordinary_shell_confirmed=True, no_other_console_session=True, root_authorized_leave_demo_running=True)
        p.review_check(r, 'a'*64, 'b'*64, ANCHOR, p.HOST, 110)
        for key,value in [('expected_identity', {'pid':3158,'start_ticks':27508908}), ('root_authorized_leave_demo_running',False), ('host','ax15'), ('proof_sha256','c'*64)]:
            bad=r.copy();bad[key]=value
            with self.assertRaises(ValueError):p.review_check(bad,'a'*64,'b'*64,ANCHOR,p.HOST,110)

    def test_owned_child_guard_checks_starttime_and_pidfile(self):
        with tempfile.TemporaryDirectory(prefix='festival-guard-') as directory:
            root=Path(directory);(root/'child.c').write_text('#include <unistd.h>\nint main(void){for(;;)pause();}\n')
            binary=root/p.PROGRAM
            subprocess.run(['gcc',str(root/'child.c'),'-o',str(binary)],check=True,capture_output=True)
            child=subprocess.Popen([str(binary),*p.ARGS],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            with tempfile.NamedTemporaryFile(prefix='festival-guard-',suffix='.pid',delete=False) as stream:
                pidfile=Path(stream.name)
            try:
                deadline=time.monotonic()+2
                while Path(f'/proc/{child.pid}/comm').read_text().strip()!=p.PROGRAM:
                    self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                fields=Path(f'/proc/{child.pid}/stat').read_text().split()
                identity=dict(pid=child.pid,start_ticks=int(fields[21]))
                pidfile.write_text(str(child.pid)+'\n')
                wrong=dict(identity,start_ticks=identity['start_ticks']+1)
                self.assertNotEqual(subprocess.run(['/bin/sh','-c',p.term_command(wrong,p.PROGRAM,str(pidfile))]).returncode,0)
                self.assertIsNone(child.poll())
                pidfile.write_text(str(child.pid+1)+'\n')
                self.assertNotEqual(subprocess.run(['/bin/sh','-c',p.term_command(identity,p.PROGRAM,str(pidfile))]).returncode,0)
                self.assertIsNone(child.poll())
                pidfile.write_text(str(child.pid)+'\n')
                subprocess.run(['/bin/sh','-c',p.term_command(identity,p.PROGRAM,str(pidfile))],check=True)
                self.assertEqual(child.wait(2),-15)
            finally:
                if child.poll() is None:child.terminate();child.wait(2)
                pidfile.unlink()


if __name__ == '__main__':
    unittest.main()
