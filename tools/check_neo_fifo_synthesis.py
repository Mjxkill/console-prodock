#!/usr/bin/env python3
"""Verify the two CPU/DDR FIFO stores in the Neo register experiment.

This checks mapped structure, not CDC timing or functional equivalence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def audit(netlist):
    raw = Path(netlist).read_bytes()
    modules = dict(re.findall(r'^module\s+(\S+)\s*\((.*?)^endmodule[^\n]*',
                              raw.decode(), re.M | re.S))
    bridge = modules.get('ahb_ddr_cdc', '')
    stores, errors = {}, []
    for instance, width in (('u_requests', 100), ('u_responses', 64)):
        found = re.findall(r'^\s*(\S+)\s+' + instance + r'\s*\(', bridge, re.M)
        if len(found) != 1 or found[0] not in modules:
            errors.append('Missing/ambiguous bridge FIFO: ' + instance)
            continue
        body = modules[found[0]]
        cells = re.findall(r'^\s*(\w+)\s+(\\\S+|\w+)\s*\(', body, re.M)
        storage = [(typ, name) for typ, name in cells if 'g_register_storage.g_slot[' in name]
        slots = Counter()
        for typ, name in storage:
            match = re.fullmatch(r'\\g_register_storage\.g_slot\[([0-3])\]\.value_(\d+)_s\d+', name)
            if not match or not typ.startswith('DFF') or int(match[2]) >= width:
                errors.append('Unexpected storage cell: ' + instance + '/' + name)
            else:
                slots[(int(match[1]), int(match[2]))] += 1
        if slots != Counter({(s, b): 1 for s in range(4) for b in range(width)}):
            errors.append('Expected exactly four complete register words: ' + instance)
        # These mapped FIFO modules are flat. Reject both RAM and unexpected
        # child modules rather than silently skipping nested memory.
        forbidden = [name for typ, name in cells
                     if typ.startswith(('RAM', 'ROM', 'SDP', 'DPB', 'SP', 'BSRAM')) or typ in modules]
        if forbidden:
            errors.append('Memory/child module inside ' + instance + ': ' + str(forbidden))
        stores[instance] = dict(module=found[0], width=width, slots=4,
                                storage_cells=dict(Counter(t for t, n in storage)),
                                forbidden_cells=forbidden)
    return dict(passed=not errors, netlist=str(netlist), sha256=hashlib.sha256(raw).hexdigest(),
                scope='Neo AHB DDR four-slot command/response stores only',
                stores=stores, errors=errors)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = audit(a.netlist)
    text = json.dumps(result, indent=2) + '\n'
    if a.out:
        a.out.write_text(text)
    print(text, end='')
    if not result['passed']:
        raise SystemExit('Neo register FIFO mapping audit failed')
