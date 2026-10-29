"""Fault-injection tests for local queue bookkeeping; providers are never called."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dispatch_queue as queue


class QueueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.packet = self.project / 'packet.txt'
        self.packet.write_text('Useful bounded review task.\n')
        self.session = self.root / 'session'
        self.session.mkdir()
        (self.session / 'logs').mkdir()
        (self.session / 'runs').mkdir()
        self.runner = self.root / 'runner.py'
        self.runner.write_text('pass\n')
        self.launched = []

    def job(self, name, after=None, priority=0):
        return dict(task_id=name, run_id=name + '_run', model='beam', packet='packet.txt', packet_sha256=queue.file_sha(self.packet),
                    domain='test', task_type='implementation', difficulty='low', acceptance_criteria='Exact checks', priority=priority, after=after or [])

    def document(self, jobs):
        return dict(schema=1, max_active=2, jobs=jobs)

    def fake(self, codes=None, statuses=None, malformed=False):
        test = self
        codes, statuses = codes or {}, statuses or {}
        class Child:
            pid = 99999999
            def __init__(self, command, **kwargs):
                def argument(name):
                    return command[command.index('--' + name) + 1]
                self.name = argument('task-id')
                test.launched.append(self.name)
                output = Path(argument('out'))
                output.mkdir()  # Must not already exist: real runner owns this.
                record = dict(task_id=self.name, run_id=argument('run-id'), model=argument('model'),
                              input_sha256=queue.file_sha(test.packet), exit_code=codes.get(self.name, 0),
                              status=statuses.get(self.name, queue.SUCCESS), truncated=False)
                (output / 'status.json').write_text('{bad' if malformed else json.dumps(record))
                (output / 'metrics.json').write_text(json.dumps(record))
                (output / 'registry_import.json').write_text(json.dumps(dict(passed=True, metrics_sha256=queue.file_sha(output / 'metrics.json'))))
            def poll(self):
                return codes.get(self.name, 0)
        return Child

    def execute(self, document, fake=None):
        queue.validate_queue(document, self.project)
        with patch.object(queue.subprocess, 'Popen', fake or self.fake()), patch.object(queue.time, 'sleep'):
            return queue.run_session(document, self.project, self.session, self.runner, queue.file_sha(self.runner))

    def test_priority_and_fresh_outputs(self):
        result = self.execute(self.document([self.job('low'), self.job('high', priority=10)]))
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(self.launched, ['high', 'low'])

    def test_fail_blocks_success_dependency_but_terminal_runs(self):
        document = self.document([self.job('a'), self.job('b', [dict(task_id='a', condition='on_success')]), self.job('c', [dict(task_id='a', condition='on_terminal')])])
        result = self.execute(document, self.fake(codes={'a': 1}, statuses={'a': 'INCOMPLETE_LENGTH'}))
        states = queue.load_state(self.session)['jobs']
        self.assertEqual(states['a']['status'], 'INCOMPLETE_LENGTH')
        self.assertEqual(states['b']['status'], 'BLOCKED_DEPENDENCY')
        self.assertEqual(states['c']['status'], queue.SUCCESS)
        self.assertEqual(result['exit_code'], 1)

    def test_popen_and_log_failure_are_local(self):
        document = self.document([self.job('a'), self.job('b'), self.job('c')])
        (self.session / 'logs' / 'a_run.log').write_text('Existing evidence, retain')
        actual_fake = self.fake()
        def spawn(command, **kwargs):
            if command[command.index('--task-id') + 1] == 'b':
                raise OSError('injected exec failure')
            return actual_fake(command, **kwargs)
        result = self.execute(document, spawn)
        states = queue.load_state(self.session)['jobs']
        self.assertEqual([states[x]['status'] for x in ('a', 'b', 'c')], ['FAILED', 'FAILED', queue.SUCCESS])
        self.assertEqual(result['exit_code'], 1)

    def test_orphan_claim_not_relaunched(self):
        document = self.document([self.job('a'), self.job('b', [dict(task_id='a', condition='on_terminal')])])
        state = queue.reconcile(document, None, self.project, self.session)
        state['jobs']['a'].update(status='CLAIMED', claim=dict(pid=None, start_ticks=None))
        queue.atomic_json(self.session / 'state.json', state)
        result = self.execute(document)
        self.assertEqual(self.launched, [])
        self.assertEqual(queue.load_state(self.session)['jobs']['b']['status'], 'BLOCKED_UNRESOLVED')
        self.assertEqual(result['exit_code'], 1)

    def test_observed_terminal_can_be_reconciled_after_monitor_restart(self):
        document = self.document([self.job('a')])
        self.execute(document)
        state = queue.load_state(self.session)
        state['jobs']['a']['status'] = 'RUNNING'
        queue.atomic_json(self.session / 'state.json', state)
        self.launched.clear()
        result = self.execute(document)
        self.assertEqual(self.launched, [])
        self.assertEqual(result['exit_code'], 0)

    def test_malformed_status_not_eternal_running(self):
        result = self.execute(self.document([self.job('a')]), self.fake(malformed=True))
        self.assertEqual(queue.load_state(self.session)['jobs']['a']['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['exit_code'], 1)

    def test_restart_does_not_lose_registry_failure_or_pending_import(self):
        for case, expected in [('failed', 'FAILED'), ('pending', 'NEEDS_REVIEW'), ('wrong_sha', 'NEEDS_REVIEW')]:
            with self.subTest(case=case):
                document = self.document([self.job(case)])
                # Separate session, with a real successful local launch first.
                self.session = self.root / ('session_' + case)
                self.session.mkdir()
                (self.session / 'runs').mkdir()
                (self.session / 'logs').mkdir()
                self.execute(document)
                state = queue.load_state(self.session)
                state['jobs'][case]['status'] = 'RUNNING'
                queue.atomic_json(self.session / 'state.json', state)
                proof = self.session / 'runs' / (case + '_run') / 'registry_import.json'
                if case == 'pending':
                    proof.unlink()
                else:
                    row = json.loads(proof.read_text())
                    row['passed'] = False if case == 'failed' else True
                    if case == 'wrong_sha':
                        row['metrics_sha256'] = '0' * 64
                    proof.write_text(json.dumps(row))
                self.launched.clear()
                result = self.execute(document)
                self.assertEqual(self.launched, [])
                self.assertEqual(result['exit_code'], 1)
                self.assertEqual(queue.load_state(self.session)['jobs'][case]['status'], expected)

    def test_nonzero_cannot_adopt_success(self):
        result = self.execute(self.document([self.job('a')]), self.fake(codes={'a': 3}))
        self.assertEqual(queue.load_state(self.session)['jobs']['a']['status'], 'FAILED')
        self.assertEqual(result['exit_code'], 1)

    def test_cycle_duplicate_escape_symlink_and_missing(self):
        a, b = self.job('a'), self.job('b')
        a['after'] = [dict(task_id='b', condition='on_terminal')]
        b['after'] = [dict(task_id='a', condition='on_success')]
        bad = [self.document([a, b]), self.document([self.job('a'), self.job('a')])]
        for packet in ('../packet.txt', '/tmp/packet.txt', 'missing.txt', 'link.txt'):
            job = self.job('a')
            job['packet'] = packet
            bad.append(self.document([job]))
        (self.project / 'link.txt').symlink_to(self.packet)
        for document in bad:
            with self.assertRaises(ValueError):
                queue.validate_queue(document, self.project)

    def test_append_only_and_isolated_sessions(self):
        first = self.document([self.job('a')])
        self.execute(first)
        self.execute(self.document([self.job('a'), self.job('b')]))
        changed = self.document([self.job('a'), self.job('b')])
        changed['jobs'][0]['acceptance_criteria'] = 'Changed after execution'
        with self.assertRaises(ValueError):
            self.execute(changed)
        other = self.root / 'other_session'
        other.mkdir()
        (other / 'runs').mkdir()
        (other / 'logs').mkdir()
        self.session = other
        self.assertEqual(self.execute(first)['exit_code'], 0)

    def test_claude_requires_two_explicit_opt_ins(self):
        job = self.job('a')
        job.update(model='claude', claude_model='fable')
        document = self.document([job])
        for cli in (False, True):
            with self.assertRaises(ValueError):
                queue.validate_queue(document, self.project, cli)
        document['allow_claude'] = True
        queue.validate_queue(document, self.project, True)

    def test_interruption_preserves_claim_without_relaunch(self):
        class Pending:
            pid = 99999999
            def __init__(self, *args, **kwargs):
                pass
            def poll(self):
                return None
        document = self.document([self.job('a')])
        with patch.object(queue.subprocess, 'Popen', Pending), patch.object(queue.time, 'sleep', side_effect=InterruptedError), self.assertRaises(InterruptedError):
            queue.run_session(document, self.project, self.session, self.runner, queue.file_sha(self.runner))
        self.assertEqual(queue.load_state(self.session)['jobs']['a']['status'], 'NEEDS_REVIEW')
        self.execute(document)
        self.assertEqual(self.launched, [])


if __name__ == '__main__':
    unittest.main()
