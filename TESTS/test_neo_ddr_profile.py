"""A Neo adapter override must leave the frozen Pro Dock baseline intact."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_ddr_profile import (ADAPTER, PROFILE, TAGGED_PROFILE, TAGGED_SOURCE,
                               SPLIT_PROFILE, SPLIT_SOURCE, FIFO, FIFO_PROFILE, FIFO_SOURCE,
                               SELECTION, audit, freeze_variant)
from check_ddr_profile import IP_VARIANT, IP_PROFILE, IP_ROOT, IP_DESTINATIONS


class DDRProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = list(json.loads((ROOT/PROFILE).read_text())['files'])
        ip=json.loads((ROOT/IP_PROFILE).read_text())
        files += [IP_PROFILE, *ip['evidence'], *[v['source'] for v in ip['overrides'].values()]]
        for name in files+[PROFILE, TAGGED_PROFILE, TAGGED_SOURCE, SPLIT_PROFILE,
                           SPLIT_SOURCE, FIFO_PROFILE, FIFO_SOURCE]:
            dest = self.root/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, dest)

    def test_default_remains_prodock(self):
        freeze_variant(ROOT, self.root, 'prodock')
        self.assertTrue(audit(self.root)['passed'])
        self.assertEqual((self.root/ADAPTER).read_bytes(), (ROOT/ADAPTER).read_bytes())
        self.assertEqual(json.loads((self.root/SELECTION).read_text())['variant'], 'prodock')

    def test_tagged_copy_is_explicit_and_changes_only_the_adapter(self):
        freeze_variant(ROOT, self.root, 'neo-tagged')
        self.assertTrue(audit(self.root, 'neo-tagged')['passed'])
        self.assertEqual(audit(self.root)['changed'], [ADAPTER])
        self.assertTrue(audit(ROOT)['passed'])

    def test_tagged_profile_cannot_hide_other_ddr_changes(self):
        freeze_variant(ROOT, self.root, 'neo-tagged')
        name = 'tang/rtl/board/ahb_ddr_cdc.v'
        with (self.root/name).open('a') as f:
            f.write('// unexpected change\n')
        self.assertEqual(audit(self.root, 'neo-tagged')['changed'], [name])

    def test_split_variant_does_not_replace_the_l31r8_reference(self):
        original = (self.root/TAGGED_SOURCE).read_bytes()
        freeze_variant(ROOT, self.root, 'neo-tagged-split')
        self.assertTrue(audit(self.root, 'neo-tagged-split')['passed'])
        self.assertEqual(audit(self.root)['changed'], [ADAPTER])
        self.assertEqual((self.root/TAGGED_SOURCE).read_bytes(), original)
        self.assertEqual((self.root/ADAPTER).read_bytes(), (ROOT/SPLIT_SOURCE).read_bytes())
        self.assertTrue(audit(ROOT)['passed'])

    def test_split_override_cannot_change_destination_or_ignore_tampering(self):
        path = self.root/SPLIT_PROFILE
        record = json.loads(path.read_text())
        record['destination'] = 'tang/rtl/board/ae350_soc.v'
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            audit(self.root, 'neo-tagged-split')
        shutil.copyfile(ROOT/SPLIT_PROFILE, path)
        with (self.root/SPLIT_SOURCE).open('a') as f:
            f.write('// changed\n')
        with self.assertRaises(ValueError):
            freeze_variant(self.root, self.root/'bad-copy', 'neo-tagged-split')

    def test_unknown_variant_and_broadened_override_are_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.root, 'unknown')
        path = self.root/TAGGED_PROFILE
        record = json.loads(path.read_text())
        record['destination'] = 'tang/rtl/board/ae350_soc.v'
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            audit(self.root, 'neo-tagged')

    def test_import_hash_is_checked_before_freezing(self):
        with (self.root/TAGGED_SOURCE).open('a') as f:
            f.write('// unexpected change\n')
        with self.assertRaises(ValueError):
            freeze_variant(self.root, self.root/'bad-copy', 'neo-tagged')

    def test_fifo_trial_preserves_adapter_and_shared_source(self):
        freeze_variant(ROOT, self.root, 'neo-fifo-registers')
        self.assertTrue(audit(self.root, 'neo-fifo-registers')['passed'])
        self.assertEqual(audit(self.root)['changed'], [FIFO])
        self.assertEqual((self.root/ADAPTER).read_bytes(), (ROOT/ADAPTER).read_bytes())
        self.assertTrue(audit(ROOT)['passed'])

    def test_fifo_trial_does_not_authorize_an_adapter_override(self):
        profile = self.root/FIFO_PROFILE
        record = json.loads(profile.read_text())
        record['destination'] = ADAPTER
        profile.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            audit(self.root, 'neo-fifo-registers')

    def test_ddr6_is_explicit_and_preserves_shared_ddr_logic(self):
        freeze_variant(ROOT,self.root,IP_VARIANT)
        self.assertTrue(audit(self.root,IP_VARIANT)['passed'])
        self.assertFalse(audit(self.root,'neo-fifo-registers')['passed'])
        self.assertTrue(audit(ROOT)['passed'])
        self.assertEqual((self.root/ADAPTER).read_bytes(),(ROOT/ADAPTER).read_bytes())
        self.assertEqual((self.root/FIFO).read_bytes(),(ROOT/FIFO_SOURCE).read_bytes())

    def test_ddr6_still_checks_arbitration_and_generated_parameters(self):
        freeze_variant(ROOT,self.root,IP_VARIANT)
        for name in ['tang/rtl/board/ddr_gpu_arb.v',IP_DESTINATIONS['gwmc_param.v']]:
            with (self.root/name).open('a') as f:
                f.write('// altered\n')
        self.assertEqual(set(audit(self.root,IP_VARIANT)['changed']),
                         {'tang/rtl/board/ddr_gpu_arb.v',IP_DESTINATIONS['gwmc_param.v']})

    def test_ddr6_changed_ip_source_is_rejected_before_freezing(self):
        with (self.root/IP_ROOT/'ddr3_standalone.v').open('a') as f:
            f.write('// altered\n')
        with self.assertRaises(ValueError):
            freeze_variant(self.root,self.root/'bad-copy',IP_VARIANT)

    def test_ddr6_override_cannot_expand_to_other_logic(self):
        p=self.root/IP_PROFILE;r=json.loads(p.read_text())
        r['overrides'][ADAPTER]=dict(source=IP_ROOT+'/ddr3_standalone.v',sha256='0'*64)
        p.write_text(json.dumps(r))
        with self.assertRaises(ValueError):
            audit(self.root,IP_VARIANT)

    def test_ddr6_rejects_unverified_generation_or_changed_memory_width(self):
        p=self.root/IP_ROOT/'generation.json';r=json.loads(p.read_text())
        r['generated_parameters']['DQ_WIDTH']='16';p.write_text(json.dumps(r))
        with self.assertRaises(ValueError):
            freeze_variant(self.root,self.root/'bad-copy',IP_VARIANT)

    def test_system_reset_profile_preserves_and_cannot_bypass_ddr_baseline(self):
        from neo.system_reset import freeze, PROFILE as RESET_PROFILE
        import hashlib
        freeze_variant(ROOT,self.root,IP_VARIANT)
        for rel in ('tang/boards/neo/console_neo.v','tang/boards/neo/soft_usb.vh',
                    'tang/boards/neo/neo.cst'):
            shutil.copyfile(ROOT/rel,self.root/rel)
        freeze(self.root)
        soc='tang/rtl/board/ae350_soc.v'
        self.assertEqual(audit(self.root,IP_VARIANT)['changed'],[soc])
        self.assertTrue(audit(self.root,IP_VARIANT,system_reset=True)['passed'])
        p=self.root/soc;p.write_text(p.read_text()+'\n// unrelated change\n')
        self.assertEqual(audit(self.root,IP_VARIANT,system_reset=True)['changed'],[soc])
        # Even a modified profile's after-hash cannot exempt unrelated SoC edits.
        p=self.root/RESET_PROFILE;r=json.loads(p.read_text())
        r['changed'][soc]['after']=hashlib.sha256((self.root/soc).read_bytes()).hexdigest()
        p.write_text(json.dumps(r))
        self.assertEqual(audit(self.root,IP_VARIANT,system_reset=True)['changed'],[soc])


if __name__ == '__main__':
    unittest.main()
