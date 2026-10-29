"""Reject synthesis/routing that restores CE or synchronous reset on pixel validity."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from neo.pixel_mask import audit


class PixelMaskAuditTests(unittest.TestCase):
    def fixture(self, *, routed=False, count=16, control='GND'):
        prefix = r'\u_accel/u_v1/u_pixels/' if routed else ''
        cells = '\n'.join(f'  DFFRE {prefix}pixel_written_{i}_s0 '
                         f'(.D(d{i}),.CLK(clk),.CE(VCC),.RESET({control}),.Q(q{i}));'
                         for i in range(count))
        return f'module {"console_neo" if routed else "gpu_v1"};\n{cells}\nendmodule\n'

    def check_fixture(self, text, routed=False):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'netlist.v'
            path.write_text(text)
            return audit(path, routed=routed)

    def test_synthesis_and_routing_without_dynamic_controls(self):
        for routed in (False, True):
            self.assertTrue(self.check_fixture(self.fixture(routed=routed), routed)['passed'])

    def test_bad_controls_missing_bits_duplicates_and_clock(self):
        for routed in (False, True):
            for text in (self.fixture(routed=routed, control='chunk_reset'),
                         self.fixture(routed=routed).replace('.CE(VCC)', '.CE(pixel_enable)', 1),
                         self.fixture(routed=routed, count=15),
                         self.fixture(routed=routed).replace('.Q(q1)', '.Q(q0)', 1),
                         self.fixture(routed=routed).replace('.CLK(clk),', '', 1)):
                self.assertFalse(self.check_fixture(text, routed)['passed'])


if __name__ == '__main__':
    unittest.main()
