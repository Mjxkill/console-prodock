"""Prefetch private geometry command operands while the engine is idle.

At the accepting edge IDLE and START are both asserted, just as before.
The payload then stays frozen while busy. Extra idle writes are private;
START no longer decodes the CE of 312 registers on a single clock cycle.
"""
import hashlib
import json
from pathlib import Path
import re
from .gpu_debug import replace_once

RTL = 'tang/rtl/video/gpu_geometry.v'
PROFILE = 'tang/boards/neo/gpu_command_prefetch.json'
CAPTURE = '''     captured_command<=command;
     mesh_vertex_end<={1'b0,command[63:32]}+{12'b0,command[127:112],5'b0};
     mesh_face_end<={1'b0,command[95:64]}+{12'b0,command[111:96],5'b0};
'''


def freeze(source):
    source = Path(source)
    path = source / RTL
    if (source / PROFILE).exists():
        raise ValueError('Geometry command prefetch already applied')
    original = path.read_text()
    changed = replace_once(original, CAPTURE, '')
    changed = replace_once(changed, ' integer j;\n', ''' // Capture at the accepting IDLE edge, and prefetch on earlier idle
 // edges. Retain the command throughout the busy interval. Only this
 // private payload loses the combinational reset/START enable decode.
 always @(posedge clk)if(state[IDLE])begin
''' + CAPTURE + ''' end
 integer j;
''')
    record = dict(profile='neo-geometry-idle-command-prefetch', extra_cycles=0,
                  before=hashlib.sha256(original.encode()).hexdigest(),
                  after=hashlib.sha256(changed.encode()).hexdigest())
    path.write_text(changed)
    (source / PROFILE).write_text(json.dumps(record, indent=2) + '\n')
    return record


def audit_mapped(netlist):
    raw = Path(netlist).read_bytes()
    matches = re.findall(r'^module gpu_geometry\b.*?^endmodule', raw.decode(), re.M | re.S)
    if len(matches) != 1:
        return dict(passed=False, errors=['Missing geometry module'])
    cells = [(kind, name, dict(re.findall(r'\.(\w+)\(([^()]*)\)', ports)))
             for kind, name, ports in re.findall(
                 r'^\s*(DFF\w+)\s+((?:captured_command|mesh_vertex_end|mesh_face_end)_\d+_s\d+)\s*\((.*?)\);',
                 matches[0], re.M | re.S)]
    expected = {f'captured_command[{i}]' for i in range(256)}
    expected |= {f'{name}[{i}]' for name in ('mesh_vertex_end', 'mesh_face_end') for i in range(5, 33)}
    errors = []
    if len(cells) != 312 or {ports.get('Q') for _, _, ports in cells} != expected:
        errors.append('Command prefetch register coverage changed')
    for kind, name, ports in cells:
        if (kind != 'DFFRE' or ports.get('CLK') != 'gpu_clk' or ports.get('RESET') != 'GND'
                or ports.get('CE') != 'state[0]'):
            errors.append('Command payload does not use the direct IDLE enable: ' + name)
    return dict(passed=not errors, errors=errors, registers=len(cells),
                netlist_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Structure of the mapped capture enable; no timing or functional waiver')
