"""Reject stale/partial constraints instead of declaring false timing closure."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo.timing_closure import compensate, source_latencies, freeze, audit, refresh, select_hdmi_clock, auto_hdmi_clock, select_hdmi_placement, zero_clock_origins, BOUND, ORIGIN_COMMAND, sections, focused_hdmi_reports, global_clock_routes


def report(latencies, missing=None, negative=False):
    result=''
    for i,kind in enumerate(('Setup','Hold','Recovery','Removal'),1):
        result+=f'3.3.{i} {kind} Analysis Report\n'
        for clock,latency in latencies.items():
            # Fast corner deliberately different: must never replace slow tCL.
            value=latency if kind in ('Setup','Recovery') else '99.000'
            result+=(f'Path Summary:\nLaunch Clk : {clock}:[R]\nLatch Clk : {clock}:[R]\n'
                     f'Data Arrival Path:\n 0.0 {value} tCL RR 1 PLL node\n'
                     f'Data Required Path:\n 0.0 {value} tCL RR 1 PLL node\nPath Statistics:\n')
        if kind in ('Recovery','Removal'):
            for ch in range(3):
                for clock in ('vid_pclk:[R]','vid_clk5x:[R]','vid_clk5x:[F]'):
                    if (kind,ch,clock)==missing:continue
                    result+=(f'Path Summary:\nSlack : {"-0.1" if negative else "0.5"}\n'
                             f'From : u_hdmi/g_reset[{ch}].reset_sync_fall_s1\n'
                             f'To : u_hdmi/g_ser[{ch}].u_ser\n'
                             f'Launch Clk : vid_pclk:[F]\nLatch Clk : {clock}\n')
    return result


class ClosureTests(unittest.TestCase):
    latencies=dict(clk50='0.000',bus80_clk='0.000',ddr3_sys_clk='0.000',
                   vid_pclk='5.598',vid_clk5x='5.598',PHY_CLKOUT='9.066')

    def test_two_directions_and_corner(self):
        sdc=(ROOT/'tang/boards/neo/neo.sdc').read_text()
        actual=source_latencies(report(self.latencies))
        self.assertEqual(actual,self.latencies)
        changed,entries=compensate(sdc,actual)
        bounds={(e['source'],e['sink']):e['sdc_limit_ns'] for e in entries}
        self.assertEqual(bounds['PHY_CLKOUT','bus80_clk'],'17.066')
        self.assertEqual(bounds['bus80_clk','PHY_CLKOUT'],'-1.066')
        untouched=lambda s:[l for l in s.splitlines() if not l.startswith('set_max_delay ')]
        self.assertEqual(untouched(sdc),untouched(changed))

    def test_missing_or_changed_constraint_rejected(self):
        sdc=(ROOT/'tang/boards/neo/neo.sdc').read_text()
        with self.assertRaises(ValueError):compensate(sdc,dict(clk50='0'))
        with self.assertRaises(ValueError):compensate(sdc.replace('set_max_delay 8','set_max_delay 9',1),self.latencies)
        with self.assertRaises(ValueError):compensate(sdc+'\nset_max_delay 8 -from [get_clocks {clk50}] -to [get_clocks {clk50}]\n',self.latencies)

    def test_nested_focused_reports_are_not_lost(self):
        original=report(self.latencies)
        nested=original
        for i,kind in ((3,'Recovery'),(4,'Removal')):
            label=f'3.3.{i} {kind} Analysis Report\n'
            nested=nested.replace(label,label+f'3.3.{i}.1 {kind} Analysis Report[1]\n')
        self.assertEqual({k:len(b) for k,b in sections(original)},
                         {k:len(b) for k,b in sections(nested)})
        self.assertEqual(source_latencies(original),source_latencies(nested))

    def test_frozen_profile_and_postroute_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';board=source/'tang/boards/neo';board.mkdir(parents=True)
            for name in ('neo.cst','neo.sdc','console_neo.v'):
                shutil.copy2(ROOT/'tang/boards/neo'/name,board/name)
            tr=root/'reference.tr';tr.write_text(report(self.latencies))
            freeze(source,tr)
            self.assertTrue(audit(source,tr)['passed'])
            self.assertIn('DCE u_video_fast',(board/'console_neo.v').read_text())
            self.assertNotIn('DHCE u_video_fast',(board/'console_neo.v').read_text())
            cst=(board/'neo.cst').read_text()
            self.assertIn('CLOCK_LOC "clk48" BUFG[4] = CLK;',cst)
            self.assertEqual(cst.count('reset_sync_fall_s1" R'),3)
            with self.assertRaises(ValueError):freeze(source,tr)
            changed=dict(self.latencies,PHY_CLKOUT='8.966')
            tr.write_text(report(changed))
            self.assertFalse(audit(source,tr)['passed'])

            old_top=(board/'console_neo.v').read_bytes()
            old_cst=(board/'neo.cst').read_bytes()
            refresh(source,tr)
            self.assertTrue(audit(source,tr)['passed'])
            self.assertEqual(old_top,(board/'console_neo.v').read_bytes())
            self.assertEqual(old_cst,(board/'neo.cst').read_bytes())
            select_hdmi_clock(source,12)
            self.assertTrue(audit(source,tr)['passed'])
            self.assertEqual((board/'neo.cst').read_bytes(),old_cst.replace(
                b'"clk5x" BUFG[4]',b'"clk5x" BUFG[12]'))
            with self.assertRaises(ValueError):select_hdmi_clock(source,7)
            auto_hdmi_clock(source)
            self.assertTrue(audit(source,tr)['passed'])
            self.assertIn('CLOCK_LOC "clk48" BUFG[4] = CLK;',(board/'neo.cst').read_text())
            with self.assertRaises(ValueError):auto_hdmi_clock(source)
            tr.write_text(report(self.latencies,missing=('Removal',2,'vid_clk5x:[F]')))
            self.assertFalse(audit(source,tr)['passed'])
            tr.write_text(report(self.latencies,negative=True))
            self.assertFalse(audit(source,tr)['passed'])

    def test_characterized_site_preserves_other_clocks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);board=root/'tang/boards/neo';board.mkdir(parents=True)
            for name in ('neo.cst','neo.sdc','console_neo.v'):
                shutil.copy2(ROOT/'tang/boards/neo'/name,board/name)
            tr=root/'reference.tr';tr.write_text(report(self.latencies))
            freeze(root,tr)
            old_top=(board/'console_neo.v').read_bytes();old_sdc=(board/'neo.sdc').read_bytes()
            select_hdmi_placement(root,'pg9-c181')
            self.assertEqual((board/'console_neo.v').read_bytes(),old_top)
            self.assertEqual((board/'neo.sdc').read_bytes(),old_sdc)
            self.assertFalse(audit(root,tr)['passed'])
            tr.write_text(tr.read_text()+'\n 0.0 0.0 tINS RR 1 PG[9] u_video_fast/CLKOUT\n')
            self.assertTrue(audit(root,tr)['passed'])
            cst=(board/'neo.cst').read_text()
            self.assertIn('INS_LOC "u_video_fast" PG[9];',cst)
            self.assertIn('CLOCK_LOC "clk48" BUFG[4] = CLK;',cst)
            self.assertIn('reset_sync_fall_s1" R102C181[2][A]',cst)
            (board/'neo.cst').write_text(cst.replace('PG[9]','PG[8]'))
            self.assertFalse(audit(root,tr)['passed'])

    def test_secondary_clock_requires_real_primary_allocation(self):
        for choice in ('sg0-c150','sg0-c160'):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);board=root/'tang/boards/neo';board.mkdir(parents=True)
                for name in ('neo.cst','neo.sdc','console_neo.v'):
                    shutil.copy2(ROOT/'tang/boards/neo'/name,board/name)
                tr=root/'reference.tr';tr.write_text(report(self.latencies))
                freeze(root,tr);select_hdmi_placement(root,choice)
                tr.write_text(tr.read_text()+'\n 0.0 0.0 tINS RR 1 SG[0] u_video_fast/CLKOUT\n')
                self.assertFalse(audit(root,tr)['passed'])
                profile=json.loads((board/'timing_closure.json').read_text())
                routes='6. Global Clock Signals\n'+''.join(
                    net+' | PRIMARY | PBR3\n' for net in profile['required_primary_clocks'])+'7. Pinout\n'
                tr.with_suffix('.rpt.txt').write_text(routes)
                self.assertTrue(audit(root,tr)['passed'])
                gao=routes.replace('6. Global','7. Global').replace('7. Pinout','8. Pinout')
                tr.with_suffix('.rpt.txt').write_text(gao)
                self.assertTrue(audit(root,tr)['passed'])
                tr.with_suffix('.rpt.txt').write_text(routes.replace('clk_d | PRIMARY','clk_d | LW'))
                self.assertFalse(audit(root,tr)['passed'])
                for bad in ('',gao.replace('8. Pinout',''),
                            gao.replace('clk_d | PRIMARY | PBR3','clk_d | PRIMARY'),
                            gao+gao):
                    tr.with_suffix('.rpt.txt').write_text(bad)
                    self.assertFalse(audit(root,tr)['passed'])

    def test_global_routes_accept_gao_numbering_and_reject_partial_reports(self):
        # Actual report format: a net can be on PRIMARY and HCLK together.
        body=('  -------------------------------------------\n'
              '  Signal | Global Clock | Location\n'
              '  -------------------------------------------\n'
              '  clk_d | PRIMARY | PTR0 PTR3 PBR0 PBR2 PBR3\n'
              '  fclk_960m | PRIMARY | PBR3\n'
              '  gpu_debug_state[48]| LW | -\n'
              '  fclk_960m | HCLK | BANK3_HCLK0\n'
              '  ===========================================\n')
        expected=[('clk_d','PRIMARY','PTR0 PTR3 PBR0 PBR2 PBR3'),
                  ('fclk_960m','PRIMARY','PBR3'),('gpu_debug_state[48]','LW','-'),
                  ('fclk_960m','HCLK','BANK3_HCLK0')]
        old='6. Global Clock Signals\n'+body+'7. Pinout by Port Name\n'
        new='4. GAO Resource Usage Summary\n...\n7. Global Clock Signals\n'+body+'8. Pinout by Port Name\n'
        self.assertEqual(global_clock_routes(old),expected)
        self.assertEqual(global_clock_routes(new),expected)
        for bad in ('',new+new,new.replace('8. Pinout by Port Name',''),
                    new.replace('8. Pinout','9. Pinout'),
                    new.replace('gpu_debug_state[48]| LW | -','gpu_debug_state[48]| LW'),
                    new.replace('| LW |','| UNKNOWN |'),
                    new.replace('  gpu_debug_state[48]| LW | -\n','unparsed content\n'),
                    new.replace(body,'\n'),
                    new.replace('  fclk_960m | HCLK | BANK3_HCLK0','  fclk_960m | PRIMARY | PBR0')):
            with self.subTest(report=bad),self.assertRaises(ValueError):global_clock_routes(bad)

    def test_zero_origins_keep_budget_phase_and_exceptions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);board=root/'tang/boards/neo';board.mkdir(parents=True)
            for name in ('neo.cst','neo.sdc','console_neo.v'):
                shutil.copy2(ROOT/'tang/boards/neo'/name,board/name)
            tr=root/'reference.tr';tr.write_text(report(self.latencies))
            freeze(root,tr)
            before=(board/'neo.sdc').read_text()
            zero_clock_origins(root)
            after=(board/'neo.sdc').read_text()
            self.assertEqual(len(list(BOUND.finditer(after))),14)
            self.assertTrue(all(m[1]=='8' for m in BOUND.finditer(after)))
            self.assertIn(ORIGIN_COMMAND,after)
            fixed=lambda s:[l for l in s.splitlines() if l.startswith(('create_','set_false_path','set_clock_groups'))]
            self.assertEqual(fixed(before),fixed(after))
            self.assertFalse(audit(root,tr)['passed'])
            tr.write_text(report({k:'0.000' for k in self.latencies}))
            self.assertTrue(audit(root,tr)['passed'])
            with self.assertRaises(ValueError):zero_clock_origins(root)
            with self.assertRaises(ValueError):refresh(root,tr)
            focused_hdmi_reports(root)
            new=(board/'neo.sdc').read_text()
            self.assertIn('report_timing -recovery -max_paths 10000',new)
            self.assertIn('report_timing -removal -max_paths 10000',new)
            self.assertEqual(new.count('-to [get_pins {u_hdmi/g_ser['),2)
            with self.assertRaises(ValueError):focused_hdmi_reports(root)


if __name__=='__main__':unittest.main()
