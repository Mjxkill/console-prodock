"""Unit failure injection only; synthetic events are not autonomy evidence."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request

from agent_core import execute
from agent_events import parse
from agent_provider import ProviderProxy


def event(kind, part_id, message='msg_1', **values):
    part = dict(id=part_id, messageID=message, sessionID='ses_test', **values)
    return dict(type=kind, sessionID='ses_test', part=part)


def events(suffix=''):
    return [event('step_start', 'start' + suffix, 'msg_' + suffix),
            event('tool_use', 'tool' + suffix, 'msg_' + suffix, callID='call' + suffix,
                  tool='taskbox_run_tests', state=dict(status='completed', output='test failed',
                                                     metadata={'exit': 1})),
            event('step_finish', 'end' + suffix, 'msg_' + suffix, reason='stop')]


def raw(items):
    return '\n'.join(map(json.dumps, items))


class ParserTests(unittest.TestCase):
    def test_task_not_equal_to_step_or_tool(self):
        result = parse(raw(events('1') + events('2')))
        self.assertTrue(result['complete'])
        self.assertEqual(result['model_steps_finished'], 2)
        self.assertEqual(result['tool_invocations_observed'], 2)
        self.assertIsNone(result['api_requests_observed'])

    def test_duplicate_events_do_not_inflate(self):
        stream = events('a')
        result = parse(raw(stream + stream))
        self.assertTrue(result['complete'])
        self.assertEqual(result['tool_invocations_observed'], 1)

    def test_conflicting_duplicate_refused(self):
        stream = events()
        changed = copy.deepcopy(stream[-1])
        changed['part']['reason'] = 'length'
        self.assertFalse(parse(raw(stream + [changed]))['complete'])

    def test_wrong_session_and_partial(self):
        self.assertFalse(parse(raw(events()), expected_session='ses_other')['complete'])
        self.assertFalse(parse(raw(events()[:-1]))['complete'])
        self.assertFalse(parse(raw(events()) + '\n{"type":')['complete'])

    def test_tool_failure_does_not_end_repair(self):
        result = parse(raw(events()))
        self.assertTrue(result['complete'])
        self.assertEqual(result['tools'][0]['exit_code'], 1)

    def test_unknown_terminal_or_unfinished(self):
        stream = events()
        stream[-1]['part']['reason'] = 'tool-calls'
        self.assertFalse(parse(raw(stream))['complete'])
        stream[-1]['part']['reason'] = 'stop'
        stream[1]['part']['state']['status'] = 'running'
        self.assertFalse(parse(raw(stream))['complete'])


class FakeBackend:
    """Fake transport for lifecycle tests. Never called a real sandbox/model."""
    def __init__(self, outcomes=(True,), initial=1, changes=True, policy=True):
        self.outcomes, self.initial, self.changes, self.policy = list(outcomes), initial, changes, policy
        self.sessions, self.closed = [], False
    def preflight(self, spec):
        return {'isolation_verified': True}
    def baseline(self):
        return dict(returncode=self.initial, policy_ok=True, infrastructure_ok=True)
    def run_agent(self, prompt, session_id, attempt):
        self.sessions.append(session_id)
        return dict(returncode=0, events=raw(events(str(attempt))), api_requests_observed=1)
    def validate(self):
        passed = self.outcomes.pop(0)
        return dict(passed=passed, policy_ok=self.policy, infrastructure_ok=True,
                    changed_files=['owned.py'] if self.changes else [], feedback='actual test failure')
    def close(self):
        self.closed = True


class LifecycleTests(unittest.TestCase):
    def run_case(self, backend, **options):
        with tempfile.TemporaryDirectory() as tmp:
            spec = dict(task_id='task', run_id='run', prompt='implement', **options)
            state = execute(backend, spec, Path(tmp) / 'out', parse)
            self.assertEqual(json.loads((Path(tmp) / 'out/state.json').read_text()), state)
            self.assertTrue(backend.closed)
            return state

    def test_exit0_with_failed_test_is_failure(self):
        result = self.run_case(FakeBackend((False,)))
        self.assertEqual(result['status'], 'TESTS_FAILED')

    def test_review_pending_requires_independent_test(self):
        result = self.run_case(FakeBackend())
        self.assertEqual(result['status'], 'REVIEW_PENDING')
        self.assertFalse(result['source_integrated'])

    def test_exact_session_continuation_is_bounded(self):
        backend = FakeBackend((False, False, True))
        result = self.run_case(backend, max_continuations=2)
        self.assertEqual(backend.sessions, [None, 'ses_test', 'ses_test'])
        self.assertEqual(result['api_requests_observed'], 3)
        self.assertEqual(result['status'], 'REVIEW_PENDING')

    def test_persistent_fail_stops_after_bound(self):
        backend = FakeBackend((False, False, False))
        result = self.run_case(backend, max_continuations=2)
        self.assertEqual(len(backend.sessions), 3)
        self.assertEqual(result['status'], 'TESTS_FAILED')

    def test_explicit_demo_evidence_required_only_when_requested(self):
        result = self.run_case(FakeBackend(), required_tool_evidence={'min_model_steps': 2})
        self.assertEqual(result['status'], 'INSUFFICIENT_EXECUTION_EVIDENCE')
        result = self.run_case(FakeBackend(initial=0, changes=False))
        self.assertEqual(result['status'], 'REVIEW_PENDING')
        result = self.run_case(FakeBackend(initial=0), require_initial_failure=True)
        self.assertEqual(result['status'], 'FAILED')

    def test_policy_failure_cannot_be_hidden_by_test_pass(self):
        result = self.run_case(FakeBackend(policy=False))
        self.assertEqual(result['status'], 'POLICY_FAILED')

    def test_interruption_closes_and_preserves(self):
        class Interrupted(FakeBackend):
            def run_agent(self, *args):
                raise InterruptedError()
        self.assertEqual(self.run_case(Interrupted())['status'], 'INTERRUPTED')

    def test_wrong_session_is_not_repaired_by_new_task(self):
        class WrongSession(FakeBackend):
            def run_agent(self, prompt, sid, attempt):
                value = super().run_agent(prompt, sid, attempt)
                if attempt:
                    value['events'] = value['events'].replace('ses_test', 'ses_alien')
                return value
        result = self.run_case(WrongSession((False, True)), max_continuations=1)
        self.assertEqual(result['status'], 'MODEL_INCOMPLETE')


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'text/event-stream'}


class GatewayTests(unittest.TestCase):
    def test_real_http_counts_and_secret_isolation(self):
        seen = []
        def fake_provider(request, timeout):
            seen.append((request.full_url, request.get_header('Authorization')))
            return Response(b'data: {"model":"observed-label"}\n\ndata: [DONE]\n\n')
        proxy = ProviderProxy('private-test-key', 'beam', max_requests=2, opener=fake_provider)
        url = proxy.start()
        try:
            def send(path='/chat/completions', model='beam', token=None):
                request = urllib.request.Request(url + path, data=json.dumps({'model': model}).encode(),
                    headers={'Authorization': 'Bearer ' + (proxy.token if token is None else token)})
                return urllib.request.urlopen(request, timeout=3).read()
            with self.assertRaises(urllib.error.HTTPError):
                send(token='wrong')
            with self.assertRaises(urllib.error.HTTPError):
                send(path='/models')
            with self.assertRaises(urllib.error.HTTPError):
                send(model='another-model')
            send(); send()
            with self.assertRaises(urllib.error.HTTPError):
                send()
            records = proxy.snapshot()
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]['response_models'], ['observed-label'])
            self.assertNotIn('private-test-key', json.dumps(records))
            self.assertTrue(all(endpoint == 'https://ollama.com/v1/chat/completions' for endpoint, _ in seen))
        finally:
            proxy.close()


if __name__ == '__main__':
    unittest.main()
