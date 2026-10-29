"""Prevalidate full Verilator harness inside actual isolation before delegation."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'TESTS/global_model_workflow_20261028/release_02/pack'))
import agent_isolation
spec=json.loads((HERE/'firmware_spec_01.json').read_text())
spec['project']=str(HERE/'firmware_task_01')
spec['tests']=[['/usr/bin/python3','-B','validate.py','--infra']]
m=agent_isolation.prepare(spec,HERE/'firmware_runtime_02')
p=agent_isolation.preflight(m['manifest_path'])
r=agent_isolation.run_tests(m['manifest_path'])
(HERE/'firmware_runtime_02/result.json').write_text(json.dumps({'preflight':p,'tests':r},indent=2)+'\n')
print(json.dumps({'isolation_verified':p['isolation_verified'],'passed':r['passed'],'tests_log':r['tests_log']}))
assert p['isolation_verified'] and r['passed']
