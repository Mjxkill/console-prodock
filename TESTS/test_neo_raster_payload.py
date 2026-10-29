import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from neo.raster_payload import freeze, audit_mapped, RTL, PROFILE, OLD, NEW


class RasterPayloadTests(unittest.TestCase):
    def test_transform_is_local_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / RTL
            path.parent.mkdir(parents=True)
            (source / PROFILE).parent.mkdir(parents=True)
            original = (ROOT / RTL).read_text()
            path.write_text(original)
            freeze(source)
            self.assertEqual(path.read_text(), original.replace(OLD, NEW, 1))
            with self.assertRaises(ValueError):
                freeze(source)
            (source / PROFILE).unlink()
            drift = original.replace('if(chunk_init)', 'if(other_condition)', 1)
            path.write_text(drift)
            with self.assertRaises(ValueError):
                freeze(source)
            self.assertEqual(path.read_text(), drift)

    def test_mapping_rejects_missing_bits_and_wrong_clear(self):
        good = 'module gpu_raster ();\n' + ''.join(
            f'DFFRE {name}_{i}_s0 (.Q({name}[{i}]),.D(d),.CLK(gpu_clk),.RESET(chunk_init),.CE(e));\n'
            for name in ('color_buf', 'z_buf') for i in range(256)) + 'endmodule\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mapped.v'
            path.write_text(good)
            self.assertTrue(audit_mapped(path)['passed'])
            for old, new in [('RESET(chunk_init)', 'RESET(global_reset)'),
                             ('CLK(gpu_clk)', 'CLK(other_clk)'),
                             ('DFFRE color_buf_0_s0', 'DFFRE missing_bit'),
                             ('Q(z_buf[0])', 'Q(z_buf[1])')]:
                path.write_text(good.replace(old, new, 1))
                self.assertFalse(audit_mapped(path)['passed'])


if __name__ == '__main__':
    unittest.main()
