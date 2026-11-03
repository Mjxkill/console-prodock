#!/usr/bin/env python3
"""Measure coverage/data delays for both original USB2 PHY Gray-pointer FIFOs.

Expected connections are read from the untouched vendor model, including
optimized pointer MSBs driven by rbin_num. An absent path is never a PASS.
Cross-clock setup slack is printed as evidence, not used as CDC sign-off.
"""
import argparse
import hashlib
import json
from pathlib import Path
from vendor_reference import USB as SIPEED_USB
import re

MODEL = SIPEED_USB / 'usb2_0_softphy/usb2_0_softphy.vo'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_paths(model, instance_prefix='u_usb_softphy_top/'):
    cells, drivers = {}, {}
    text = model.read_text()
    for match in re.finditer(r'(?m)^(DFF\w*)\s+(\\\S+)\s+\(\n(.*?)\n\);', text, re.S):
        ports = {k: re.sub(r'\s+', '', v) for k, v in re.findall(r'\.(\w+)\(([^)]*)\)', match[3])}
        name = match[2][1:]
        cells[name] = ports
        if 'Q' in ports:
            drivers[ports['Q']] = name + '/Q'
    wanted = {}
    for name, ports in cells.items():
        match = re.search(r'(Equal|Small)\.(rq[12]_wptr|wq[12]_rptr)_(\d+)_s0$', name)
        if not match:
            continue
        if 'fifo_4to8_sub_inst/' in name:
            fifo = 'rx'
        elif 'fifo_8to4_sub_inst/' in name:
            fifo = 'tx'
        else:
            continue
        stage = match[2]
        group = fifo + '_' + stage
        if ports['D'] not in drivers:
            raise ValueError(f'Cannot find original register driving {name}/D: {ports["D"]}')
        source = instance_prefix + drivers[ports['D']]
        target = instance_prefix + name + '/D'
        wanted[(source, target)] = dict(group=group, bit=int(match[3]))
    counts = {g: sum(x['group'] == g for x in wanted.values()) for g in {x['group'] for x in wanted.values()}}
    if len(wanted) != 44 or sorted(counts.values()) != [5]*4 + [6]*4:
        raise ValueError(f'Unexpected original FIFO topology: {counts}')
    return wanted


def inspect(report, wanted):
    paths, analysis = {}, None
    with report.open() as stream:
        for line in stream:
            match = re.match(r'3\.1\.\d+ (Setup|Hold|Recovery|Removal)', line)
            if match:
                analysis = match[1].lower()
            if line.startswith('3.2 '):
                break
            if analysis != 'setup' or 'u_usb_softphy_top/' not in line:
                continue
            fields = line.split()
            if len(fields) != 9 or not fields[0].isdigit():
                continue
            key = tuple(fields[2:4])
            if key not in wanted:
                continue
            value = dict(source=key[0], target=key[1], launch_clock=fields[4],
                         capture_clock=fields[5], data_delay_ns=float(fields[8]),
                         reported_setup_slack_ns=float(fields[1]))
            if key not in paths or value['data_delay_ns'] > paths[key]['data_delay_ns']:
                paths[key] = value
    groups = {}
    for group in sorted({x['group'] for x in wanted.values()}):
        found = [dict(bit=x['bit'], **paths[key]) for key, x in wanted.items()
                 if x['group'] == group and key in paths]
        missing = [dict(**x, source=key[0], target=key[1]) for key, x in wanted.items()
                   if x['group'] == group and key not in paths]
        delays = [x['data_delay_ns'] for x in found]
        groups[group] = dict(expected=len(found)+len(missing), reported=len(found),
                             delay_range_ns=[min(delays), max(delays)] if delays else None,
                             paths=sorted(found, key=lambda x: x['bit']), missing=missing)
    return groups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('--model', type=Path, default=MODEL)
    p.add_argument('--reference-bin', type=Path)
    p.add_argument('--audit-bin', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if bool(a.reference_bin) != bool(a.audit_bin):
        p.error('Both reference and audit binaries are required to check configuration identity')
    wanted = expected_paths(a.model)
    groups = inspect(a.report, wanted)
    complete = all(not g['missing'] for g in groups.values())
    result = dict(report=str(a.report.resolve()), report_sha256=digest(a.report),
                  model_sha256=digest(a.model), expected_paths=len(wanted), groups=groups,
                  coverage_complete=complete,
                  limits='Measured data delays and coverage only. Cross-domain synchronous slack is not a CDC qualification; no metastability/reset/analog proof.')
    identical = None
    if a.reference_bin:
        reference, audit = digest(a.reference_bin), digest(a.audit_bin)
        identical = reference == audit
        result['configuration'] = dict(reference=str(a.reference_bin.resolve()),
                                       audit=str(a.audit_bin.resolve()), reference_sha256=reference,
                                       audit_sha256=audit, identical=identical)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    for name, g in groups.items():
        print(f"{name}: {g['reported']}/{g['expected']}, data delay {g['delay_range_ns']}")
    print(f'Coverage complete={complete}; configuration identical={identical}')
    return 0 if complete and identical is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
