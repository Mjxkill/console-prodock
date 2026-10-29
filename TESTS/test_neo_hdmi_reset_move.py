"""Keep reset-placement changes physical and reject stale profile/CST pairs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo.timing_closure import move_hdmi_resets,PROFILE


class MoveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);board=self.root/'tang/boards/neo';board.mkdir(parents=True)
        self.cst=board/'neo.cst';self.sdc=board/'neo.sdc'
        self.sdc.write_text('set_max_delay 8 -from A -to B\n')
        self.record=dict(hdmi_reset_column=150,hdmi_dce_site='SG[0]',hdmi_clock_index='auto')
        (self.root/PROFILE).write_text(json.dumps(self.record))
        self.original='INS_LOC "u_video_fast" SG[0];\n'+''.join(
            f'INS_LOC "u_hdmi/g_reset[{ch}].reset_sync_fall_s1" R{row}C150[{slot}][A];\n'
            for ch,row,slot in ((0,102,1),(1,102,2),(2,57,1)))
        self.cst.write_text(self.original)

    def test_roundtrip_keeps_clocks_and_other_metadata(self):
        move_hdmi_resets(self.root,160)
        self.assertEqual(json.loads((self.root/PROFILE).read_text()),dict(self.record,hdmi_reset_column=160))
        move_hdmi_resets(self.root,150)
        self.assertEqual(self.cst.read_text(),self.original)
        self.assertEqual(self.sdc.read_text(),'set_max_delay 8 -from A -to B\n')

    def test_stale_cst_rejected_without_partial_mutation(self):
        bad=self.original.replace('R57C150[1][A]','R58C150[1][A]')
        self.cst.write_text(bad)
        with self.assertRaises(ValueError):move_hdmi_resets(self.root,160)
        self.assertEqual(self.cst.read_text(),bad)
        self.assertEqual(json.loads((self.root/PROFILE).read_text()),self.record)

    def test_unknown_site_or_column_rejected(self):
        with self.assertRaises(ValueError):move_hdmi_resets(self.root,140)
        self.cst.write_text(self.original.replace('SG[0]','SG[1]'))
        with self.assertRaises(ValueError):move_hdmi_resets(self.root,160)


if __name__=='__main__':unittest.main()
