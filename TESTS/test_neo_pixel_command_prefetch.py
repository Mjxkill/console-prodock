import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from neo.pixel_command_prefetch import freeze, audit_mapped, RTL, PROFILE, CAPTURE


class PixelPrefetchTests(unittest.TestCase):
    def test_freeze_rejects_drift_and_duplicate_application(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / RTL
            path.parent.mkdir(parents=True)
            (source / PROFILE).parent.mkdir(parents=True)
            original = (ROOT / RTL).read_text()
            path.write_text(original)
            freeze(source)
            self.assertIn(CAPTURE, path.read_text())
            self.assertEqual(path.read_text().count('packet<=command;'), 1)
            self.assertNotIn('packet<=0;', path.read_text())
            with self.assertRaises(ValueError):
                freeze(source)
            (source / PROFILE).unlink()
            changed = original.replace('packet<=command;', 'packet<=other;')
            path.write_text(changed)
            with self.assertRaises(ValueError):
                freeze(source)
            self.assertEqual(path.read_text(), changed)

    def test_mapping_checks_all_bits_and_rejects_start_or_reset_decode(self):
        good = 'module gpu_v1 ();\n' + ''.join(
            f'DFFRE packet_{i}_s0 (.Q(packet[{i}]),.D(d),.CLK(gpu_clk),.CE(state[0]),.RESET(GND));\n'
            for i in range(256)) + 'endmodule\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'net.v'
            path.write_text(good)
            self.assertTrue(audit_mapped(path)['passed'])
            for old, new in [('CE(state[0])', 'CE(start_decode)'), ('RESET(GND)', 'RESET(rst)'),
                             ('CLK(gpu_clk)', 'CLK(other_clk)'), ('DFFRE packet_0_s0', 'DFFRE lost_bit'),
                             ('Q(packet[0])', 'Q(packet[1])')]:
                path.write_text(good.replace(old, new, 1))
                self.assertFalse(audit_mapped(path)['passed'])


if __name__ == '__main__':
    unittest.main()
