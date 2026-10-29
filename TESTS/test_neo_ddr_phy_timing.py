"""Do not let the vendor PHY exception exempt application logic."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo.ddr_phy_timing import clock_fanout,FAST_NET,PREFIX


class PhyClockTests(unittest.TestCase):
    def fixture(self):
        cells=[('PLL','u_soc/u_pll_ddr3/u_pll/PLL_inst','CLKOUT2')]
        for kind,pin,count in [('DDRDLL','CLKIN',1),('CLKDIV','HCLKIN',1),
                               ('OSER8_MEM','FCLK',40),('IDES8_MEM','FCLK',32),
                               ('OSER8','FCLK',25),('DQS','FCLK',4)]:
            cells += [(kind,PREFIX+kind+str(i),pin) for i in range(count)]
        return '\n'.join(f'{kind} \\{name} (.{pin}(\\{FAST_NET} ));' for kind,name,pin in cells)

    def test_vendor_only_fanout(self):
        self.assertTrue(clock_fanout(self.fixture())['passed'])

    def test_console_endpoint_cannot_be_hidden(self):
        text=self.fixture().replace(PREFIX+'OSER80','u_gpu/serializer0')
        self.assertFalse(clock_fanout(text)['passed'])
        text=self.fixture()+f'\nDFFCE extra (.CLK(\\{FAST_NET} ));'
        self.assertFalse(clock_fanout(text)['passed'])

    def test_alias_and_missing_macro_rejected(self):
        text=self.fixture()+f'\nassign other_clock=\\{FAST_NET} ;'
        self.assertFalse(clock_fanout(text)['passed'])
        self.assertFalse(clock_fanout(self.fixture().replace('DQS \\'+PREFIX+'DQS0','DFFCE \\'+PREFIX+'DQS0'))['passed'])


if __name__=='__main__':unittest.main()
