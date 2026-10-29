#!/usr/bin/env python3
"""Independent oracle: real retained bitstream and external ownership reference."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import festival_trial as t
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
REFERENCE=ROOT/'tang/boards/prodock/reference.json'
class Tests(unittest.TestCase):
    def test_identity_against_external_reference_and_real_bitstream(self):
        external=json.loads(REFERENCE.read_text());expected=external['bitstream_sha256']
        self.assertEqual(t.digest(ROOT/external['bitstream'])['sha256'],expected)
        self.assertEqual((HERE/'fpga_reference.json').read_bytes(),REFERENCE.read_bytes())
        self.assertEqual(t.FPGA_SHA,expected);self.assertEqual(t.preflight(HERE)['fpga_sha256'],expected)
    def test_jointly_wrong_constant_and_manifest_still_rejected(self):
        bad='fbbea9c357d0c4d5b33c3c4a7e54f9fd0ff8e31cc3fad1ac9dc1771f8e8cba5f'
        original=t.json.loads
        def changed(raw):
            value=original(raw)
            if isinstance(value,dict) and value.get('controller_revision')==6:value['fpga_sha256']=bad
            return value
        with patch.object(t,'FPGA_SHA',bad),patch.object(t.json,'loads',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'independently retained'):t.preflight(HERE)
    def test_only_wrong_manifest_rejected(self):
        original=t.json.loads
        def changed(raw):
            value=original(raw)
            if isinstance(value,dict) and value.get('controller_revision')==6:value['fpga_sha256']='0'*64
            return value
        with patch.object(t.json,'loads',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'Wrong retained reference'):t.preflight(HERE)
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (HERE/'external_anchor_tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,manifest_sha256=t.digest(HERE/'manifest.json')['sha256'],controller_sha256=t.digest(HERE/'festival_trial.py')['sha256'],external_reference_sha256=t.digest(REFERENCE)['sha256'],test_sha256=t.digest(Path(__file__))['sha256']),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
