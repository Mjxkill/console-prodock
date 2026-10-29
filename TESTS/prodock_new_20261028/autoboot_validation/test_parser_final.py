"""Reuse both protected suites unchanged against the final supervised source."""
import importlib.util
from pathlib import Path
import sys
import unittest
import boot_log
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H/'project_r2'))
import test_boot_log as first
first.m=boot_log
import test_counterexamples as second
second.m=boot_log
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(first),unittest.defaultTestLoader.loadTestsFromModule(second)])
if __name__=='__main__':raise SystemExit(not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful())
