"""Protected public contract for the separate hardened MD12 decoder."""
import struct
import unittest
from microdma_decode_v2 import decode


def good():
    words = [0]*128
    words[:10] = [0x4d443132,1,10,1,0,0,0xa0000001,0,0x1800,0]
    words[17:24] = [0x424c5432,0,1,2,0,0,0]
    words[24:32] = [1,0x1200007c,0,0,32,32,32,0]
    seed = [(0x12000000+4*i)^0xa5396c17 for i in range(32)]
    words[32:96] = seed+seed
    words[96:128] = seed[:8]+[0x6b4d6b4d]*8+seed[16:]
    return words


class ExactMD12Contract(unittest.TestCase):
    def test_actual_healthy_completion(self):
        self.assertTrue(decode(struct.pack('<128I',*good()))['passed'])

    def test_all_reserved_extent_lastword_mutations(self):
        for index, value in [(24,0),(24,2),(25,0),(25,0x12000080),(26,1),(27,1),(31,1)]:
            with self.subTest(index=index,value=value):
                words=good();words[index]=value
                self.assertFalse(decode(struct.pack('<128I',*words))['passed'])
