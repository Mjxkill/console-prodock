#!/usr/bin/env python3
"""CST isolation tests only; no Gowin process, board access or build writes."""
import json
import unittest
import route9_dma_cone as r


class ConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (r.BASE / 'source/tang/boards/neo/neo.cst').read_text()
        cls.candidate = cls.base + r.ADDITION

    def test_exact_eight_cell_delta(self):
        result = r.validate_delta(self.base, self.candidate)
        self.assertTrue(result['passed'])
        self.assertEqual(result['added_cells'], 8)

    def test_comments_and_statement_layout_preserve_meaning(self):
        reformatted = self.candidate.replace(';\n', '; \n') + '\n// harmless comment\n'
        self.assertTrue(r.validate_delta(self.base, reformatted)['passed'])

    def test_prepare_record_survives_serialization(self):
        _, _, record = r.inputs()
        self.assertEqual(record, json.loads(json.dumps(record)))

    def test_reject_every_other_mutation(self):
        variants = {
            'hidden pin change': self.candidate + 'IO_LOC "uart_tx" V22;',
            'clock allocation': self.candidate + 'CLOCK_LOC "gpu_clk" LOCAL_CLOCK;',
            'hdmi relocation': self.candidate.replace('R102C150[1][A]', 'R102C149[1][A]'),
            'existing anchor moved': self.candidate.replace('R[60:80]C[90:110]', 'R[60:80]C[89:110]'),
            'observer added': self.candidate + 'INS_LOC "u_scan_observe/up_1_s0" ' + r.REGION + ';',
            'ninth cell': self.candidate + 'INS_LOC "u_accel/u_dma/state_0_s1" ' + r.REGION + ';',
            'duplicate cell': self.candidate + f'INS_LOC "{r.NAMES[0]}" {r.REGION};',
            'wildcard': self.candidate.replace('u_accel/u_dma/n66_s4', 'u_accel/u_dma/n66_*'),
            'wrong region': self.candidate.replace(r.REGION, 'R[40:65]C[64:90]'),
            'missing target': self.candidate.replace(f'INS_LOC "{r.NAMES[0]}" {r.REGION};', ''),
            'same-line hidden IO': self.candidate.replace(r.ADDITION, r.ADDITION.replace(';\n', '; IO_LOC "clk" A1;\n', 1)),
        }
        for name, candidate in variants.items():
            with self.subTest(name=name):
                self.assertNotEqual(candidate, self.candidate, 'Mutation did not match the real CST')
                with self.assertRaises(AssertionError):
                    r.validate_delta(self.base, candidate)


if __name__ == '__main__':
    unittest.main()
