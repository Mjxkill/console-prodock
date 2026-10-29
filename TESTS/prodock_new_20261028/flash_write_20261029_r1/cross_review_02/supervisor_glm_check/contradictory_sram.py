"""Reproduce a contradictory re-signed SRAM proof using the true producer.
No hardware: imports the existing fake-boundary producer test unchanged.
This changes both the result and root attestation SHA deliberately, and does
not establish a natural run_session path that can produce the contradiction.
"""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / 'corrected_r2'))
import test_producer_schema as producer_test

original = producer_test.writer.prepare
rows = []

def resign_and_prepare(path, digest, out, *, root):
    request = json.loads(path.read_text())
    result_path = Path(request['sram_result']['path'])
    result = json.loads(result_path.read_text())
    assert result['passed'] is True and result['returncode'] == 0
    result['returncode'] = 1
    result_path.write_text(json.dumps(result) + '\n')
    request['sram_result']['sha256'] = producer_test.sha(result_path)
    acceptance_path = Path(request['acceptance']['path'])
    acceptance = json.loads(acceptance_path.read_text())
    acceptance['sram_result_sha256'] = request['sram_result']['sha256']
    acceptance_path.write_text(json.dumps(acceptance) + '\n')
    request['acceptance']['sha256'] = producer_test.sha(acceptance_path)
    path.write_text(json.dumps(request) + '\n')
    plan = original(path, producer_test.sha(path), out, root=root)
    rows.append({'actual_producer_initial_passed': True,
                 'initial_returncode': 0, 'mutated_returncode': 1,
                 'root_attestation_resigned': True,
                 'contradiction_accepted_by_prepare': bool(plan)})
    return plan

with patch.object(producer_test.writer, 'prepare', side_effect=resign_and_prepare):
    case = producer_test.ActualSchema('test_real_sram_report_and_readonly_report_are_consumable')
    case.debug()
print(json.dumps({'hardware_access': False, 'runs': rows,
  'limit': 'Deliberately re-signed proof only; no natural producer path shown.'}, indent=2))
