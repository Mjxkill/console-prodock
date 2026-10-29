"""A physical experiment must not demote clocks or silently miss new LW nets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo.gpu_control_routes import catalog,constrain,audit


class ControlRouteTests(unittest.TestCase):
    def fixture(self):
        # A genuine clock has just as much fanout as the CE; only the CE may
        # receive a new constraint. A reset owned by the parent is not guessed.
        text='module console_neo ();\ngpu_accel u_accel (.clk(c));\ngpu_scanout u_gpu (.clk(c));\nendmodule\n'
        text+='module gpu_accel ();\nLUT2 enable (.F(en),.I0(a),.I1(b));\n'
        text+='DFFCE clock_source (.Q(clk),.D(d),.CLK(c),.CE(VCC),.CLEAR(GND));\n'
        text+=''.join(f'DFFCE data_{i} (.Q(q_{i}),.D(d),.CLK(clk),.CE(en),.CLEAR(parent_reset));\n' for i in range(64))
        text+='endmodule\nmodule gpu_scanout ();\nendmodule\n'
        return text

    def test_only_driven_nonclock_controls_are_constrained(self):
        text=self.fixture();cst,r=constrain('IO_LOC "pin" A1;\n',text)
        self.assertEqual([e['net'] for e in r['entries']],['u_accel/en'])
        self.assertIn('CLOCK_LOC "u_accel/en" LOCAL_CLOCK;',cst)
        self.assertEqual(r['parent_owned'][0]['net'],'parent_reset')
        self.assertNotIn('CLOCK_LOC "u_accel/clk"',cst)
        with self.assertRaises(ValueError):constrain('CLOCK_LOC "u_accel/en" BUFG = CE;',text)
        with self.assertRaises(ValueError):catalog(text.replace('u_accel','wrong_root'))

    def test_changed_catalog_and_new_gpu_lw_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            net=Path(d)/'net.v';rpt=Path(d)/'report.txt'
            net.write_text(self.fixture());r=catalog(net.read_text())
            rpt.write_text('6. Global Clock Signals\n gpu_clk | PRIMARY | PTR0\n7. IO\n')
            self.assertTrue(audit(net,rpt,r)['passed'])
            changed=json.loads(json.dumps(r));changed['entries'][0]['loads']=65
            self.assertFalse(audit(net,rpt,changed)['passed'])
            for name in ('u_accel/en','u_accel/unanticipated','u_gpu/new_reset'):
                rpt.write_text(f'6. Global Clock Signals\n {name} | LW | -\n7. IO\n')
                self.assertFalse(audit(net,rpt,r)['passed'])

    def test_reset_inverter_uses_local_source_or_parent_constraint(self):
        text=self.fixture().replace('module gpu_scanout ();\n',
            'module gpu_scanout ();\nDFFCE reset_ff (.Q(reset_n),.D(d),.CLK(clk),.CE(VCC),.CLEAR(GND));\n'
            'INV reset_inv (.O(reset),.I(reset_n));\n'+''.join(
                f'DFFRE r_{i} (.Q(q_{i}),.D(d),.CLK(clk),.CE(VCC),.RESET(reset));\n' for i in range(64)))
        cst,r=constrain('',text)
        self.assertIn('CLOCK_LOC "u_gpu/reset_n" LOCAL_CLOCK;',cst)
        self.assertNotIn('CLOCK_LOC "u_gpu/reset"',cst)
        text=text.replace('DFFCE reset_ff (.Q(reset_n),.D(d),.CLK(clk),.CE(VCC),.CLEAR(GND));\n','')
        cst,r=constrain('',text)
        self.assertNotIn('CLOCK_LOC "u_gpu/reset_n"',cst)
        self.assertTrue(any(e.get('inverted_reset')=='reset' for e in r['parent_owned']))

    def test_exported_gpu_control_alias_is_also_checked(self):
        with tempfile.TemporaryDirectory() as d:
            net=Path(d)/'net.v';rpt=Path(d)/'report.txt'
            text=self.fixture().replace('gpu_accel u_accel (.clk(c));','gpu_accel u_accel (.clk(c),.exported(alias));')
            text=text.replace('module gpu_accel ();','module gpu_accel ();\noutput exported;')
            net.write_text(text);r=catalog(text)
            rpt.write_text('6. Global Clock Signals\n alias | LW | -\n7. IO\n')
            self.assertFalse(audit(net,rpt,r)['passed'])


if __name__=='__main__':unittest.main()
