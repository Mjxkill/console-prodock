"""Incremental reuse must not cross changed logic, clocks or pin constraints."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo.incremental import freeze,audit,digest


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.ref=Path(temp.name)/'reference';self.build=Path(temp.name)/'candidate'
        board=Path('source/tang/boards/neo');self.board=board
        for root in (self.ref,self.build):
            (root/board).mkdir(parents=True)
            (root/'impl/pnr').mkdir(parents=True)
            (root/'console_neo.vg').write_text('same netlist\n')
            (root/board/'neo.cst').write_text('IO_LOC "clk" V22;\nCLOCK_LOC "clk" BUFG[0] = CLK;\nINS_LOC "q" R1C1[0][A];\n')
            (root/board/'neo.sdc').write_text('create_clock -period 20 [get_ports clk]\n')
        (self.ref/'build.log').write_text('Bitstream generation completed\n')
        (self.ref/'impl/pnr/console_neo.fs').write_bytes(b'bitstream')
        (self.ref/'impl/pnr/cmd.do').write_text('-pn GW5AST-LV138PG484AC1/I0\n')
        for suffix in ('p','pr'):(self.ref/f'impl/pnr/console_neo.{suffix}').write_bytes(b'cache')
        self.manifest()

    def manifest(self):
        (self.ref/'sources.json').write_text(json.dumps({str(p.relative_to(self.ref/'source')):digest(p)
            for p in (self.ref/'source').rglob('*') if p.is_file()}))

    def test_only_locations_may_change_and_real_option_is_checked(self):
        p=self.build/self.board/'neo.cst';p.write_text(p.read_text().replace('R1C1','R2C2'))
        record=freeze(self.ref,self.build)
        cache=self.build/record['cache'];self.assertEqual(cache.read_bytes(),b'cache')
        cmd=self.build/'impl/pnr/cmd.do';cmd.write_text('-inc_pnr '+str(cache)+'\n')
        self.assertTrue(audit(self.build,record)['passed'])
        cmd.write_text('-inc_place '+str(cache)+'\n');self.assertFalse(audit(self.build,record)['passed'])
        cmd.write_text('-inc_pnr '+str(cache)+'\n');cache.write_bytes(b'changed')
        self.assertFalse(audit(self.build,record)['passed'])

    def test_changed_logic_pin_clock_or_timing_is_rejected(self):
        for rel,new in [('console_neo.vg','other netlist'),
                        (str(self.board/'neo.cst'),'IO_LOC "clk" D22;'),
                        (str(self.board/'neo.sdc'),'create_clock -period 40 [get_ports clk]')]:
            p=self.build/rel;original=p.read_bytes();p.write_text(new)
            with self.assertRaises(ValueError):freeze(self.ref,self.build)
            self.assertFalse((self.build/'incremental_reference.pr').exists())
            p.write_bytes(original)

    def test_incomplete_or_changed_reference_is_rejected(self):
        log=self.ref/'build.log';log.write_text('ERROR PNR failed\nBitstream generation completed\n')
        with self.assertRaises(ValueError):freeze(self.ref,self.build)
        log.write_text('Bitstream generation completed\n')
        p=self.ref/self.board/'neo.cst';p.write_text(p.read_text()+'// drift\n')
        with self.assertRaises(ValueError):freeze(self.ref,self.build)
        self.manifest();(self.ref/'impl/pnr/console_neo.pr').write_bytes(b'')
        with self.assertRaises(ValueError):freeze(self.ref,self.build)

    def test_other_device_reference_is_rejected(self):
        (self.ref/'impl/pnr/cmd.do').write_text('-pn GW5AST-LV138PG484AC2/I1\n')
        with self.assertRaises(ValueError):freeze(self.ref,self.build)


if __name__=='__main__':unittest.main()
