"""Same-cycle reset replication, isolation and mapped-function guard."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo.system_reset import freeze,original_soc,audit,audit_routed,constrain,BRANCHES,PROFILE


class SystemResetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.files=['tang/rtl/board/ae350_soc.v','tang/boards/neo/console_neo.v',
                    'tang/boards/neo/soft_usb.vh','tang/boards/neo/neo.cst']
        for rel in self.files:
            out=self.root/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,out)

    def test_isolated_reversible_soc_and_consumers(self):
        before={rel:(ROOT/rel).read_bytes() for rel in self.files}
        freeze(self.root)
        self.assertEqual(original_soc(self.root),before[self.files[0]])
        for rel,data in before.items():self.assertEqual((ROOT/rel).read_bytes(),data)
        top=(self.root/self.files[1]).read_text();usb=(self.root/self.files[2]).read_text()
        for i in range(4):self.assertEqual(top.count(f'(vid_reset_branches[{i}])'),1)
        for i in (4,5):self.assertEqual(usb.count(f'vid_reset_branches[{i}] && !rst_usb'),1)
        with self.assertRaises(ValueError):freeze(self.root)
        p=self.root/self.files[0];p.write_text(p.read_text().replace('assign vid_hsel = br_hsel[1]','assign vid_hsel = br_hsel[0]'))
        with self.assertRaises(ValueError):original_soc(self.root)

    def test_missing_consumer_refused_atomically(self):
        p=self.root/self.files[2];p.write_text(p.read_text().replace('usb_msc_port u_usb_msc_port','usb_msc_port unknown'))
        before={rel:(self.root/rel).read_bytes() for rel in self.files}
        with self.assertRaises(ValueError):freeze(self.root)
        self.assertFalse((self.root/PROFILE).exists())
        for rel,data in before.items():self.assertEqual((self.root/rel).read_bytes(),data)

    def test_mapping_rejects_merge_stage_or_reset_change(self):
        names=('vid_hrstn_r',)+tuple('vid_hrstn_'+b for b in BRANCHES)
        parts=[f"DFFCE {name}_s0 (.Q(out{i}),.D(exts_hrstn),.CLK(vid_hclk),.CLEAR(GND),.CE(VCC));\n"
               f"defparam {name}_s0.INIT=1'b0;\n" for i,name in enumerate(names)]
        good='module ae350_soc();\n'+''.join(parts)+'endmodule\n';p=self.root/'net.vg';p.write_text(good)
        self.assertTrue(audit(p)['passed'])
        # syn_keep retains intermediate names and changes Gowin's cell suffix.
        p.write_text(good.replace('_s0','_s1'));self.assertTrue(audit(p)['passed'])
        for bad in (good.replace('out1','out0'),good.replace('.D(exts_hrstn)','.D(vid_hrstn)',1),
                    good.replace('.CLEAR(GND)','.CLEAR(rst)',1),good.replace("INIT=1'b0","INIT=1'b1",1),
                    good.replace(parts[-1],''),good.replace('endmodule',parts[0].replace('_s0','_s1')+'endmodule')):
            p.write_text(bad);self.assertFalse(audit(p)['passed'])

    def test_routed_copies_must_retain_function(self):
        names=('vid_hrstn_r',)+tuple('vid_hrstn_'+b for b in BRANCHES)
        parts=[f"DFFCE \\u_soc/{name}_s1 (\n.D(\\u_soc/exts_hrstn ),.CLK(vid_hclk),.CE(VCC),.CLEAR(GND),.Q(out{i}));\n"
               f"defparam \\u_soc/{name}_s1 .INIT=1'b0;\n" for i,name in enumerate(names)]
        good='\n'.join(parts);p=self.root/'route.vo';p.write_text(good)
        self.assertTrue(audit_routed(p)['passed'])
        for bad in (good.replace('out1','out0'),good.replace('exts_hrstn','bad',1),
                    good.replace('vid_hclk','gpu_clk',1),good.replace("INIT=1'b0","INIT=1'b1",1),
                    good.replace(parts[-1],'')):
            p.write_text(bad);self.assertFalse(audit_routed(p)['passed'])

    def test_old_port_aliases_bound_to_verified_internal_driver_nets(self):
        freeze(self.root)
        names=('vid_hrstn_r',)+tuple('vid_hrstn_'+b for b in BRANCHES)
        net='module ae350_soc();\n'+''.join(
            f"DFFCE {n}_s1 (.Q({n}),.D(exts_hrstn),.CLK(vid_hclk),.CLEAR(GND),.CE(VCC));\n"
            f"defparam {n}_s1.INIT=1'b0;\n" for n in names)+'endmodule\n'
        p=self.root/'net.vg';p.write_text(net)
        cst=self.root/self.files[-1];expected=cst.read_text()
        aliases=('vid_hrstn',)+tuple(f'vid_reset_branches[{i}]' for i in range(6))
        old=expected
        for name,alias in zip(names,aliases):old=old.replace('"u_soc/'+name+'"','"'+alias+'"')
        cst.write_text(old);constrain(self.root,p);self.assertEqual(cst.read_text(),expected)
        constrain(self.root,p);self.assertEqual(cst.read_text(),expected)
        p.write_text(net.replace('.D(exts_hrstn)','.D(bad)',1))
        with self.assertRaises(ValueError):constrain(self.root,p)
        self.assertEqual(cst.read_text(),expected)


if __name__=='__main__':unittest.main()
