"""Neo GPU observation taps must be isolated and fail closed on source drift."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/neo'))
from gpu_debug import instrument,local_reset_constraints
from probe_gpu_debug import decode,target_cases,control_cases


class InstrumentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.source=Path(self.temp.name)
        self.paths=['tang/rtl/video/gpu_accel.v','tang/rtl/video/blitter.v','tang/boards/neo/console_neo.v']
        for rel in self.paths:
            dest=self.source/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/rel,dest)

    def test_only_copy_changed_and_no_control_input_added(self):
        before={rel:(ROOT/rel).read_bytes() for rel in self.paths}
        records=instrument(self.source)
        for rel in self.paths:
            self.assertEqual((ROOT/rel).read_bytes(),before[rel])
            self.assertEqual(records[rel]['before'],hashlib.sha256(before[rel]).hexdigest())
        for rel in self.paths[:2]:
            new=(self.source/rel).read_text().split(');',1)[0]
            old=before[rel].decode().split(');',1)[0]
            self.assertEqual(new.count('input '),old.count('input '))
        self.assertIn('neo_gpu_debug u_gpu_debug',(self.source/self.paths[2]).read_text())
        top=(self.source/self.paths[2]).read_text()
        self.assertIn("selected[2] ? (selected[0] ? debug_hready:1'b1):",top)
        self.assertIn('.hready(debug_hready)',top)

    def test_unknown_source_refused_without_partial_changes(self):
        broken=self.source/self.paths[2]
        broken.write_text(broken.read_text().replace('selected[2] ? pad_hrdata:','changed_selector'))
        before={rel:(self.source/rel).read_bytes() for rel in self.paths}
        with self.assertRaises(ValueError):instrument(self.source)
        for rel in self.paths:self.assertEqual((self.source/rel).read_bytes(),before[rel])


class DecodeTests(unittest.TestCase):
    def test_configuration_suites_never_issue_memory_operations(self):
        cases=target_cases()+control_cases()
        self.assertEqual(len(cases),40)
        self.assertEqual(len({c['name'] for c in cases}),40)
        for case in cases:
            self.assertEqual(len(case['words']),8)
            self.assertIn(case['words'][0]>>24,(22,24,25,26,30,31,33))
            self.assertTrue(all(0<=w<=0xffffffff for w in case['words']))
        self.assertEqual(sum(c['accepted'] for c in target_cases()),22)
        self.assertEqual(sum(c['accepted'] for c in control_cases()),9)

    def test_register_and_bit_positions(self):
        raw=[0x4e474442,6,16,3,16,0x1234,0,0,2,0xfc00,0x00010002,0x10081600,1,0,0,0x16000000]
        r=decode(raw)
        self.assertEqual((r['engine_resetn'],r['mrst']),(15,3))
        self.assertEqual((r['blitter_wp'],r['blitter_rp'],r['opcode']),(16,8,22))
        self.assertEqual((r['done'],r['command_bad'],r['command_lost']),(2,1,2))
        self.assertEqual(r['state_bits'],[0])
        self.assertFalse(r['blitter_reset'])

    def test_stale_or_incomplete_snapshots_rejected(self):
        for raw in ([0]*16,[0x4e474442,5]+[0]*14,[0x4e474442,6]+[0]*13):
            with self.assertRaises(ValueError):decode(raw)


class ResetRoutingTests(unittest.TestCase):
    def setUp(self):
        self.netlist='module gpu_accel (gpu_clk);\n'+''.join(
            f' DFFCE engine_resetn_{i}_s0 (.Q(gpu_debug_state_{44+i}),.D(gpu_debug_state_42),'
            '.CLK(gpu_clk),.CLEAR(n1205_6),.CE(VCC));\n' for i in range(4))+'endmodule\n'

    def test_preserves_original_constraints_and_only_adds_four_reset_nets(self):
        cst='IO_LOC "clk" V22;\nCLOCK_LOC "gpu_clk" BUFG[5] = CLK;\n'
        changed,nets=local_reset_constraints(cst,self.netlist)
        self.assertTrue(changed.startswith(cst))
        self.assertEqual(nets,[f'gpu_debug_state[{i}]' for i in range(44,48)])
        self.assertEqual(changed[len(cst):].count('LOCAL_CLOCK;'),4)

    def test_wrong_driver_or_duplicate_constraint_refused(self):
        for bad in [self.netlist.replace('DFFCE engine_resetn_2_s0','DFF engine_resetn_2_s0'),
                    self.netlist.replace('.D(gpu_debug_state_42)','.D(VCC)',1),
                    self.netlist.replace('.CLK(gpu_clk)','.CLK(vid_hclk)',1)]:
            with self.assertRaises(ValueError):local_reset_constraints('',bad)
        with self.assertRaises(ValueError):
            local_reset_constraints('CLOCK_LOC "gpu_debug_state[45]" LOCAL_CLOCK;',self.netlist)


if __name__=='__main__':unittest.main()
