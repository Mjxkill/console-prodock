#!/usr/bin/env python3
"""Offline release preparation and adversarial archive tests; no Gowin/board.

Run: python3 -m unittest discover -s tools/tests -p test_rebuild_release.py -v
Tiny packages exercise the same extractor and guards as the published inputs.
"""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/'rebuild_release.py'
spec = importlib.util.spec_from_file_location('release_under_test', SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='release-rebuild-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packages = self.root/'packages'
        self.package = self.packages/'neo_reject_r1'
        self.package.mkdir(parents=True)
        self.output = self.root/'different user'/'fresh output'
        self.contents = {'console_neo.vg': b'module console_neo; endmodule\n',
                         'neo.cst': b'// pinned\n'}
        self.script = 'add_file {console_neo.vg}\nadd_file {neo.cst}\nrun pnr\n'
        (self.package/'route.tcl').write_text(self.script)
        self.record = {'schema': 1, 'board': 'neo', 'release': 'neo_reject_r1',
            'build_kind': 'mapped-netlist-reroute',
            'files': {n: {'bytes': len(v), 'sha256': digest(v)} for n, v in self.contents.items()},
            'scripts': {'route.tcl': digest(self.script.encode())}, 'relocation': {},
            'outputs': {'netlist': 'console_neo.vg', 'bitstream': 'impl/pnr/console_neo.fs'},
            'bitstream': {'sha256': 'historical-reference-only'}}
        self.write_archive()

    def write_archive(self, *, extra=None, symlink=False, corrupt_data=False):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for index, (name, data) in enumerate(self.contents.items()):
                member = tarfile.TarInfo(name)
                if symlink and index == 0:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '../outside'
                    archive.addfile(member)
                else:
                    if corrupt_data and index == 0:
                        data = b'X'+data[1:]
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            if extra is not None:
                member = tarfile.TarInfo(extra)
                member.size = 1
                archive.addfile(member, io.BytesIO(b'!'))
        data = gzip.compress(stream.getvalue(), mtime=0)
        (self.package/'inputs.tar.gz').write_bytes(data)
        self.record['archive'] = {'path': 'inputs.tar.gz', 'sha256': digest(data)}
        self.write_manifest()

    def write_manifest(self):
        (self.package/'manifest.json').write_text(json.dumps(self.record))

    def prepare(self):
        return release.prepare('neo', self.output, packages=self.packages)

    def test_prepare_preserves_bytes_in_an_unrelated_directory(self):
        with patch.object(release.subprocess, 'run', side_effect=AssertionError('must not launch')):
            output, record = self.prepare()
        self.assertEqual(output, self.output)
        for name, expected in self.contents.items():
            self.assertEqual((output/name).read_bytes(), expected)
        evidence = json.loads((output/'PREPARATION.json').read_text())
        self.assertFalse(evidence['Gowin_executed'])
        self.assertFalse(evidence['timing_qualified'])
        self.assertEqual(record['build_kind'], 'mapped-netlist-reroute')

    def test_no_overwrite(self):
        self.output.mkdir(parents=True)
        marker = self.output/'keep'
        marker.write_bytes(b'original')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.prepare()
        self.assertEqual(marker.read_bytes(), b'original')

    def test_changed_archive_refused_before_output_creation(self):
        with (self.package/'inputs.tar.gz').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed input archive'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_changed_recipe_refused(self):
        (self.package/'route.tcl').write_text('run syn\n')
        with self.assertRaisesRegex(ValueError, 'Changed release script'):
            self.prepare()

    def test_wrong_board_identity_refused(self):
        self.record['board'] = 'prodock'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Wrong release identity'):
            self.prepare()

    def test_tar_symlink_refused(self):
        self.write_archive(symlink=True)
        with self.assertRaisesRegex(ValueError, 'Non-regular archive'):
            self.prepare()
        self.assertFalse((self.root/'outside').exists())

    def test_path_traversal_refused_even_when_manifest_lists_it(self):
        self.contents['../escape'] = b'bad'
        self.record['files']['../escape'] = {'bytes': 3, 'sha256': digest(b'bad')}
        self.write_archive()
        with self.assertRaisesRegex(ValueError, 'Unsafe package path'):
            self.prepare()
        self.assertFalse((self.output.parent/'escape').exists())

    def test_unlisted_or_duplicate_tar_members_refused(self):
        for extra in ('unlisted', 'console_neo.vg'):
            with self.subTest(extra=extra):
                self.write_archive(extra=extra)
                output = self.root/('duplicate' if extra.endswith('.vg') else 'extra')
                with self.assertRaisesRegex(ValueError, 'inventory differs'):
                    release.prepare('neo', output, packages=self.packages)

    def test_member_hash_failure_is_recorded(self):
        self.write_archive(corrupt_data=True)
        with self.assertRaisesRegex(ValueError, 'member hash'):
            self.prepare()
        self.assertIn('member hash', (self.output/'PREPARATION_FAILED.json').read_text())
        self.assertFalse((self.output/'PREPARATION.json').exists())

    def test_neo_cannot_masquerade_as_source_synthesis(self):
        output, record = self.prepare()
        with self.assertRaisesRegex(ValueError, 'netlist-only'):
            release.build(output, record, 'syn')

    def test_prepared_input_modification_refused_before_tool_import(self):
        output, record = self.prepare()
        (output/'console_neo.vg').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Prepared input changed'):
            release.build(output, record, 'all')

    def test_nominal_exit_cannot_hide_error_in_tool_log(self):
        self.output.mkdir(parents=True)
        def fake_run(argv, **kwargs):
            kwargs['stdout'].write('  ERROR routing failed\n')
            return type('Result', (), {'returncode': 0})()
        with patch.object(release.subprocess, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, 'Gowin failed'):
                release.run_phase(self.output, 'route.tcl', self.root/'IDE', {})
        result = json.loads((self.output/'route.tcl.result.json').read_text())
        self.assertEqual(result['returncode'], 0)
        self.assertTrue(result['tool_errors'])


if __name__ == '__main__':
    unittest.main()
