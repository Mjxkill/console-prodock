"""Response-stage integration must preserve shared DDR and reset ownership."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from neo.gpu_response import freeze, audit_mapped, RTL, PROFILE
from neo.gpu_debug import instrument


class ResponseStageTests(unittest.TestCase):
    def test_mapping_rejects_bypass_clock_or_reset_changes(self):
        data=''.join(f'DFFCE out_data_{i}_s0 (.Q(gpu_response_data[{i}]),.D(blit_rd_data[{i}]),.CLK(gpu_clk),.CLEAR(GND),.CE(VCC));\n' for i in range(256))
        control=''
        for name,q,d in [('released_0_s0','released[0]','VCC'),
                         ('released_1_s0','released[1]','released[0]'),
                         ('out_valid_s0','gpu_response_valid','decoded_valid')]:
            control+=f'DFFCE {name} (.Q({q}),.D({d}),.CLK(gpu_clk),.CLEAR(clear),.CE(VCC));\ndefparam {name}.INIT=1\'b0;\n'
        good='module neo_gpu_response ();\n'+data+control+'INV inv (.O(clear),.I(vid_hrstn_accel));\nendmodule\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'mapped.v';p.write_text(good)
            self.assertTrue(audit_mapped(p)['passed'])
            for old,new in [('.CLK(gpu_clk)','.CLK(bus80_clk)'),
                            ('.CE(VCC)','.CE(in_valid)'),
                            ('.D(released[0])','.D(VCC)'),
                            ('out_data_0_s0','lost_payload_bit'),
                            ('.I(vid_hrstn_accel)','.I(other_reset)')]:
                with self.subTest(change=new):
                    p.write_text(good.replace(old,new,1))
                    self.assertFalse(audit_mapped(p)['passed'])

    def test_plain_and_instrumented_top_and_failure_atomicity(self):
        for debug in (False, True):
            with self.subTest(debug=debug), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp)
                for rel in (RTL, 'tang/boards/neo/console_neo.v',
                            'tang/rtl/video/gpu_accel.v', 'tang/rtl/video/blitter.v'):
                    p=source/rel;p.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(ROOT/rel,p)
                if debug:instrument(source)
                top=source/'tang/boards/neo/console_neo.v'
                original=top.read_text()
                record=freeze(source)
                self.assertEqual(record['latency_cycles'],1)
                self.assertIn('.blit_rd_data(blit_rd_data), .blit_rd_valid(blit_rd_valid)',top.read_text())
                self.assertIn('.rd_data(gpu_response_data),.rd_valid(gpu_response_valid)',top.read_text())
                after=top.read_bytes()
                with self.assertRaises(ValueError):freeze(source)
                self.assertEqual(after,top.read_bytes())
                (source/PROFILE).unlink()
                top.write_text(original.replace('.rd_valid(blit_rd_valid)', '.rd_valid(unknown)'))
                before=top.read_bytes()
                with self.assertRaises(ValueError):freeze(source)
                self.assertEqual(before,top.read_bytes())
                self.assertFalse((source/PROFILE).exists())


if __name__=='__main__':unittest.main()
