"""Offline process and transcript tests; no request is sent to any provider."""
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import runner
from process_io import capture, CaptureLimit
from event_parser import parse_events


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'packet.txt').write_text('Prepared code fragment, no secrets.\n')
        self.out = self.root / 'run'

    def args(self, extra=()):
        return ['--mode', 'review', '--project', str(self.project), '--out', str(self.out), '--packet', 'packet.txt',
                '--model', 'beam', '--task-id', 'test_task', '--run-id', 'test_run', '--domain', 'test',
                '--task-type', 'implementation', '--acceptance-criteria', 'Compare exact output',
                '--registry', str(self.root / 'metrics.sqlite')] + list(extra)

    def fake_cli(self, body):
        path = self.root / 'fake-opencode'
        path.write_text('#!/usr/bin/env python3\n' + body)
        path.chmod(0o700)
        return path

    def test_prepare_has_no_network_or_credential_access(self):
        with patch.object(runner, 'credential', side_effect=AssertionError('must not read')), patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            self.assertEqual(runner.main(self.args(['--prepare-only'])), 0)
        self.assertFalse(self.out.exists())

    def test_secret_redacted_and_metrics_observed(self):
        cli = self.fake_cli("import json,os,sys\nsys.stdin.read()\nprint(json.dumps({'type':'text','part':{'text':'answer '+os.environ['OLLAMA_API_KEY']}}))\nprint(json.dumps({'type':'step_finish','part':{'id':'s','reason':'stop','tokens':{'input':10,'output':3}}}))\n")
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET_123'}):
            self.assertEqual(runner.main(self.args(['--opencode-bin', str(cli)])), 0)
        metrics = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(metrics['tokens']['input'], 10)
        self.assertIsNone(metrics['tokens']['reasoning'])
        self.assertIsNone(metrics['automatic_quality_score'])
        self.assertGreater(metrics['elapsed_seconds'], 0)
        self.assertEqual(metrics['quality_status'], 'pending_independent_evaluation')
        for path in self.out.iterdir():
            self.assertNotIn('TEST_SECRET_123', path.read_text())
        self.assertEqual(len((self.out / 'task_events.jsonl').read_text().splitlines()), 2)

    def test_length_and_nonzero_are_explicit_failures(self):
        cli = self.fake_cli("import json,sys\nsys.stdin.read()\nprint(json.dumps({'type':'text','part':{'text':'partial'}}))\nprint(json.dumps({'type':'step_finish','part':{'id':'s','reason':'length'}}))\n")
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET'}):
            self.assertEqual(runner.main(self.args(['--opencode-bin', str(cli)])), 1)
        metrics = json.loads((self.out / 'metrics.json').read_text())
        self.assertTrue(metrics['truncated'])
        self.assertEqual(metrics['status'], 'INCOMPLETE_LENGTH')

    def test_cli_missing_records_failed(self):
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET'}):
            self.assertEqual(runner.main(self.args(['--opencode-bin', '/nonexistent/opencode'])), 1)
        self.assertEqual(json.loads((self.out / 'metrics.json').read_text())['status'], 'FAILED')

    def test_timeout_records_failure_and_stops_only_owned_child(self):
        cli = self.fake_cli('import sys,time\nsys.stdin.read()\ntime.sleep(10)\n')
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET'}):
            self.assertEqual(runner.main(self.args(['--opencode-bin', str(cli), '--timeout', '1'])), 1)
        metrics = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(metrics['status'], 'TIMEOUT')
        self.assertTrue(all(value is None for value in metrics['tokens'].values()))

    def test_paths_duplicate_out_and_claude_opt_in(self):
        link = self.project / 'link.txt'
        link.symlink_to(self.project / 'packet.txt')
        for extra in (['--packet', 'link.txt'], ['--packet', '../escape.txt'], ['--model', 'claude'], ['--queued-at', '2999-01-01T00:00:00Z']):
            with self.assertRaises(ValueError):
                runner.validate(runner.arguments(self.args(extra)))
        self.out.mkdir()
        with self.assertRaises(ValueError):
            runner.validate(runner.arguments(self.args()))

    def test_credential_in_packet_never_persisted(self):
        (self.project / 'packet.txt').write_text('Do not publish TEST_SECRET')
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET'}):
            self.assertEqual(runner.main(self.args()), 1)
        self.assertFalse((self.out / 'prompt.txt').exists())
        for path in self.out.iterdir():
            self.assertNotIn('TEST_SECRET', path.read_text())

    def test_duplicate_finish_and_conflicting_length(self):
        finish = dict(type='step_finish', part=dict(id='s', reason='stop', tokens=dict(input=2, output=3)))
        raw = json.dumps(finish)
        result = parse_events(raw + '\n' + raw, 'ollama-cloud')
        self.assertEqual(result['tokens']['input'], 2)
        finish['part']['reason'] = 'length'
        result = parse_events(raw + '\n' + json.dumps(finish), 'ollama-cloud')
        self.assertTrue(result['truncated'])
        self.assertTrue(result['errors'])

    def test_partial_malformed_or_invalid_numeric_streams(self):
        for text in ('{"type":"text","part":{"text":"partial"}}', 'nonsense', '{"type":"step_finish","part":{"reason":"stop","tokens":{"input":-1}}}', '{"type":"step_finish","part":{"reason":"stop","tokens":{"input":1.5}}}'):
            self.assertTrue(parse_events(text, 'ollama-cloud')['errors'])
        self.assertTrue(parse_events('bad\n{"type":"result","result":"ok"}', 'claude-code')['errors'])

    def test_claude_missing_usage_remains_unknown(self):
        value = parse_events('{"type":"result","result":"ok"}', 'claude-code')
        self.assertTrue(all(item is None for item in value['tokens'].values()))
        self.assertIsNone(value['cost'])

    def test_partial_usage_never_looks_like_total(self):
        known = dict(type='step_finish', part=dict(id='known', reason='stop', tokens=dict(output=10), cost=1.0))
        missing = dict(type='step_finish', part=dict(id='missing', reason='stop', tokens={}))
        for first, second in ((known, missing), (missing, known)):
            result = parse_events(json.dumps(first) + '\n' + json.dumps(second), 'ollama-cloud')
            self.assertIsNone(result['tokens']['output'])
            self.assertIsNone(result['cost_observed'])
            self.assertEqual(len(result['observations']), 2)

    def test_missing_credential_is_a_registered_attempt(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runner.main(self.args()), 1)
        metrics = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(metrics['status'], 'FAILED')
        self.assertEqual(metrics['error_type'], 'ValueError')
        self.assertTrue(json.loads((self.out / 'registry_import.json').read_text())['passed'])

    def test_registry_failure_never_silently_succeeds(self):
        cli = self.fake_cli("import json,sys\nsys.stdin.read()\nprint(json.dumps({'type':'text','part':{'text':'done'}}))\nprint(json.dumps({'type':'step_finish','part':{'id':'s','reason':'stop'}}))\n")
        target = self.root / 'broken.sqlite'
        target.mkdir()
        with patch.dict(os.environ, {'OLLAMA_API_KEY': 'TEST_SECRET'}):
            self.assertEqual(runner.main(self.args(['--opencode-bin', str(cli), '--registry', str(target)])), 1)
        self.assertFalse(json.loads((self.out / 'registry_import.json').read_text())['passed'])
        self.assertTrue((self.out / 'metrics.json').is_file())

    def test_nonfinal_tool_call_cannot_be_completion(self):
        source = '{"type":"text","part":{"text":"partial"}}\n{"type":"step_finish","part":{"id":"a","reason":"tool-calls"}}'
        self.assertTrue(parse_events(source, 'ollama-cloud')['errors'])
        final = source + '\n{"type":"step_finish","part":{"id":"b","reason":"stop"}}'
        self.assertFalse(parse_events(final, 'ollama-cloud')['errors'])

    def test_capture_enforces_bound_during_read(self):
        child = subprocess.Popen([sys.executable, '-c', "import sys;sys.stdout.write('x'*100000)"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with self.assertRaises(CaptureLimit) as error:
                capture(child, b'', timeout=3, maximum=1024)
            self.assertLessEqual(len(error.exception.captured_stdout) + len(error.exception.captured_stderr), 1024)
        finally:
            child.kill()
            child.wait(3)
            child.stdout.close()
            child.stderr.close()


if __name__ == '__main__':
    unittest.main()
