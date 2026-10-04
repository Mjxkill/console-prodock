#!/usr/bin/env python3
"""Reject the known two-enable DSP C absorption in our V1 address arithmetic.

This conservative structural guard supplements the primitive reproduction
and board tests. It neither edits vendor netlists nor proves full equivalence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def audit(netlist):
    raw = netlist.read_bytes()
    cells = []
    for module_name in ('gpu_copy565','gpu_v1'):
        module = re.search(r'^module '+module_name+r'\b.*?^endmodule', raw.decode(), re.M | re.S)[0]
        for match in re.finditer(r'^\s+MULTALU27X18\s+(\S+)\s*\(', module, re.M):
            name = match[1]
            params = dict(re.findall(r'defparam '+re.escape(name)+r'\.(\w+)="([^"]+)";', module))
            c_regs = {key: params[key] for key in ('C_IREG_CLK','C_IREG_CE','C_PREG_CLK','C_PREG_CE')}
            risky = (c_regs['C_IREG_CLK'] != 'BYPASS' and c_regs['C_PREG_CLK'] != 'BYPASS'
                     and c_regs['C_IREG_CE'] != c_regs['C_PREG_CE'])
            cells.append(dict(cell=module_name+'/'+name, c_registers=c_regs, risky=risky))
    if not cells:
        raise ValueError('Expected copy arithmetic DSP cells; update audit after an intentional architecture change')
    rejected = [c['cell'] for c in cells if c['risky']]
    return dict(netlist=str(netlist),sha256=hashlib.sha256(raw).hexdigest(),
                scope='gpu_copy565/gpu_v1; independently enabled double C pipeline',
                dsp=cells,rejected_cells=rejected,passed=not rejected)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.stage/f'impl/gwsynthesis/console_{a.stage.name}.vg')
    a.out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result))
    if not result['passed']:
        raise SystemExit('Unsafe two-enable DSP C register absorption in RGB565 copy')


if __name__ == '__main__':
    main()
