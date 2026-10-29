#!/usr/bin/env python3
"""Three reset-register placement anchors from the completed N54r0 report."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'optimizer')]
from check_neo_fifo_mapped import module
from placement import anchored_cells
from reports import fixed_constraints

source = ROOT/'tang/impl/console_neo_n54_timing'
if 'GowinSynthesis finish' not in (source/'build.log').read_text():
    raise ValueError('Wait for complete synthesis')
net = source/'impl/gwsynthesis/console_neo.vg'
text = net.read_text()
spec = {
    'u_soc/vid_hrstn_r_s0': ('ae350_soc', 'vid_hrstn_r_s0', 'R[50:65]C[100:120]'),
    'u_accel/engine_resetn_1_s0': ('gpu_accel', 'engine_resetn_1_s0', 'R[30:50]C[70:95]'),
    'u_accel/engine_resetn_3_s0': ('gpu_accel', 'engine_resetn_3_s0', 'R[60:80]C[70:95]'),
}
cells = {}
for name, (owner, leaf, region) in spec.items():
    body = module(text, owner)
    matches = re.findall(r'^\s*(DFF\w*)\s+'+re.escape(leaf)+r'\s*\(([^;]+)\);', body, re.M)
    if len(matches) != 1:
        raise ValueError('Missing/ambiguous mapped reset register: '+name)
    kind, ports = matches[0]
    cells[name] = dict(kind=kind, ports=ports, region=region)
base_path = source/'source/tang/boards/neo/neo.cst'
base = base_path.read_text()
if anchored_cells(base) & cells.keys():
    raise ValueError('An existing anchor would be replaced')
candidate = base+'\n// N54r1: measured long GPU reset paths; no logic or pin changes.\n'
candidate += ''.join(f'INS_LOC "{name}" {c["region"]};\n' for name,c in cells.items())
if fixed_constraints(candidate) != fixed_constraints(base):
    raise ValueError('Non-placement constraints changed')
out = Path(__file__).parent/'n54r1.cst'
with out.open('x') as stream:
    stream.write(candidate)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = dict(source=str(source), netlist_sha256=sha(net), base_cst_sha256=sha(base_path),
              candidate_cst_sha256=sha(out), cells=cells,
              evidence='timing_analysis.json',
              rationale='N54r0 reset routes to engine_resetn[1,3] are 7.968/8.380 ns. Bring their receivers toward the bus reset source. Leave DDR cells and logic unchanged.',
              limitation='Placement hypothesis only; reroute and all timing checks required.')
out.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
print(out)
