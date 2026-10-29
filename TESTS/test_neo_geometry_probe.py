"""Small-window diagnostics must reject memory commands outside their capture."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/neo'))
from probe_geometry import SIZE, WINDOWS, check_small_windows


class SmallWindowTests(unittest.TestCase):
    def setUp(self):
        self.initial = bytes(3*SIZE)
        self.words = [22 << 24, *WINDOWS[:2], (64 << 16) | 32,
                      (160 << 16) | 192, 0, 0, 0]

    def test_bounded_target_and_texture(self):
        words = self.words + [24 << 24, WINDOWS[2], (16 << 16) | 16, 32, 0, 0, 0, 0]
        check_small_windows(words, self.initial, self.initial, 16384)

    def test_wrong_surface_or_unsupported_command(self):
        for word, value in ((1, 0x12000000), (3, (64 << 16) | 512), (4, (4096 << 16) | 192)):
            bad = list(self.words);bad[word] = value
            with self.assertRaises(ValueError):check_small_windows(bad, self.initial, self.initial, 16384)
        for opcode in (1, 29, 34):
            with self.assertRaises(ValueError):
                check_small_windows(self.words + [opcode << 24] + [0]*7,
                                    self.initial, self.initial, 16384)
        with self.assertRaises(ValueError):
            check_small_windows([27 << 24]+[0]*7, self.initial, self.initial, 16384)

    def test_expected_guard_change_outside_capture(self):
        for offset in (16384, SIZE+16384, 2*SIZE+16384):
            expected = bytearray(self.initial);expected[offset] = 1
            with self.assertRaises(ValueError):
                check_small_windows(self.words, self.initial, expected, 16384)

    def test_texture_range_and_invalid_size(self):
        for base, dimensions, stride in ((WINDOWS[2]+32, (16 << 16) | 16, 32),
                                          (WINDOWS[2], (512 << 16) | 512, 1024)):
            words = self.words + [24 << 24, base, dimensions, stride, 0, 0, 0, 0]
            with self.assertRaises(ValueError):check_small_windows(words, self.initial, self.initial, 16384)
        for size in (0, -1, 4000, SIZE+4096):
            with self.assertRaises(ValueError):
                check_small_windows(self.words, self.initial, self.initial, size)


if __name__ == '__main__':
    unittest.main()
