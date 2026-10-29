import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from neo.command_prefetch import freeze, audit_mapped, RTL, PROFILE, CAPTURE


class CommandPrefetchTests(unittest.TestCase):
    def test_transform_preserves_one_assignment_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / RTL
            path.parent.mkdir(parents=True)
            (source / PROFILE).parent.mkdir(parents=True)
            original = (ROOT / RTL).read_text()
            path.write_text(original)
            freeze(source)
            self.assertEqual(path.read_text().count('captured_command<=command;'), 1)
            self.assertIn('always @(posedge clk)if(state[IDLE])begin\n' + CAPTURE, path.read_text())
            with self.assertRaises(ValueError):
                freeze(source)
            (source / PROFILE).unlink()
            path.write_text(original.replace('captured_command<=command;', 'captured_command<=different;'))
            with self.assertRaises(ValueError):
                freeze(source)

    def test_mapping_rejects_decoded_enable_and_missing_bits(self):
        good = 'module gpu_geometry ();\n' + ''.join(
            f'DFFRE {name}_{i}_s0 (.Q({name}[{i}]),.D(d),.CLK(gpu_clk),.RESET(GND),.CE(state[0]));\n'
            for name, first, last in [('captured_command', 0, 256), ('mesh_vertex_end', 5, 33), ('mesh_face_end', 5, 33)]
            for i in range(first, last)) + 'endmodule\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mapped.v'
            path.write_text(good)
            self.assertTrue(audit_mapped(path)['passed'])
            for old, new in [('CE(state[0])', 'CE(decoded_start)'), ('RESET(GND)', 'RESET(global_reset)'),
                             ('CLK(gpu_clk)', 'CLK(other_clk)'), ('DFFRE captured_command_0_s0', 'DFFRE missing_bit')]:
                path.write_text(good.replace(old, new, 1))
                self.assertFalse(audit_mapped(path)['passed'])


if __name__ == '__main__':
    unittest.main()
