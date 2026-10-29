#!/usr/bin/env python3
"""Execute exact readback functions via AST; no serial modules or hardware."""
import ast,hashlib,json,re,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE/'prodock_valley_benchmark.py'
parsed=ast.parse(source.read_text());functions=[n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name in ('readback_timeout','readback')]
assert len(functions)==2
ns={'re':re,'hashlib':hashlib};exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),ns)
class TX:
    def __init__(self,data=b'0000000 141 142 143\n0000003\n'):self.calls=[];self.data=data
    def run(self,*a):self.calls.append(a);return self.data
class Tests(unittest.TestCase):
    def test_exact_deadlines(self):
        for n,expected in [(1464,240),(32768,240),(62*1024,325),(221180,982),(1048576,4430)]:self.assertEqual(ns['readback_timeout'](n),expected)
    def test_refuses_unbounded_without_any_command(self):
        for n in (0,-1,1048577,221180.0,True,None):
            tx=TX()
            with self.assertRaises(ValueError):ns['readback'](tx,'x','/tmp/mc1-helper',n,'x')
            self.assertEqual(tx.calls,[])
    def test_real_readback_uses_deadline_and_checks_all_bytes(self):
        tx=TX();ns['readback'](tx,'x','/tmp/mc1-helper',3,hashlib.sha256(b'abc').hexdigest());self.assertEqual(tx.calls,[('x','od -b -v /tmp/mc1-helper',240)])
        for size,sha in [(4,hashlib.sha256(b'abc').hexdigest()),(3,'0'*64)]:
            with self.assertRaises(AssertionError):ns['readback'](TX(),'x','/tmp/mc1-helper',size,sha)
        with self.assertRaises(AssertionError):ns['readback'](tx,'x','/tmp/mc1-helper',221180,'x')
        self.assertEqual(tx.calls[-1][-1],982)
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (HERE/'deadline_tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),hardware=False,tests=r.testsRun,manifest_sha256=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
