#!/usr/bin/env python3
"""Read immutable run02 evidence; no debugger, process or board interaction."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BOARD = ROOT / 'TESTS/neo_common_cause_20261028/root_microdma_board_02'
FW = HERE.parent / 'microdma_r1'
RTL = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local/source'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze():
    spec = importlib.util.spec_from_file_location('journal_decoder', FW / 'decode_journal.py')
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    result = json.loads((BOARD / 'result.json').read_text())
    decoded = decoder.decode((BOARD / 'journal.bin').read_bytes())
    h = decoded['header']
    raw = re.findall(r'^MICRODMA_GPU ([^\n]+)$', (BOARD / 'microdma.log').read_text(), re.M)
    if len(raw) != 1:
        raise ValueError('Expected exactly one final GPU register read')
    gpu = [int(value, 16) for value in raw[0].split()]
    if len(gpu) != 14 or gpu[0] != 0x424c5432:
        raise ValueError('Wrong final register span or GPU identity')
    if result['firmware_sha256'] != sha(FW / 'build_02/microdma.bin'):
        raise ValueError('Board payload does not match build02')
    expected = [(0x12000000 + 4*i) ^ 0xa5396c17 for i in range(32)]
    facts = {
        'cpu_seed_words_exact': sum(a == b for a, b in zip(decoded['images']['seed'], expected)),
        'after_target_words_exact': sum(a == b for a, b in zip(decoded['images']['target'], expected)),
        'seed_compared_words': h['seed_compared_words'],
        'target_compared_words': h['target_compared_words'],
        'clear_compared_words': h['clear_compared_words'],
        'cpu_phase': h['phase'], 'cpu_result': h['result'],
        'cpu_returned_to_parking_rom': 'MICRODMA_PC pc (/32): 0x80000004' in (BOARD / 'microdma.log').read_text(),
        'done_target': h['done_target'], 'done_at_clear_timeout': h['done_clear'],
        'later_gpu_status': gpu[1], 'later_done': gpu[2],
        'later_command_errors': gpu[3], 'later_queue_lost': gpu[7], 'later_v1_rejected': gpu[13],
        'restoration_reported': result['restored'],
        'snapshots_ngdb_present': False,
        'post_clear_ddr_image_observed': h['clear_compared_words'] == 32,
    }
    inputs = [BOARD / name for name in ['result.json', 'journal.bin', 'microdma.log', 'microdma.tcl']]
    inputs += [FW / name for name in ['microdma.S', 'build_02/microdma.bin', 'decode_journal.py',
                                     'rtl_payload_02/result.json']]
    inputs += [RTL / name for name in ['tang/rtl/video/gpu_accel.v', 'tang/rtl/video/gpu_geometry.v',
        'tang/rtl/video/gpu_v1.v', 'tang/rtl/video/blitter.v', 'tang/rtl/board/ddr_gpu_arb.v',
        'tang/boards/neo/neo_gpu_debug.v', 'tang/boards/neo/console_neo.v']]
    return {'hardware_access_by_analysis': False, 'hardware_diagnostic_passed': False,
            'facts': facts, 'strict_journal_validation': decoded,
            'inference': 'CLEAR was submitted by CPU but completion was not observed; exact internal stall boundary is not captured.',
            'not_demonstrated': ['native DDR request emission or acceptance', 'post-CLEAR DDR contents',
                'physical DDR defect', 'FIFO defect', 'timing as root cause', 'reset as root cause'],
            'inputs': {str(path.relative_to(ROOT)): sha(path) for path in inputs}}


if __name__ == '__main__':
    report = analyze()
    path = HERE / 'evidence.json'
    if path.exists():
        raise SystemExit('Refusing to overwrite previous evidence')
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['facts'], indent=2))
