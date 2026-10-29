"""Protected artifact/scope contract; no rebuilding and no physical I/O."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest


class Tests(unittest.TestCase):
    def test_inputs_preserved(self):
        manifest=json.loads(Path('input_manifest.json').read_text())
        for name,entry in manifest.items():
            data=Path(name).read_bytes()
            self.assertEqual(len(data),entry['bytes'],name)
            self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'],name)
    def test_report_scope(self):
        run=subprocess.run(['/usr/bin/python3','-B','audit.py'],capture_output=True,text=True,timeout=40)
        self.assertEqual(run.returncode,0,run.stderr)
        report=json.loads(run.stdout)
        self.assertIs(report['hardware_access'],False)
        self.assertIs(report['hardware_validated'],False)
        self.assertIs(report['r4_post_route_verified'],False)
        self.assertGreaterEqual(len(report['checks']),6)
        for item in report['checks']:
            self.assertIs(type(item['passed']),bool)
            self.assertTrue(item['name'] and item['evidence'] and item['scope'])
        self.assertTrue(report['limitations'])
        self.assertIsInstance(report['findings'],list)
    def test_documented_limits(self):
        doc=Path('REPORT.md').read_text()
        self.assertIn('R3',doc)
        self.assertIn('R4',doc)
        self.assertLessEqual(len(Path('audit.py').read_text().splitlines()),1000)

if __name__=='__main__':unittest.main()
