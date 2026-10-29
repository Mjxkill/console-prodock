import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo.gpu_replication import audit

BASE="""INV \\u_accel/inv_reset  (.I(resetn),.O(reset));
INV \\u_accel/inv_ce  (.I(active),.O(enable));
DFFRE \\u_accel/v1_select_s0  (
 .Q(original),.D(d),.CLK(clk),.CE(enable),.RESET(reset)
);
defparam \\u_accel/v1_select_s0 .INIT=1'b0;
"""
COPY="""DFFRE \\u_accel/gowin_replicate_reg_v1_select_1  (
 .Q(copy_q),.D(d),.CLK(clk),.CE(enable),.RESET(reset)
);
defparam \\u_accel/gowin_replicate_reg_v1_select_1 .INIT=1'b0;
"""


class ReplicationTests(unittest.TestCase):
    def check(self,text):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'mapped.vo';path.write_text(text)
            return audit(path)

    def test_no_copy_and_identical_copy(self):
        self.assertTrue(self.check(BASE)['passed'])
        result=self.check(BASE+COPY)
        self.assertTrue(result['passed']);self.assertEqual(result['checked_copies'],1)

    def test_lost_inversions_and_other_changes_fail(self):
        for old,new in [('CE(enable)','CE(active)'),('RESET(reset)','RESET(resetn)'),
                        ('.D(d)','.D(other)'),('.CLK(clk)','.CLK(other)'),
                        (".INIT=1'b0",".INIT=1'b1"),('DFFRE','DFFCE')]:
            self.assertFalse(self.check(BASE+COPY.replace(old,new))['passed'],(old,new))
        self.assertFalse(self.check(COPY)['passed'])

    def test_equivalent_buffered_polarities(self):
        buffers="""INV inv2 (.I(resetn),.O(reset2)
);
BUF buf1 (.I(enable),.O(enable2)
);
"""
        self.assertTrue(self.check(BASE+buffers+COPY.replace('CE(enable)','CE(enable2)').replace('RESET(reset)','RESET(reset2)'))['passed'])


if __name__=='__main__':unittest.main()
