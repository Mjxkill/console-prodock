"""Execution adapter checks; common dispatcher owns concurrent scheduling tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import agent_queue as q


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.spec = dict(schema=1, execution_mode='execution', task_id='task',
                         domain='workflow', task_type='implementation', acceptance_criteria='tests pass',
                         inputs=['owned.py'], owned=['owned.py'], tests=[['python3', 'test.py']])
        (self.project / 'task.json').write_text(json.dumps(self.spec))
        sha = hashlib.sha256((self.project / 'task.json').read_bytes()).hexdigest()
        self.job = dict(task_id='task', run_id='run', model='beam', execution_mode='execution',
                        domain='workflow', task_type='implementation', acceptance_criteria='tests pass',
                        packet='task.json', packet_sha256=sha)
        self.document = dict(schema=1, max_active=2, jobs=[self.job])

    def test_execution_validates(self):
        self.assertEqual(q.validate(self.document, self.project), self.document)

    def test_review_is_not_silently_execution(self):
        for mode in (None, 'review'):
            document = copy.deepcopy(self.document)
            if mode is None:
                del document['jobs'][0]['execution_mode']
            else:
                document['jobs'][0]['execution_mode'] = mode
            with self.assertRaises(ValueError):
                q.validate(document, self.project)

    def test_changed_spec_refused(self):
        (self.project / 'task.json').write_text('{}')
        with self.assertRaises(ValueError):
            q.validate(self.document, self.project)

    def test_duplicate_identity_refused_by_shared_engine(self):
        self.document['jobs'].append(copy.deepcopy(self.job))
        with self.assertRaises(ValueError):
            q.validate(self.document, self.project)

    def test_worker_command_mode_and_no_shell(self):
        argv = q.command(self.job, self.project, self.project/'out', Path('/safe/agent_runner.py'))
        self.assertEqual(argv[argv.index('--mode') + 1], 'execution')
        self.assertNotIn('--packet', argv)
        self.assertNotIn('--mode review', argv)
        self.assertEqual(argv[argv.index('--spec') + 1], str(self.project/'task.json'))

    def test_metadata_mismatch_refused(self):
        self.job['domain'] = 'other'
        with self.assertRaises(ValueError):
            q.validate(self.document, self.project)

    def test_difficulty_bound_and_queue_time_forwarded(self):
        argv = q.command(self.job, self.project, self.project/'out', Path('/safe/agent_runner.py'),
                         queued_at='2026-10-28T12:00:00Z')
        self.assertEqual(argv[argv.index('--queued-at') + 1], '2026-10-28T12:00:00Z')
        self.job['difficulty'] = 'high'
        with self.assertRaises(ValueError):
            q.validate(self.document, self.project)

    def test_orphan_claim_is_not_relaunched(self):
        state = q.common.reconcile(self.document, None, self.project, self.project/'session')
        state['jobs']['task']['status'] = 'CLAIMED'
        resumed = q.common.reconcile(self.document, state, self.project, self.project/'session')
        self.assertEqual(resumed['jobs']['task']['status'], 'NEEDS_REVIEW')


if __name__ == '__main__':
    unittest.main()
