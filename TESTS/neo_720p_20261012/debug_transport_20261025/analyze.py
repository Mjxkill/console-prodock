#!/usr/bin/env python3
"""Decode archived TAP observations; no hardware access."""
import csv
import hashlib
import json
from pathlib import Path
import re

here = Path(__file__).resolve().parent
result = {'scope': 'Archived JTAG transport observations, not a CPU/FPGA qualification', 'runs': {}}
for name in ['read_01', 'dmstatus_01', 'clear_sticky_01', 'dmcontrol_01']:
    folder = here / name
    meta = json.loads((folder / 'result.json').read_text())
    log = folder / 'openocd.log'
    assert hashlib.sha256(log.read_bytes()).hexdigest() == meta['log_sha256']
    assert hashlib.sha256((folder / 'read.tcl').read_bytes()).hexdigest() == meta['script_sha256']
    assert meta['returncode'] == 0 and not meta.get('timed_out')
    txt = log.read_text()
    transport = []
    for speed, index, raw in re.findall(r'TRANSPORT_DTMCS speed_khz=(\d+) index=(\d+) raw=([0-9a-f]+)', txt):
        val = int(raw, 16)
        transport.append(dict(speed_khz=int(speed), index=int(index), raw=raw,
            version=val & 15, abits=(val >> 4) & 63, dmistat=(val >> 10) & 3, idle=(val >> 12) & 7))
    assert len(transport) == 12
    assert all(t['raw'] == '00007071' for t in transport)
    dmi = []
    for label, fields, raw in re.findall(r'(DMSTATUS_RESPONSE|DMCONTROL_RESPONSE|DMSTATUS_AFTER_CLEAR|DMCONTROL_AFTER_CLEAR)([^\n]*?)raw=([0-9a-f]+)', txt):
        val = int(raw, 16)
        dmi.append(dict(label=label, context=fields.strip(), raw=raw,
            address=(val >> 34) & 127, payload=(val >> 2) & 0xffffffff,
            status=val & 3, payload_is_register_value=(val & 3) == 0))
    clearing = []
    for index, raw in re.findall(r'STICKY_CLEAR_AFTER index=(\d+) raw=([0-9a-f]+)', txt):
        clearing.append(dict(index=int(index), dtmcs=raw, dmistat=(int(raw, 16) >> 10) & 3))
    if name != 'read_01':
        expected_address = 0x10 if name == 'dmcontrol_01' else 0x11
        assert all(x['status'] == 3 and x['address'] == expected_address for x in dmi)
        assert len(dmi) == (3 if name == 'dmstatus_01' else 5)
    if clearing:
        assert len(clearing) == 2 and all(x['dmistat'] == 0 for x in clearing)
    result['runs'][name] = dict(log_sha256=meta['log_sha256'], transport=transport,
        dmi=dmi, sticky_clear=clearing, metadata=meta)
result['findings'] = [
    'DTMCS is consistently 0x7071 at 100, 1000 and 100 kHz.',
    'One DMI read of DMSTATUS and one separate read of DMCONTROL return BUSY.',
    'DMIRESET clears DMISTAT, but the subsequent NOP returns BUSY again in each of two checks.',
    'BUSY payload zeros are not DMSTATUS/DMCONTROL values.',
    'This distinguishes an uncompleted DMI read from merely retained sticky status; it does not identify the internal clock/reset cause.',
    'No CPU halt, CPU reset, DMI write, memory write, or FPGA programming was requested.'
]
gao_folder = here.parent / 'reload_r1_cold_20261022/gao_cli_research/r10_initial_read_04'
gao_path = gao_folder / 'initial_core0_window0.csv'
gao_meta = json.loads((gao_folder / 'result.json').read_text())
gao_hash = hashlib.sha256(gao_path.read_bytes()).hexdigest()
assert gao_hash == gao_meta['outputs'][gao_path.name]['sha256']
with gao_path.open() as handle:
    assert handle.readline().strip() == 'Data:'
    rows = list(csv.reader(handle, skipinitialspace=True))
signals = rows[0][1:-1]
samples = rows[1:]
assert len(samples) == 4096 and len(signals) == 20
columns = {}
for i, name in enumerate(signals, 1):
    data = [int(r[i]) for r in samples]
    assert set(data) <= {0, 1}
    columns[name] = dict(zeros=data.count(0), ones=data.count(1),
        transitions=sum(a != b for a, b in zip(data, data[1:])))
result['gao_followup'] = dict(csv=str(gao_path), sha256=gao_hash,
    rows=4096, sample_period_ns=20, window_duration_us=81.92, signals=columns,
    caveat='Requested initial buffer; acquisition chronology not established. GAO timing qualification still FAIL.')
(here / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(dict(runs=len(result['runs']), findings=result['findings']), indent=2))
