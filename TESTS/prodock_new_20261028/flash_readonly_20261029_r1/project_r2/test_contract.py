"""Protected minimal adverse contract; no hardware fixtures."""
from pathlib import Path
import tempfile
import unittest
import flash_readonly as m

GOOD = (b'found 1 devices\nindex 0:\n\tidcode 0x1081b\n'
        b'Detect flash:\nJEDEC ID: 0xef4018\n'
        b'Detected: winbond W25Q128 256 sectors size: 128Mb\nDone\n')


class Tests(unittest.TestCase):
    def test_exact_detection(self):
        r=m.parse_detection(GOOD)
        self.assertEqual(r['jedec'],'ef4018')
        self.assertEqual(r['model'],'winbond W25Q128')
        self.assertEqual(r['sectors'],256)
        self.assertEqual(r['capacity'],16777216)
        m.parse_detection(GOOD+b'\t[9] auto_boot_1st_fail\n')
    def test_detection_adverse(self):
        for raw in (GOOD+b'FAIL\n', GOOD+b'Failed to read flash\n', GOOD+b'error\n',
                    GOOD+GOOD, GOOD.replace(b'0x1081b',b'0x281b'),
                    GOOD.replace(b'128Mb',b'64Mb'),
                    b'Detail:\nJedec ID : ff\nmemory capacity : ff\nDone\n'):
            with self.assertRaises((ValueError,RuntimeError)):m.parse_detection(raw)
    def test_backup_contents_and_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';a.write_bytes(bytes(range(256)));b.write_bytes(a.read_bytes())
            self.assertEqual(m.backup_summary(a,256)['bytes'],256)
            self.assertTrue(m.compare_backups(a,b,256)['matching'])
            b.write_bytes(b.read_bytes()[:-1]+b'X')
            with self.assertRaises((ValueError,RuntimeError)):m.compare_backups(a,b,256)
            b.unlink();b.hardlink_to(a)
            with self.assertRaises((ValueError,RuntimeError)):m.compare_backups(a,b,256)
            b.unlink();b.symlink_to(a)
            with self.assertRaises((ValueError,RuntimeError,OSError)):m.backup_summary(b,256)
            with self.assertRaises((ValueError,RuntimeError)):m.backup_summary(a,255)
    def test_owned_tests_not_empty(self):
        src=Path('test_owned.py').read_text()
        self.assertIn('def test_',src)
        self.assertIn('unittest',src)

if __name__=='__main__':unittest.main()
