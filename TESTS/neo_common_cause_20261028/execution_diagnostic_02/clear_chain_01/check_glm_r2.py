import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'TESTS/global_model_workflow_20261028/release_02/pack'))
import agent_isolation
s=json.loads((HERE/'glm_spec_r2.json').read_text());s['project']=str(HERE/'glm_task_r2')
m=agent_isolation.prepare(s,HERE/'glm_runtime_02');p=agent_isolation.preflight(m['manifest_path']);r=agent_isolation.run_tests(m['manifest_path'])
(HERE/'glm_runtime_02/result.json').write_text(json.dumps({'preflight':p,'tests':r},indent=2)+'\n')
print(json.dumps({'isolation_verified':p['isolation_verified'],'passed':r['passed'],'log':r['tests_log']}))
assert p['isolation_verified'] and 'FULL_CHAIN_COMPILE_PASS' in r['tests_log']
