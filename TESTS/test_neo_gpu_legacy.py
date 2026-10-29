"""A changed pixel is not proof of a working fence, or intact guard bytes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/neo'))
from probe_gpu_legacy import analyze, PATTERN, EXPECTED


class LegacyProbeTests(unittest.TestCase):
    def log(self, before=0, after=1):
        return f'LEGACY_BEGIN\nLEGACY_BEFORE 0 {before} 0\nLEGACY_AFTER 0 {after} 0\nLEGACY_COMPLETE\n'

    def test_exact_dma_and_fence(self):
        self.assertTrue(analyze(self.log(), PATTERN, EXPECTED)['passed'])
        self.assertTrue(analyze(self.log(65535, 0), PATTERN, EXPECTED)['passed'])

    def test_dma_without_fence_is_distinguished(self):
        r = analyze(self.log(0, 0), PATTERN, EXPECTED)
        self.assertTrue(r['dma_exact'])
        self.assertFalse(r['fence_passed'])
        self.assertFalse(r['passed'])

    def test_missing_or_guard_corruption_never_passes(self):
        wrong = bytearray(EXPECTED)
        wrong[0] ^= 1
        for after in (PATTERN, bytes(wrong), EXPECTED[:-1], b''):
            self.assertFalse(analyze(self.log(), PATTERN, after)['passed'])
        self.assertFalse(analyze(self.log(), b'', EXPECTED)['passed'])

    def test_completion_marker_required(self):
        self.assertFalse(analyze(self.log().replace('LEGACY_COMPLETE', ''), PATTERN, EXPECTED)['passed'])


if __name__ == '__main__':
    unittest.main()
