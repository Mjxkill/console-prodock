"""Relocation and immutable-input tests; no vendor tools or hardware needed."""
import hashlib
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap_build import install_archive
from build_gpu_geometry import relocate_template


class BuildPortability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'inputs.tar'

    def archive_with(self, name='input.txt', data=b'frozen bytes', symlink=False):
        with tarfile.open(self.archive, 'w') as archive:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            if symlink:
                entry.type = tarfile.SYMTYPE
                entry.linkname = '/tmp/outside'
            archive.addfile(entry, io.BytesIO(data))
        return {name: hashlib.sha256(data).hexdigest()}

    def test_install_and_idempotence(self):
        entries = self.archive_with('stage/input.txt')
        self.assertEqual(install_archive(self.archive, entries, self.root), 1)
        self.assertEqual((self.root / 'stage/input.txt').read_bytes(), b'frozen bytes')
        self.assertEqual(install_archive(self.archive, entries, self.root), 0)

    def test_different_file_is_preserved(self):
        entries = self.archive_with()
        target = self.root / 'input.txt'
        target.write_bytes(b'local work')
        with self.assertRaisesRegex(ValueError, 'preserving'):
            install_archive(self.archive, entries, self.root)
        self.assertEqual(target.read_bytes(), b'local work')

    def test_corruption_is_not_installed(self):
        entries = self.archive_with()
        entries['input.txt'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            install_archive(self.archive, entries, self.root)
        self.assertFalse((self.root / 'input.txt').exists())

    def test_parent_path_is_rejected(self):
        entries = self.archive_with('../outside')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            install_archive(self.archive, entries, self.root)

    def test_archive_symlink_is_rejected(self):
        entries = self.archive_with(symlink=True)
        with self.assertRaisesRegex(ValueError, 'nonregular'):
            install_archive(self.archive, entries, self.root)

    def test_destination_symlink_is_rejected(self):
        entries = self.archive_with()
        (self.root / 'input.txt').symlink_to(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'Symlinked'):
            install_archive(self.archive, entries, self.root)

    def test_tcl_relocates_both_snapshot_and_helper(self):
        original = '/work/old-checkout'
        stage = original + '/tang/impl/gpu_sdusb_c28'
        recipe = ('add_file {' + stage + '/source/tang/rtl/console_gpu.v}\n'
                  'puts [exec python3 {' + original + '/tools/build_gpu.py}]\n')
        new = relocate_template(recipe, self.root / 'new-build')
        self.assertNotIn(original, new)
        self.assertIn(str(self.root / 'new-build/source/tang/rtl/console_gpu.v'), new)
        self.assertIn(str(Path(__file__).resolve().parents[1] / 'build_gpu.py'), new)

    def test_unknown_tcl_fails_instead_of_using_old_paths(self):
        with self.assertRaises(ValueError):
            relocate_template('run all', self.root)


if __name__ == '__main__':
    unittest.main()
