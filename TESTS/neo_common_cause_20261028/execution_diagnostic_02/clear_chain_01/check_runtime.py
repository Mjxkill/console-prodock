#!/usr/bin/env python3
"""Prevalidate the complete isolated harness before calling any paid model."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'TESTS/global_model_workflow_20261028/release_02/pack'))
import agent_isolation

name = sys.argv[1] if len(sys.argv) == 2 else 'deepseek'
assert name in ('deepseek', 'glm')
spec = json.loads((HERE / f'{name}_spec.json').read_text())
spec['project'] = str(HERE / f'{name}_task')
manifest = agent_isolation.prepare(spec, HERE / f'{name}_runtime_01')
preflight = agent_isolation.preflight(manifest['manifest_path'])
tests = agent_isolation.run_tests(manifest['manifest_path'])
result = {'preflight': preflight, 'tests': tests}
(HERE / f'{name}_runtime_01/result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert preflight['isolation_verified']
assert 'FULL_CHAIN_COMPILE_PASS' in tests['tests_log'], 'Full harness did not compile inside box'
assert 'BASELINE_PASS' in tests['tests_log'], 'Healthy baseline did not execute inside box'
