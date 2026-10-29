"""Clock-stop/reset behavior and strictly scoped Neo DDR startup generation."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo.ddr_startup import freeze,original_soc,SOC,RTL
from neo.system_reset import freeze as split_reset,original_soc as undo_split
from neo.build_ddr_ip import generator_options,parameters
from check_ddr_profile import (IP_PROFILES,IP300_VARIANT,PROFILE,SELECTION,
                               IP325_VARIANT,IP400_VARIANT,PLL_CHANGES,audit,freeze_variant,
                               hynix_efr_clock_range)


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        files=list(json.loads((ROOT/PROFILE).read_text())['files'])+[PROFILE,RTL,
            'tang/boards/neo/console_neo.v','tang/boards/neo/neo.cst','tang/boards/neo/neo.sdc',
            'tang/boards/neo/soft_usb.vh','tang/boards/neo/ddr_fifo_registers.json',
            'tang/boards/neo/ddr_dcfifo_registers.v']
        profile,_=IP_PROFILES[IP300_VARIANT]
        ip=json.loads((ROOT/profile).read_text())
        files += [profile,*ip['evidence'],*[v['source'] for v in ip['overrides'].values()]]
        for rel in files:
            dest=self.root/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/rel,dest)

    def test_300_profile_and_composed_reset_edits_are_scoped(self):
        before=(ROOT/SOC).read_bytes()
        freeze_variant(ROOT,self.root,IP300_VARIANT)
        freeze(self.root)
        self.assertEqual(original_soc(self.root),before)
        self.assertTrue(audit(self.root,IP300_VARIANT,ddr_startup=True)['passed'])
        self.assertFalse(audit(self.root,IP300_VARIANT)['passed'])
        split_reset(self.root)
        self.assertEqual(original_soc(self.root,undo_split(self.root)),before)
        self.assertTrue(audit(self.root,IP300_VARIANT,system_reset=True,ddr_startup=True)['passed'])
        self.assertTrue(audit(ROOT)['passed'])
        p=self.root/RTL;p.write_text(p.read_text().replace('HOLD_BITS = 10','HOLD_BITS = 1'))
        self.assertFalse(audit(self.root,IP300_VARIANT,system_reset=True,ddr_startup=True)['passed'])

    def test_only_explicit_period_override_allowed(self):
        profile,iproot=IP_PROFILES[IP300_VARIANT]
        baseline=parameters((ROOT/'tang/rtl/board/ddr3_standalone_32b/cfg/gwmc_param.v').read_text())
        self.assertEqual(generator_options(baseline)['Memory_Clock'],'400')
        self.assertEqual(generator_options(baseline,300)['Memory_Clock'],'300')
        self.assertEqual(generator_options(baseline,400)['Memory_Clock'],'400')
        with self.assertRaises(ValueError):generator_options(baseline,401)
        p=self.root/iproot/'generation.json';record=json.loads(p.read_text())
        record['generated_parameters']['tREFI']='10400000';p.write_text(json.dumps(record))
        with self.assertRaises(ValueError):freeze_variant(self.root,self.root/'bad',IP300_VARIANT)

    def check_pll_profile(self,variant):
        freeze_variant(ROOT,self.root,variant)
        self.assertTrue(audit(self.root,variant)['passed'])
        self.assertTrue(audit(ROOT)['passed'])
        source=next(iter(PLL_CHANGES[variant]))
        profile,iproot=IP_PROFILES[variant]
        p=self.root/iproot/Path(source).name
        text=p.read_text();p.write_text(text+'\n// undeclared change\n')
        with self.assertRaises(ValueError):audit(self.root,variant)
        p.write_text(text)
        cfg=self.root/'tang/rtl/board/ddr3_standalone_32b/cfg/gwmc_param.v'
        cfg.write_text(cfg.read_text().replace('parameter tCK =','parameter BAD_tCK ='))
        # Exact generated parameter file hashes must remain part of the audit.
        if audit(self.root,variant)['passed']:
            cfg.write_text(cfg.read_text()+'\n// changed\n')
        self.assertFalse(audit(self.root,variant)['passed'])

    def test_325_pll_and_initialization_factor_are_coupled(self):
        self.check_pll_profile(IP325_VARIANT)

    def test_400_changes_only_memory_divider(self):
        self.check_pll_profile(IP400_VARIANT)

    def test_slower_ddr_clock_is_not_automatically_in_spec(self):
        params={'CL':'6','CWL':'5'}
        for clock in (300,300.03,401,0):
            with self.subTest(clock=clock):
                self.assertFalse(hynix_efr_clock_range(params,clock)['passed'])
        for clock in (325,400):
            self.assertTrue(hynix_efr_clock_range(params,clock)['passed'])
        self.assertFalse(hynix_efr_clock_range({'CL':'7','CWL':'6'},400)['passed'])

    def test_simulated_startup_faults_across_clock_ratios(self):
        binary=self.root/'sim'
        base=Path('/tmp/console-usb-sim-tools/extracted/usr')
        iv=shutil.which('iverilog')
        compiler=[iv] if iv else [str(base/'bin/iverilog'),'-B',str(base/'lib/x86_64-linux-gnu/ivl')]
        runtime=shutil.which('vvp') or str(base/'bin/vvp')
        subprocess.run(compiler+['-g2012','-s','neo_ddr_startup_tb','-o',str(binary),
                        str(ROOT/RTL),str(ROOT/'TESTS/rtl/neo_ddr_startup_tb.sv')],check=True,
                       capture_output=True,text=True)
        for half in ('6.25','6.243','6.257','11.731'):
            run=subprocess.run([runtime,str(binary),'+CPU_HALF='+half],check=True,
                               capture_output=True,text=True,timeout=10)
            self.assertIn('PASS DDR startup',run.stdout)


if __name__=='__main__':unittest.main()
