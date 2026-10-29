"""Neo experiment: keep the perspective selector off shared CE/reset controls.

The selector still clears on reset/CHUNK and toggles on pixel_advance. Only
its implementation changes: a kept D-input expression and unconditional FF.
"""
import hashlib
import json
from pathlib import Path
import re

REL = 'tang/rtl/video/gpu_v1.v'
PROFILE = 'tang/boards/neo/gpu_pixel_selector.json'


def transform(text):
    edits = (
        ('    reg per_select;', '    reg per_select /* synthesis syn_preserve=1 */;'),
        ('    wire pixel_advance=state[PIX_NEXT] || state[PIX_STORE] || state[PIX_OPAQUE];',
         '''    wire pixel_advance=state[PIX_NEXT] || state[PIX_STORE] || state[PIX_OPAQUE];
    wire per_select_next /* synthesis syn_keep=1 */;
    assign per_select_next=!rst && !state[CHUNK] && (per_select ^ pixel_advance);
    always @(posedge clk)per_select<=per_select_next;'''),
        ('        if(rst)begin per_ready<=0;per_select<=0;end',
         '        if(rst)begin per_ready<=0;end'),
        ('            if(state[CHUNK])per_select<=0;\n'
         '            else if(pixel_advance)per_select<=~per_select;\n', ''),
    )
    if any(text.count(before) != 1 for before, _ in edits):
        raise ValueError('Unexpected reference perspective-selector implementation')
    for before, after in edits:
        text = text.replace(before, after)
    return text


def freeze(source):
    source = Path(source)
    path = source/REL
    before = path.read_bytes()
    after = transform(before.decode()).encode()
    path.write_bytes(after)
    record = dict(scope='Neo only; unchanged selector cycles, dividers, buffers and DDR protocol',
                  file=REL, before_sha256=hashlib.sha256(before).hexdigest(),
                  after_sha256=hashlib.sha256(after).hexdigest(),
                  reference='N38 CHUNK-clear fault model; perspective first-pair inversions')
    (source/PROFILE).write_text(json.dumps(record, indent=2)+'\n')
    return record


def audit(netlist, *, routed=False):
    raw = Path(netlist).read_bytes()
    text = raw.decode()
    if not routed:
        match = re.search(r'\bmodule gpu_v1\b.*?\bendmodule\b', text, re.S)
        if not match:
            raise ValueError('Missing synthesized gpu_v1')
        text = match[0]
    cells = []
    for kind, name, ports in re.findall(r'^[ \t]*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);', text, re.M | re.S):
        if not kind.startswith('DFF') or 'per_select' not in name:
            continue
        if routed and not name.removeprefix('\\').startswith('u_accel/u_v1/u_pixels/'):
            continue
        pins = {k: re.sub(r'\s+', '', v).removeprefix('\\')
                for k, v in re.findall(r'\.(\w+)\(([^()]*)\)', ports)}
        cells.append(dict(kind=kind, name=name, pins=pins))
    errors = []
    if len(cells) != 1:
        errors.append('Expected exactly one preserved perspective selector register')
    for cell in cells:
        p = cell['pins']
        if (not {'D', 'Q', 'CLK'} <= p.keys() or p.get('CE', 'VCC') != 'VCC' or
                any(p.get(pin, 'GND') != 'GND' for pin in ('RESET', 'SET', 'CLEAR', 'PRESET'))):
            errors.append('Perspective selector still uses a dynamic CE/reset: '+cell['name'])
    return dict(passed=not errors, errors=errors, registers=cells, routed=routed,
                netlist_sha256=hashlib.sha256(raw).hexdigest())
