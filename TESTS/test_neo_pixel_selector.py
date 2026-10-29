"""Reject selector transformations/mappings which restore shared CE/reset."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from neo.pixel_selector import audit, transform


class PixelSelectorTests(unittest.TestCase):
    def test_transform_fails_closed_on_drift_and_duplicate(self):
        original = (ROOT/'tang/rtl/video/gpu_v1.v').read_text()
        changed = transform(original)
        self.assertEqual(changed.count('per_select<='), 1)
        with self.assertRaises(ValueError):
            transform(changed)
        with self.assertRaises(ValueError):
            transform(original.replace('per_select<=~per_select;', 'per_select<=1;'))

    def test_synthesis_and_route_reject_bad_controls_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'net.v'
            for routed in (False, True):
                name = r'\u_accel/u_v1/u_pixels/per_select_s0' if routed else 'per_select_s0'
                cell = f'DFFCE {name} (.D(next),.CLK(gpu_clk),.CE(VCC),.CLEAR(GND),.Q(per_select));\n'
                header = 'module console_neo;\n' if routed else 'module gpu_v1;\n'
                for text, passed in ((cell, True), ('', False), (cell+cell, False),
                        (cell.replace('.CE(VCC)', '.CE(advance)'), False),
                        (cell.replace('.CLEAR(GND)', '.CLEAR(chunk)'), False),
                        (cell.replace('.CLK(gpu_clk),', ''), False)):
                    path.write_text(header+text+'endmodule\n')
                    self.assertEqual(audit(path, routed=routed)['passed'], passed)


if __name__ == '__main__':
    unittest.main()
