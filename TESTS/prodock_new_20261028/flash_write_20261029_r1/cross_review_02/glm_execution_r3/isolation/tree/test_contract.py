"""Output/immutability contract; not a quality or correctness score."""
import hashlib,json,unittest
from pathlib import Path
import review_tests
class Contract(unittest.TestCase):
    def test_actual_cases_exist(self):
        suite=unittest.defaultTestLoader.loadTestsFromModule(review_tests)
        self.assertGreaterEqual(suite.countTestCases(),6)
    def test_frozen_sources(self):
        for name,digest in json.loads(Path('SOURCE_HASHES.json').read_text()).items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(),digest,name)
    def test_limits_and_report(self):
        for name in ('review_tests.py','review_schemas.py','review_tail.py'):
            self.assertLessEqual(len(Path(name).read_bytes().splitlines()),1000)
        result=json.loads(Path('findings.json').read_text())
        self.assertIs(result['hardware_access'],False)
        self.assertNotEqual(result.get('status'),'pending')
        self.assertGreater(len(Path('REPORT.md').read_text()),300)
if __name__=='__main__':unittest.main()
