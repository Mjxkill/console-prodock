#!/usr/bin/env python3
"""Check the frozen task runtime without any model or provider credential."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'global_model_workflow_20261028/release_02/pack'))
import agent_isolation

spec=json.loads((HERE/'deepseek_task_r3.json').read_text())
spec['project']=str(HERE/'task_r3')
manifest=agent_isolation.prepare(spec,HERE/'runtime_check_r3')
preflight=agent_isolation.preflight(manifest['manifest_path'])
test=agent_isolation.run_tests(manifest['manifest_path'])
result=dict(preflight=preflight,baseline=test)
(HERE/'runtime_check_r3/result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
assert preflight['isolation_verified']
# The unfinished bench must execute and report its intentional failure.
assert 'CASE seed=1 fault=0' in test['tests_log'], 'Full bench failed to compile/run'
