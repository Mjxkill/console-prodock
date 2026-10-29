"""Audit counts and lifecycle/contract proof, independent of model answers."""
import json
from pathlib import Path
import tempfile
import unittest
from agent_evidence import audit
from agent_runner import test_counts


def tool(event, request, name='run_tests', **more):
    return dict(event=event, launch_id='launch', request_id=request, name=name, **more)


def finish(request, rc):
    return dict(event='test_finish', launch_id='launch', request_id=request,
                index=0, returncode=rc, timeout=False, output_limited=False)


class EvidenceTests(unittest.TestCase):
    def rows(self):
        pid = 2**30
        return [dict(event='launcher_start', launch_id='launch', pid=pid, start_ticks=1),
                dict(event='sandbox_start', launch_id='launch', pid=pid+1, start_ticks=1),
                tool('tool_start', 1), tool('tool_finish', 1, error=False), finish(1, 1),
                tool('tool_start', 2, 'write_file'), tool('tool_finish', 2, 'write_file', error=False),
                tool('tool_start', 3), tool('tool_finish', 3, error=False), finish(3, 0),
                dict(event='sandbox_exit', launch_id='launch', pid=pid+1, start_ticks=1),
                dict(event='launcher_exit', launch_id='launch', pid=pid, start_ticks=1)]

    def inspect(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'audit.jsonl'
            path.write_text('\n'.join(map(json.dumps, rows))+'\n')
            return audit(path)

    def test_same_session_failure_edit_pass(self):
        result = self.inspect(self.rows())
        self.assertEqual((result['agent_test_runs'], result['agent_test_failures']), (2, 1))
        self.assertTrue(result['failed_test_before_write'])
        self.assertTrue(result['passed_test_after_write'])
        self.assertTrue(result['all_recorded_processes_exited'])

    def test_absent_exit_not_hidden_by_pass(self):
        self.assertFalse(self.inspect(self.rows()[:-1])['all_recorded_processes_exited'])

    def test_without_agent_failure_no_demo_claim(self):
        rows = self.rows()
        rows[4]['returncode'] = 0
        self.assertFalse(self.inspect(rows)['failed_test_before_write'])

    def test_incomplete_test_result_remains_incomplete(self):
        rows = self.rows()
        del rows[4]
        self.assertFalse(self.inspect(rows)['test_audit_complete'])

    def test_supervisor_counts_are_separate(self):
        class Backend:
            tests = [dict(test_runs=1, test_failures=1), dict(test_runs=2, test_failures=0)]
        self.assertEqual(test_counts(Backend()), (3, 1))


if __name__ == '__main__':
    unittest.main()
