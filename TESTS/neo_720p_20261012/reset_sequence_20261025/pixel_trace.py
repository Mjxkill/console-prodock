#!/usr/bin/env python3
"""Decode R16 observations without promoting a sampled mismatch to a root cause."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r16_gao_pixels'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping():
    return json.loads((BUILD / 'observation_preparation.json').read_text())['mapping']


def audit_wrapper():
    """Check generated public wrapper; internal GAO pipeline is encrypted."""
    prepared = json.loads((BUILD / 'observation_preparation.json').read_text())
    for name, digest in prepared['inputs'].items():
        assert sha(BUILD / name) == digest, name
    m = prepared['mapping']
    config = ET.parse(BUILD / 'source/tang/boards/neo/pixel_capture.gao').getroot()
    core = config.find('AoCore')
    assert config.findtext('GAO_ID') == '0101011010110000'
    assert core.attrib['sample_clock'] == 'gpu_clk'
    assert core.attrib['storage_depth'] == core.attrib['capture_amount'] == '512'
    assert core.attrib['trigger_pos'] == '32'
    assert core.attrib['capture_init_data_enabled'] == 'true'
    assert [s.text for s in core.findall('SignalList/Signal')] == m['unique_signals']
    assert core.findtext('Triggers/Trigger/SignalList/Signal') == m['controls']['shader_start']
    wrapper = BUILD / 'impl/gao/gw_gao_top.v'
    text = wrapper.read_text()
    match = re.search(r'\.data_i\(\{([^}]+)\}\)', text)
    assert match
    data = [v.strip().lstrip('\\') for v in match[1].split(',')]
    assert data == m['unique_signals']
    assert '.clk_i(gpu_clk)' in text
    assert '.trig0_i(\\u_accel/u_v1/shader_start )' in text
    parameters = BUILD / 'impl/gao/ao_0/gw_ao_parameter.v'
    p = dict(re.findall(r'^parameter (\w+) = ([^;]+);', parameters.read_text(), re.M))
    for key, value in {'SIG_PORT_WIDTH':'113', 'MEM_DATA_WIDTH':'114',
                       'STORAGE_DEPTH':'512', 'NUM_TRIG_PORTS':'1',
                       'TRIG_PORT_WIDTH_0':'1', 'MATCH_EN_0':'1'}.items():
        assert p[key] == value, key
    defines = BUILD / 'impl/gao/ao_0/gw_ao_top_define.v'
    assert '`define CORE0_DEF_CAPTURE_INIT_DATA' in defines.read_text()
    return dict(public_wrapper_passed=True, sample_clock='gpu_clk', data_signals=113,
                trigger_also_stored=True, memory_width=114,
                internal_pipeline_verified=False,
                limit='Public wrapper only; encrypted GAO internals and postroute paths still need examination.',
                inputs={str(p):sha(p) for p in [wrapper, parameters, defines,
                    BUILD/'observation_preparation.json']})


def parse_csv(text, m):
    lines = text.splitlines()
    assert lines[0].strip() == 'Data:', 'Missing GAO Data header'
    table = list(csv.reader(io.StringIO('\n'.join(lines[1:])), skipinitialspace=True))
    table = [[v.strip() for v in row[:-1]] if row and not row[-1].strip()
             else [v.strip() for v in row] for row in table if row]
    header = table[0]
    assert header[0].startswith('time unit:'), header[0]
    names = header[1:]
    assert set(names) == set(m['unique_signals']), 'Wrong/missing/extra probes'
    duplicates = {name for name in names if names.count(name) > 1}
    assert duplicates <= {m['controls']['shader_start']}, duplicates
    assert len(names) in (113, 114)
    rows = []
    for index, values in enumerate(table[1:]):
        assert len(values) == len(header), (index, 'Wrong column count')
        assert values[0] == str(index), (index, 'Unexpected sample sequence')
        row = {}
        for name, token in zip(names, values[1:]):
            assert token.lower() in ('0', '1', 'x', 'z'), (index, name, token)
            value = int(token) if token in ('0', '1') else None
            if name in row:
                assert row[name] == value, (index, 'Trigger/data duplicate disagreement')
            row[name] = value
        rows.append(row)
    assert len(rows) >= 2, 'Insufficient samples'
    return rows


def word(row, bits):
    if any(row[name] is None for name in bits.values()):
        return None
    return sum(row[name] << int(bit) for bit, name in bits.items())


def analyze(rows, m):
    decoded = []
    for i, row in enumerate(rows):
        d = dict(sample=i, time_from_buffer_start_ns=i * (1000 / 75))
        for key in ('geometry_header', 'actual_pixel_D', 'pixel_Q'):
            d[key] = word(row, m[key])
        d.update({key:row[name] for key, name in m['controls'].items()})
        decoded.append(d)
    transitions, captures, violations, skipped = [], [], [], []
    ce_disagreements, reset_disagreements = [], []
    for i, a in enumerate(decoded[:-1]):
        b = decoded[i+1]
        rst, ce, q, data = (a[k] for k in ('pixel_reset_active_high',
            'pixel_capture_enable', 'pixel_Q', 'actual_pixel_D'))
        if a['shader_start'] is not None and a['pixel_idle'] is not None and ce is not None:
            if ce != (a['shader_start'] & a['pixel_idle']):
                ce_disagreements.append(i)
        if rst is not None and a['pixel_reset_n'] is not None:
            if rst != 1-a['pixel_reset_n']:
                reset_disagreements.append(i)
        if rst == 1:
            expected, rule = 0, 'reset'
        elif rst == 0 and ce == 1:
            expected, rule = data, 'capture'
            captures.append(dict(sample=i, D=data, Q_before=q,
                Q_next=b['pixel_Q'], geometry=a['geometry_header']))
        elif rst == 0 and ce == 0:
            expected, rule = q, 'hold'
        else:
            expected, rule = None, 'unknown_control'
        if expected is None or b['pixel_Q'] is None:
            skipped.append(i)
        elif b['pixel_Q'] != expected:
            violations.append(dict(sample=i, rule=rule, expected=expected,
                                   observed_next=b['pixel_Q']))
        changes = {key:[a[key], b[key]] for key in a
                   if key not in ('sample', 'time_from_buffer_start_ns') and a[key] != b[key]}
        if changes:
            transitions.append(dict(from_sample=i, to_sample=i+1, changes=changes))
    return dict(samples=len(rows), unknown_values=sum(v is None for row in rows for v in row.values()),
        sampled_capture_events=captures, conditional_dffre_mismatches=violations,
        conditional_checks_skipped=skipped, ce_and_disagreements=ce_disagreements,
        reset_inverse_disagreements=reset_disagreements, transitions=transitions,
        all_rows_preserved=True, last_four_samples=decoded[-4:],
        interpretation='DFFRE comparisons assume aligned pre-edge samples. A mismatch is an observation, not proof of a faulty CE, reset, timing path or FPGA primitive.',
        capture_pipeline_assumed_uniform=True, hardware_cause_established=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    assert not a.out.exists(), 'Preserve previous evidence'
    result = dict(wrapper=audit_wrapper(), hardware_access=False)
    if a.csv:
        rows = parse_csv(a.csv.read_text(), mapping())
        assert len(rows) == 512, 'Unexpected hardware capture length'
        result.update(csv_sha256=sha(a.csv), observation=analyze(rows, mapping()))
    a.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(wrapper_passed=True, decoded=bool(a.csv), output=str(a.out))))


if __name__ == '__main__':
    main()
