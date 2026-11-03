#!/usr/bin/env python3
"""Selection and environment contracts; no vendor process/license is invoked.

Run: python3 -m unittest discover -s tools/tests -p test_gowin_toolchain.py -v
Fixtures use independent home directories, installations and PATH entries. A
missing explicitly selected installation must never choose another version.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'gowin_toolchain.py'
spec = importlib.util.spec_from_file_location('tested_gowin_toolchain', SOURCE)
toolchain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolchain)


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gowin-selection-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'different-user'
        self.home.mkdir()
        self.ide = self.install(self.root / 'selected version' / 'IDE')
        self.library = self.root / 'system-freetype.so.6'
        self.library.write_bytes(b'fixture only; never loaded')

    def install(self, directory):
        (directory/'bin').mkdir(parents=True)
        (directory/'lib').mkdir()
        for name in ('gw_sh', 'GowinSynthesis'):
            executable = directory/'bin'/name
            executable.write_text('#!/bin/sh\nexit 99\n')
            executable.chmod(0o700)
        return directory

    def test_explicit_configuration_wins_over_home_and_path(self):
        self.install(self.home/'gowin/IDE')
        other = self.install(self.root/'other/IDE')
        selected = toolchain.select_ide(environ={'GOWIN_IDE': str(self.ide),
            'PATH': str(other/'bin')}, home=self.home)
        self.assertEqual(selected, self.ide)

    def test_missing_explicit_configuration_never_falls_back(self):
        missing = self.root/'missing/IDE'
        selected = toolchain.select_ide(environ={'GOWIN_IDE': str(missing),
            'PATH': str(self.ide/'bin')}, home=self.home)
        self.assertEqual(selected, missing)
        with self.assertRaisesRegex(RuntimeError, 'no alternate installation'):
            toolchain.environment(selected)

    def test_empty_and_relative_explicit_paths_are_errors(self):
        for value in ('', '   ', 'relative/IDE'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'GOWIN_IDE'):
                toolchain.select_ide(environ={'GOWIN_IDE': value}, home=self.home)

    def test_existing_home_installation_preserves_priority(self):
        preferred = self.home/'gowin/IDE'
        preferred.mkdir(parents=True)  # Broken home installation still wins.
        selected = toolchain.select_ide(environ={'PATH': str(self.ide/'bin')}, home=self.home)
        self.assertEqual(selected, preferred)
        with self.assertRaisesRegex(RuntimeError, 'Incomplete Gowin IDE'):
            toolchain.environment(selected)

    def test_path_symlink_identifies_real_installation(self):
        links = self.root/'commands'
        links.mkdir()
        (links/'gw_sh').symlink_to(self.ide/'bin/gw_sh')
        self.assertEqual(toolchain.select_ide(environ={'PATH': str(links)},
                                             home=self.home), self.ide)

    def test_path_wrapper_requires_explicit_directory(self):
        wrapper = self.root/'gw_sh'
        wrapper.write_text('#!/bin/sh\nexit 99\n')
        wrapper.chmod(0o700)
        with self.assertRaisesRegex(ValueError, 'set GOWIN_IDE explicitly'):
            toolchain.select_ide(environ={'PATH': str(self.root)}, home=self.home)

    def test_absent_tool_retains_importable_expected_paths(self):
        self.assertEqual(toolchain.select_ide(environ={'PATH': ''}, home=self.home),
                         self.home/'gowin/IDE')
        self.assertEqual(toolchain.PRIMITIVES, toolchain.IDE/'simlib/gw5a/prim_sim.v')

    def test_environment_is_local_and_preserves_preloads(self):
        original = {'GOWIN_FREETYPE': str(self.library), 'LD_PRELOAD': '/other.so',
                    'LD_LIBRARY_PATH': '/not-the-selected-tool', 'DISPLAY': ':5'}
        with patch.dict(os.environ, original, clear=True), patch.object(toolchain, 'IDE', self.ide):
            result = toolchain.environment(self.ide)
            self.assertEqual(dict(os.environ), original)
        self.assertEqual(result['LD_LIBRARY_PATH'], str(self.ide/'lib'))
        self.assertEqual(result['LD_PRELOAD'], str(self.library)+':/other.so')
        self.assertEqual((result['DISPLAY'], result['QT_QPA_PLATFORM']), ('', 'offscreen'))

    def test_preload_is_not_duplicated(self):
        with patch.dict(os.environ, {'GOWIN_FREETYPE': str(self.library),
                'LD_PRELOAD': str(self.library)+':/other.so'}, clear=True):
            result = toolchain.environment(self.ide, system_freetype=True)
        self.assertEqual(result['LD_PRELOAD'], str(self.library)+':/other.so')

    def test_workaround_can_be_disabled_without_changing_tool(self):
        with patch.dict(os.environ, {'GOWIN_FREETYPE': 'off'}, clear=True), \
                patch.object(toolchain, 'IDE', self.ide):
            result = toolchain.environment(self.ide)
        self.assertNotIn('LD_PRELOAD', result)
        self.assertEqual(result['LD_LIBRARY_PATH'], str(self.ide/'lib'))

    def test_missing_library_is_explicit_and_not_silently_skipped(self):
        with patch.dict(os.environ, {'GOWIN_FREETYPE': str(self.root/'absent.so')}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'GOWIN_FREETYPE'):
                toolchain.environment(self.ide, system_freetype=True)

    def test_nonexecutable_tool_is_rejected_before_launch(self):
        (self.ide/'bin/GowinSynthesis').chmod(0o600)
        with self.assertRaisesRegex(RuntimeError, 'GowinSynthesis'):
            toolchain.environment(self.ide)


if __name__ == '__main__':
    unittest.main()
