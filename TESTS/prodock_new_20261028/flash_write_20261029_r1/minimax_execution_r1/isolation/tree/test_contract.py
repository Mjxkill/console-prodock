"""Protected tests: parser completion is distinct from a driver exit status."""
from pathlib import Path
import unittest
import program_log

IDENT=b'found 1 devices\nindex 0:\n idcode 0x1081b\n'
FLASH=b'JEDEC ID: 0xef4018\nDetected: winbond W25Q128 256 sectors size: 128Mb\n'
WRITE=b'Writing [================] 100.00%\nDone\nVerifying write (May take time)\nReading [================] 100.00%\nDone\n'
GOOD=IDENT+FLASH+FLASH+WRITE
class Contract(unittest.TestCase):
    def test_real_two_identical_identifications(self):
        value=program_log.parse_program(GOOD,jedec='ef4018',sectors=256)
        self.assertIsInstance(value,dict)
        program_log.parse_program(IDENT+FLASH+WRITE,jedec='ef4018',sectors=256)
    def test_write_is_not_verification(self):
        for raw in (IDENT+FLASH, IDENT+FLASH+b'Writing 100.00%\nDone\n',
                    GOOD+b'Error: fail to disable flash access\n',
                    GOOD.replace(b'0x1081b',b'0x281b'),
                    GOOD.replace(FLASH,FLASH.replace(b'ef4018',b'ef4017'),1),
                    IDENT+FLASH+WRITE.replace(b'Reading [================] 100.00%',b'Reading 99.00%'),
                    GOOD+IDENT):
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError,RuntimeError)):
                    program_log.parse_program(raw,jedec='ef4018',sectors=256)
    def test_module_bounds(self):
        for n in ['flash_write.py','proofs.py','program_log.py','test_owned.py']:
            self.assertLessEqual(len(Path(n).read_bytes().splitlines()),1000,n)
        self.assertIn('def test_',Path('test_owned.py').read_text())
if __name__=='__main__':unittest.main()
