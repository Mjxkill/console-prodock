"""Local, simulated filesystem tests; no model, hardware or network access."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import check_code_size as c


class CodeSizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='code-size-')
        self.root = Path(self.tmp.name)
        self.manifest = self.root / 'manifest.json'
        (self.root / 'src').mkdir()
        (self.root / 'src/a.c').write_text('int x;\n')

    def tearDown(self):
        self.tmp.cleanup()

    def manifest_for(self, *entries):
        spec = {'version': 1, 'files': list(entries) or [{'path': 'src/a.c', 'ownership': 'project'}]}
        self.manifest.write_text(json.dumps(spec))
        return self.manifest

    def check(self, *entries):
        return c.audit(self.root, self.manifest_for(*entries))

    def test_boundary_and_generated(self):
        for lines in (0, 1, 999, 1000, 1001):
            with self.subTest(lines=lines):
                data = b'x\n' * lines
                (self.root / 'src/a.c').write_bytes(data)
                r = self.check({'path': 'src/a.c', 'ownership': 'project', 'generated': True})
                self.assertEqual(r['passed'], lines <= 1000)
                self.assertEqual(r['files'][0]['lines'], lines)
                self.assertEqual(r['files'][0]['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(len(r['violations']), int(lines > 1000))
                self.assertFalse(r['exemptions'])

    def test_physical_newlines(self):
        for data, count in [(b'', 0), (b'x', 1), (b'x\n', 1), (b'\r\n', 1),
                            (b'a\rb\r', 2), (b'a\r\nb\nc', 3),
                            (b'a'*65535+b'\r\nb', 2), (b'\n'*1000+b'x', 1001)]:
            with self.subTest(data_bytes=len(data)):
                p = self.root / 'src/a.c'; p.write_bytes(data)
                self.assertEqual(c.read_measure(p)['lines'], count)

    def test_visible_exemptions(self):
        (self.root / 'src/a.c').write_bytes(b'x\n'*1001)
        for owner in ('vendor', 'archive'):
            with self.subTest(owner=owner):
                r = self.check({'path': 'src/a.c', 'ownership': owner, 'reason': 'Declared external snapshot'})
                self.assertTrue(r['passed'])
                self.assertEqual(r['exemptions'][0]['lines'], 1001)
                self.assertTrue(r['exemptions'][0]['over_limit'])
                self.assertEqual(r['exemptions'][0]['sha256'], r['files'][0]['sha256'])
                self.assertFalse(r['violations'])
                self.assertTrue(self.check({'path': 'src/a.c', 'ownership': owner})['errors'])

    def test_bad_paths(self):
        for name in ('../a.c', 'src/../a.c', './src/a.c', '/etc/passwd', 'src//a.c',
                     'src/a.c/', 'src\\a.c', '', 'src/\0a.c'):
            with self.subTest(name=name):
                r = self.check({'path': name, 'ownership': 'project'})
                self.assertFalse(r['passed']); self.assertTrue(r['errors'])

    def test_absent_directory_and_symlinks(self):
        for name in ('absent.c', 'src'):
            self.assertTrue(self.check({'path': name, 'ownership': 'project'})['errors'])
        (self.root / 'alias.c').symlink_to(self.root / 'src/a.c')
        self.assertTrue(self.check({'path': 'alias.c', 'ownership': 'project'})['errors'])
        (self.root / 'aliasdir').symlink_to(self.root / 'src', target_is_directory=True)
        self.assertTrue(self.check({'path': 'aliasdir/a.c', 'ownership': 'project'})['errors'])
        self.manifest_for()
        alias = self.root / 'manifest_alias.json'; alias.symlink_to(self.manifest)
        self.assertTrue(c.audit(self.root, alias)['errors'])
        alias = self.root / 'root_alias'; alias.symlink_to(self.root, target_is_directory=True)
        self.assertTrue(c.audit(alias, self.manifest)['errors'])

    def test_schema(self):
        entry = {'path': 'src/a.c', 'ownership': 'project'}
        for bad in [dict(entry, ownership='ignored'), dict(entry, generated='yes'),
                    dict(entry, reason=False), dict(entry, unknown=0), {'path': 'src/a.c'}]:
            self.assertTrue(self.check(bad)['errors'])
        self.assertTrue(self.check(entry, entry)['errors'])
        for text in ('{}', '{"version":1,"files":[]}', '{"version":true,"files":[]}',
                     '{"version":1,"version":1,"files":[]}', '[1]', '{broken'):
            self.manifest.write_text(text)
            self.assertTrue(c.audit(self.root, self.manifest)['errors'])

    def test_parent_components_before_normalization(self):
        # A link followed by '..' must never silently audit a different tree.
        outside = self.root / 'outside'; (outside / 'deep').mkdir(parents=True)
        (outside / 'src').mkdir(); (outside / 'src/a.c').write_bytes(b'x\n' * 1001)
        (self.root / 'alias').symlink_to(outside / 'deep', target_is_directory=True)
        self.manifest_for()
        for project, manifest in (
            (self.root / 'alias' / '..', self.manifest),
            (self.root / 'src' / '..', self.manifest),
            (self.root, self.root / 'alias' / '..' / 'manifest.json'),
            (self.root, self.root / 'src' / '..' / 'manifest.json'),
        ):
            with self.subTest(project=str(project), manifest=str(manifest)):
                result = c.audit(project, manifest)
                self.assertFalse(result['passed'])
                self.assertEqual(result['files'], [])
                self.assertIn('Parent traversal refused', result['errors'][0])

    def test_cli_exit_codes(self):
        for lines, expected in [(1000, 0), (1001, 1)]:
            (self.root / 'src/a.c').write_bytes(b'x\n'*lines); self.manifest_for()
            q = subprocess.run([sys.executable, c.__file__, '--project', str(self.root),
                                '--manifest', str(self.manifest)], capture_output=True, timeout=10)
            self.assertEqual(q.returncode, expected)
            self.assertEqual(json.loads(q.stdout)['passed'], expected == 0)
        (self.root / 'src/a.c').unlink()
        q = subprocess.run([sys.executable, c.__file__, '--project', str(self.root),
                            '--manifest', str(self.manifest)], capture_output=True, timeout=10)
        self.assertEqual(q.returncode, 2); self.assertTrue(json.loads(q.stdout)['errors'])


if __name__ == '__main__':
    unittest.main()
