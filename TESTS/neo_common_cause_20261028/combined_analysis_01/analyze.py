#!/usr/bin/env python3
"""Read-only analysis of the completed combined capture; never changes its verdict."""
import ast, hashlib, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / 'combined_gpu_usb_prepared_01/combined_20261028_133840'
RTL = ROOT / 'tang/impl/console_neo_n56r22r1_utw1_reports/source/tang'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def main():
    result_path = SOURCE / 'result.json'
    require(sha(result_path) == '8d32a697110990d3185d0e43f041c4903624339892223d0bc7af8771d05e2649', 'Unexpected result')
    report = json.loads(result_path.read_text())
    require(report.get('finished_unix') and report['left_startup_verified'], 'Run not completed/restored')
    require(report['last_programmed_sha256'] == report['r19_sha256'], 'Restoration identity')
    for name, digest in report['files'].items():
        require(sha(SOURCE / name) == digest, 'Changed capture file: ' + name)
    raw = (SOURCE / 'candidate_utw1_capture.log').read_text()
    obs = report['observation']
    snapshots = {}
    for label, text in re.findall(r'^COMBINED_SNAPSHOT (\w+) (.+)$', raw, re.M):
        require(label not in snapshots, 'Duplicate snapshot')
        snapshots[label] = [int(v, 0) for v in text.split()]
    require(snapshots == obs['snapshots'], 'Stored snapshots differ from actual log')
    for label, seq in [('GPU_BEFORE', 1), ('GPU_AFTER_MATRIX', 2), ('GPU_FINAL', 3), ('SCAN_BEFORE', 1), ('SCAN_FINAL', 2)]:
        v = snapshots[label]
        require(len(v) == 17 and v[:2] == [0x4e474442, 6] and v[3] == seq, 'Snapshot sequence/status: ' + label)
    debug_source = RTL / 'boards/neo/neo_gpu_debug.v'
    require(sha(debug_source) == 'e4fe28e1aac8386e31fde8b2c3ec1087dbe37dcd712c23b96684ac9dd1b4857c', 'RTL changed')
    s = debug_source.read_text()
    require('assign register_value[2]=host_words;' in s and 'assign register_value[4]=snapshot[287:256];' in s, 'Register mapping changed')
    require('held<={last_word,received,live};' in s and 'snapshot<=held;' in s, 'Snapshot handshake changed')

    # Reuse only the existing pure decode function, never import hardware helpers.
    decoder_path = ROOT / 'tools/neo/probe_gpu_debug.py'
    tree = ast.parse(decoder_path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'decode')
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(decoder_path), 'exec'), ns)
    decoded = {k: ns['decode'](v[:16]) for k, v in snapshots.items() if k.startswith('GPU_')}
    before = decoded['GPU_BEFORE']
    after = decoded['GPU_AFTER_MATRIX']
    final = decoded['GPU_FINAL']
    properties = {
        'live_host_increment8': after['host_words'] == before['host_words'] + 8,
        'fresh_snapshot_received_increment8': after['received_words'] == before['received_words'] + 8,
        'fresh_snapshot_done_increment1': after['done'] == before['done'] + 1,
        'no_command_bad_or_lost': all(v['command_bad'] == v['command_lost'] == 0 for v in decoded.values()),
        'final_counters_stable': all(after[k] == final[k] for k in ['host_words', 'received_words', 'done']),
        'matrix_header_observed': after['extended_word0'] == 0x1f000000 and snapshots['GPU_AFTER_MATRIX'][6] == 0x1f000000,
        'all_engine_resets_released_at_snapshots': all(v['engine_resetn'] == 15 and v['child_resetn'] == 255 and v['mrst'] == 3 for v in decoded.values()),
        'stale_received_matches_previous_capture': obs['matrix']['AFTER'][1] == before['received_words'],
    }
    require(all(properties.values()), 'Counter interpretation is not supported by capture')
    scan = {}
    for k in ['SCAN_BEFORE', 'SCAN_FINAL']:
        v = snapshots[k]
        scan[k] = dict(sequence=v[3], accepted_by_queue=v[11], accepted_by_arbiter=v[12], returned=v[13], last_address=v[14], flags_hex=hex(v[15]))
    output = dict(
        hardware_access=False, original_result_changed=False,
        original_protocol_passed=obs['protocol_passed'], original_qualification_status=report['qualification_status'],
        original_errors=obs['combined_errors'],
        finding='The matrix counter FAIL is a host diagnostic bug: received was read from the old snapshot before requesting the next capture.',
        local_command_observation_supported=all(properties.values()), properties=properties,
        gpu_snapshots=decoded, scan_snapshots=scan,
        video_frames_delta_T0_T1200=obs['video_frame_delta_mod32'], host_usb=report['host_usb'],
        utw1_all_four_coherent=all(c['decode']['coherent'] and c['decode']['passed'] for c in obs['captures']),
        limits=[
            'No GPU rendering, DDR transfer, Linux boot, or USB functionality is qualified.',
            'Reset release is observed at three snapshots, not proven continuously.',
            'No USB sysfs device was observed; this does not establish a reset cause.',
            'Global STA remains FAIL; local command completion does not waive it.',
            'Video frame counter advancement does not attest the HDMI picture or physical clock frequency.',
            'The original failed result is preserved; this is a separate interpretation with provenance.',
        ],
        inputs={str(p.relative_to(ROOT)):sha(p) for p in [result_path, SOURCE/'candidate_utw1_capture.log', debug_source, decoder_path, RTL/'boards/neo/neo_scan_observe.v', RTL/'rtl/video/gpu_accel.v', Path(__file__)]},
    )
    (HERE/'result.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(dict(command_observation=output['local_command_observation_supported'], original_result_preserved=True, properties=properties)))

if __name__ == '__main__':
    main()
