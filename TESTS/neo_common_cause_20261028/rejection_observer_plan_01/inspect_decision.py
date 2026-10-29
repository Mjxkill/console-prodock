#!/usr/bin/env python3
"""Inventory decision-edge taps in the exact R19 VG; never writes RTL.

This checks named primitive ports, not combinational equivalence or timing.
It produces evidence only after the source netlist identity has been checked.
"""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local'
EXPECTED = 'dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(text, name):
    matches = list(re.finditer(r'^module ' + re.escape(name) + r'\b.*?^endmodule',
                              text, re.M | re.S))
    assert len(matches) == 1, name
    return matches[0].group(0)


def cells(text):
    result = {}
    parameters = {}
    for name, key, value in re.findall(
            r'^\s*defparam\s+(\S+)\.(\w+)\s*=\s*([^;]+);', text, re.M):
        parameters.setdefault(name, {})[key] = value
    for kind, name, body in re.findall(
            r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);', text, re.M | re.S):
        if kind == 'module':
            continue
        assert name not in result, name
        ports = {pin: re.sub(r'\s+', '', net)
                 for pin, net in re.findall(r'\.(\w+)\(([^()]*)\)', body)}
        result[name] = {'kind': kind, 'ports': ports, 'parameters': parameters.get(name, {})}
    return result


def main():
    path = BUILD / 'console_neo.vg'
    assert digest(path) == EXPECTED, 'R19 netlist changed'
    text = path.read_text()
    blocks = {n: module(text, n) for n in
              ('gpu_v1', 'gpu_copy565', 'neo_gpu_debug_0', 'neo_gpu_debug')}
    cc = {n: cells(t) for n, t in blocks.items()}
    copy, parent = cc['gpu_copy565'], cc['gpu_v1']
    checks = {}
    for i, d in enumerate(('n2373_7', 'n2382_7', 'n2436_5')):
        cell = copy[f'descriptor_bad_{i}_s0']
        assert cell['kind'] == 'DFFRE'
        assert cell['ports'] == {'Q': f'descriptor_bad[{i}]', 'D': d,
                                'CLK': 'gpu_clk', 'RESET': 'n577_9', 'CE': 'n5984_12'}
        checks[f'copy.descriptor_bad[{i}]'] = cell
    expected = {
        'state_1_s0': ('state[1]', 'n22771_33', 'n1617_5', 'VCC'),
        'bad_header_s0': ('bad_header', 'n5713_12', 'n5721_3', 'VCC'),
        'target_valid_s2': ('shader_target_valid', 'n22777_13', 'n1617_5', 'target_valid_7'),
    }
    for name, (q, d, reset, ce) in expected.items():
        cell = parent[name]
        assert cell['kind'] == 'DFFRE'
        assert cell['ports'] == {'Q': q, 'D': d, 'CLK': 'gpu_clk', 'RESET': reset, 'CE': ce}
        checks['parent.' + name] = cell
    assert copy['bad_s0']['ports'] == {
        'Q': 'copy_bad', 'D': 'n4731_54', 'CLK': 'gpu_clk', 'RESET': 'n577_9', 'CE': 'VCC'}
    checks['copy.bad_s0'] = copy['bad_s0']
    for name in ('n5984_s7', 'n7630_s2', 'n421_s1'):
        checks['copy.' + name] = copy[name]
    packet = [c for c in copy.values() if c['kind'] == 'DFFRE' and
              re.fullmatch(r'packet_0\[\d+\]', c['ports'].get('Q', ''))]
    assert len(packet) == 256
    assert {c['ports']['CE'] for c in packet} == {'n7630_6'}
    assert {c['ports']['CLK'] for c in packet} == {'gpu_clk'}
    banks = {}
    for name in ('neo_gpu_debug_0', 'neo_gpu_debug'):
        stages = {}
        for stage in ('held', 'snapshot'):
            regs = {int(m.group(1)): c for c in cc[name].values()
                    if c['kind'] == 'DFFRE'
                    and (m := re.fullmatch(stage + r'\[(\d+)\]', c['ports'].get('Q', '')))}
            stages[stage] = {
                'count': len(regs),
                'missing_indices_320': sorted(set(range(320)) - set(regs)),
                'clock': sorted({c['ports']['CLK'] for c in regs.values()}),
                'reset': sorted({c['ports']['RESET'] for c in regs.values()}),
                'ce': sorted({c['ports']['CE'] for c in regs.values()}),
            }
        assert stages['held']['count'] == stages['snapshot']['count']
        banks[name] = stages
    assert [banks[n]['held']['count'] for n in banks] == [283, 208]
    missing = sum(len(v[s]['missing_indices_320']) for v in banks.values()
                  for s in ('held', 'snapshot'))
    assert missing == 298
    context = [
        ('tag', 32), ('destination_base', 32), ('destination_stride', 16),
        ('destination_width', 16), ('destination_height', 16), ('src_end_at_check', 33),
        ('dst_end_at_check', 33), ('parent_state_at_decision', 58),
        ('child_state_at_check', 5), ('child_state_at_bad_edge', 5),
        ('descriptor_D_at_check', 3), ('descriptor_Q_after_check', 3),
        ('parent_child_word_difference', 8), ('flags', 13), ('reason', 3),
        ('command_generation', 16), ('check_generation', 16), ('liveness', 12),
    ]
    offset = 0
    layout = []
    for name, width in context:
        layout.append({'name': name, 'lsb': offset, 'width': width})
        offset += width
    assert offset == 320
    files = [path, Path(__file__), BUILD / 'sources.json', BUILD / 'experiment.json']
    result = {
        'status': 'INVENTORY_PASS_NOT_IMPLEMENTED', 'hardware': False,
        'rtl_changed': False, 'synthesis_or_routing': False,
        'netlist_sha256': EXPECTED, 'taps': checks,
        'copy_packet_registers': len(packet), 'banks': banks,
        'transport_missing_ff_count': missing,
        'bank0_layout': [dict(name='selected_packet', lsb=0, width=256),
                         dict(name='tag', lsb=256, width=32),
                         dict(name='parent_w0', lsb=288, width=32)],
        'bank1_layout': layout,
        'inputs': {str(p.relative_to(ROOT)): digest(p) for p in files},
        'limits': ['Named port audit only; no full truth-table equivalence.',
                   'No proposed observer source, mapped helper, STA or hardware proof.',
                   'Transport FF count is structural; final mapping may add replication.'],
    }
    (HERE / 'decision_evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'packet_ff': len(packet),
                      'transport_missing_ff': missing, 'context_bits': offset}))


if __name__ == '__main__':
    main()
