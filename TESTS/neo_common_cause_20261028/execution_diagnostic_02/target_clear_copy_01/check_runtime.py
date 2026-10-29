"""Validate compiler, driver and process execution in the exact agent sandbox."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,'/home/michael/.codex/model-workflow')
import agent_isolation
spec=json.loads((HERE/'deepseek_spec_01.json').read_text())
spec['project']=str(HERE/'deepseek_task_01')
spec['tests']=[['/usr/bin/python3','-B','validate.py','--infra']]
m=agent_isolation.prepare(spec,HERE/'runtime_02')
p=agent_isolation.preflight(m['manifest_path'])
r=agent_isolation.run_tests(m['manifest_path'])
(HERE/'runtime_02/result.json').write_text(json.dumps({'preflight':p,'tests':r},indent=2)+'\n')
print(json.dumps({'isolation_verified':p['isolation_verified'],'passed':r['passed'],
                  'scope':'infrastructure compile/execute only; functional bench pending'}))
assert p['isolation_verified'] and r['passed']
