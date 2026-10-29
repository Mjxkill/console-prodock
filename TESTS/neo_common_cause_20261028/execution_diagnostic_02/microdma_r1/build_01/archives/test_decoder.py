import struct
import unittest
from pathlib import Path
from decode_journal import decode
from rv32_model import RV32

class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary=(Path(__file__).parent/'build_01/microdma.bin').read_bytes()
        cls.words=RV32(binary).run()
    def encode(self,words):return struct.pack('<128I',*words)
    def test_complete(self):self.assertTrue(decode(self.encode(self.words))['passed'])
    def test_partial_and_identity(self):
        for data in [b'',self.encode(self.words)[:-4],bytes(512)]:
            with self.assertRaises(ValueError):decode(data)
    def test_success_flag_cannot_hide_faults(self):
        for index in [2,4,5,6,9,10,16,17,18,19,20,21,22,23,28,29,30,32,64,104,112]:
            words=self.words[:];words[index]^=1
            self.assertFalse(decode(self.encode(words))['passed'],index)
    def test_failure_stays_failure(self):
        for result in [0,-1,-2,-3,-4,-5,-6,-7,-9,-8]:
            words=self.words[:];words[3]=result&0xffffffff
            self.assertFalse(decode(self.encode(words))['passed'])

if __name__=='__main__':unittest.main(verbosity=2)
