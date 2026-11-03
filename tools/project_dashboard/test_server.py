"""Evidence endpoints must never become a repository-wide file browser."""
import json
from pathlib import Path
import tempfile
import unittest

import server


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'TESTS').mkdir()
        self.report = self.root/'TESTS/result.json'
        self.report.write_text(json.dumps({'passed': False, 'detail': '<script>bad()</script>'}))

    def test_only_declared_evidence_is_exposed(self):
        allowed = server.evidence_paths({'topics': [{'tests': [{'evidence': 'TESTS/result.json'}]}],
                                          'other': 'private.json'})
        self.assertEqual(allowed, {'TESTS/result.json'})
        result = server.read_evidence(self.root, 'TESTS/result.json', allowed)
        self.assertFalse(result['truncated'])
        self.assertIn('<script>', result['text'])  # JSON response; browser uses textContent.
        with self.assertRaises(ValueError):
            server.read_evidence(self.root, 'private.json', allowed)

    def test_traversal_absolute_and_binary_refused_even_if_declared(self):
        for path in ['../result.json', '/etc/passwd', 'TESTS/code.bin']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                server.read_evidence(self.root, path, {path})

    def test_symlink_to_outside_refused(self):
        (self.root/'TESTS/link.json').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            server.read_evidence(self.root, 'TESTS/link.json', {'TESTS/link.json'})

    def test_absent_and_large_proofs_are_explicit(self):
        with self.assertRaises(FileNotFoundError):
            server.read_evidence(self.root, 'TESTS/missing.json', {'TESTS/missing.json'})
        self.report.write_text('x' * (server.MAX_EVIDENCE + 100))
        result = server.read_evidence(self.root, 'TESTS/result.json', {'TESTS/result.json'})
        self.assertTrue(result['truncated'])
        self.assertIsNone(result['sha256'])  # Never call a suffix digest the whole-file hash.
        self.assertEqual(len(result['text']), server.MAX_EVIDENCE)

    def test_stream_ignores_only_clock_ticks_and_preserves_real_changes(self):
        base = {'generated_at': 'now', 'workers': [{'state': 'RUNNING', 'elapsed_s': 4, 'tool_calls': 2}]}
        later = {'generated_at': 'later', 'workers': [{'state': 'RUNNING', 'elapsed_s': 8, 'tool_calls': 2}]}
        self.assertEqual(server.snapshot_signature(base), server.snapshot_signature(later))
        later['workers'][0]['tool_calls'] = 3
        self.assertNotEqual(server.snapshot_signature(base), server.snapshot_signature(later))
        later['workers'][0].update(tool_calls=2, state='FAILED')
        self.assertNotEqual(server.snapshot_signature(base), server.snapshot_signature(later))


if __name__ == '__main__':
    unittest.main()
