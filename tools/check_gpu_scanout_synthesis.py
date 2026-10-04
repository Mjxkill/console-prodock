#!/usr/bin/env python3
"""Reject mixed-clock DSP register absorption in the open scanout module.

Reads the official synthesis report only. No vendor netlist is decoded or
modified. This structural regression check supplements RTL and board tests;
it does not prove general synthesis equivalence or physical CDC correctness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def audit(netlist):
    raw = netlist.read_bytes()
    match = re.search(r'^module gpu_scanout\s*\(.*?^endmodule', raw.decode(), re.M | re.S)
    if not match:
        raise ValueError('Expected the open gpu_scanout module in synthesis output')
    module = match[0]
    records = []
    for cell in re.finditer(r'^\s+(MULT\w+)\s+(\S+)\s*\((.*?)\n\);', module, re.M | re.S):
        kind, name, ports = cell.groups()
        clock = re.search(r'\.CLK\((.*?)\)', ports)
        if not clock:
            raise ValueError(f'DSP clock connection missing: {name}')
        clock_nets = [s.strip() for s in clock[1].strip('{}').split(',')][::-1]
        parameters = dict(re.findall(r'defparam\s+' + re.escape(name) + r'\.(\w+)="([^"]+)";', module))
        enabled = {key: value for key, value in parameters.items()
                   if key.endswith('_CLK') and value != 'BYPASS'}
        clocks = sorted({clock_nets[int(value.removeprefix('CLK'))]
                         for value in enabled.values()})
        records.append(dict(cell=name, primitive=kind, clock_nets=clock_nets,
                            register_clocks=enabled, used_clocks=clocks))
    bad = [r['cell'] for r in records if len(r['used_clocks']) > 1]
    return dict(netlist=str(netlist), sha256=hashlib.sha256(raw).hexdigest(),
                scope='open gpu_scanout only; mixed-clock DSP register absorption',
                dsp=records, rejected_cells=bad, passed=not bad)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.stage / f'impl/gwsynthesis/console_{args.stage.name}.vg')
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    if not result['passed']:
        raise SystemExit('Mixed-clock DSP register absorption in scanout')


if __name__ == '__main__':
    main()
