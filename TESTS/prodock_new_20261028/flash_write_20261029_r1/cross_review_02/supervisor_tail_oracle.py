"""Independent byte oracle for the frozen offline sector-tail contract.

No board operation. Sizes straddle erase boundaries; full-capacity readback
also tests the final untouched byte. These are software proofs only.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / 'prepared/refs/review/offline.py'
EXPECTED_SHA = '3ee29df91dc50799bb4bcc2fca43d632d61bd26733f9317500281971628c9277'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA
spec = importlib.util.spec_from_file_location('frozen_offline_oracle', SOURCE)
offline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offline)


class TailOracle(unittest.TestCase):
    def check_case(self, length, capacity):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup = bytes(range(256)) * (capacity // 256)
            payload = (b'\x5a\xa5\x29\x10' * ((length + 3) // 4))[:length]
            (root / 'a').write_bytes(backup)
            (root / 'b').write_bytes(backup)
            (root / 'payload').write_bytes(payload)
            report = offline.prepare(root/'payload', root/'a', root/'b', capacity, root/'out')
            # Oracle uses slice replacement on a full independent bytearray;
            # no copied concatenation or bitwise-rounding implementation.
            expected = bytearray(backup)
            expected[:length] = payload
            sectors = length // 65536 + (length % 65536 != 0)
            programmed = (root/'out/program.bin').read_bytes()
            self.assertEqual(programmed, bytes(expected[:sectors*65536]))
            self.assertEqual(report['program_bytes'], sectors*65536)
            self.assertEqual(report['preserved_last_sector_bytes'], sectors*65536-length)
            self.assertEqual(report['preserved_tail_bytes'], capacity-length)
            self.assertEqual(report['expected_full_sha256'], hashlib.sha256(expected).hexdigest())
            (root/'readback').write_bytes(expected)
            self.assertTrue(offline.verify(root/'out/plan.json',root/'readback')['full_readback_matches'])
            for offset in {0, length-1, length, capacity-1}:
                if offset >= capacity:
                    continue
                bad = bytearray(expected)
                bad[offset] ^= 1
                (root/'readback').write_bytes(bad)
                with self.assertRaisesRegex(ValueError, 'differs'):
                    offline.verify(root/'out/plan.json', root/'readback')
            (root/'readback').write_bytes(expected[:-1])
            with self.assertRaisesRegex(ValueError, 'Wrong length'):
                offline.verify(root/'out/plan.json', root/'readback')

    def test_one_byte(self): self.check_case(1, 262144)
    def test_before_sector(self): self.check_case(65535, 262144)
    def test_exact_sector(self): self.check_case(65536, 262144)
    def test_after_sector(self): self.check_case(65537, 262144)
    def test_real_capacity_geometry_only(self): self.check_case(65537, 16*1024*1024)


if __name__ == '__main__': unittest.main()
