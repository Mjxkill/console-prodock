"""Neo experiment: drive triangle byte validity through register D inputs.

The CHUNK pulse no longer shares a synchronous SET with the 512 buffer bits.
The kept next-state nets are audited after synthesis; RTL equivalence alone
does not prove that the mapper respected this implementation choice.
"""
import hashlib
import json
from pathlib import Path
import re

REL = 'tang/rtl/video/gpu_v1.v'
PROFILE = 'tang/boards/neo/gpu_pixel_mask.json'


def transform(text):
    declaration = '    reg [31:0] pixel_mask;'
    replacement = '''    wire [31:0] pixel_mask;
    reg [15:0] pixel_written /* synthesis syn_preserve=1 */;
    wire [15:0] pixel_written_next /* synthesis syn_keep=1 */;
    wire pixel_commit=!color_load && pixel_visible &&
        (state[PIX_STORE] || state[PIX_OPAQUE]);
    genvar mask_lane;
    generate for(mask_lane=0;mask_lane<16;mask_lane=mask_lane+1)begin: mask_data
        assign pixel_written_next[mask_lane]=!rst && !state[CHUNK] &&
            (pixel_written[mask_lane] || (pixel_commit && lane==mask_lane));
        assign pixel_mask[mask_lane*2+:2]={2{!pixel_written[mask_lane]}};
    end endgenerate
    always @(posedge clk)pixel_written<=pixel_written_next;'''
    if text.count(declaration) != 1 or text.count('pixel_mask<=-1;') != 2 or \
            text.count('pixel_mask[lane*2+:2]<=0;') != 2:
        raise ValueError('Unexpected reference pixel-mask implementation')
    return (text.replace(declaration, replacement)
            .replace('pixel_mask<=-1;', '')
            .replace('                pixel_mask[lane*2+:2]<=0;\n', ''))


def freeze(source):
    source = Path(source)
    path = source/REL
    before = path.read_bytes()
    after = transform(before.decode()).encode()
    path.write_bytes(after)
    record = dict(scope='Neo only; unchanged cycle, mask polarity, buffers and DDR protocol',
                  file=REL, before_sha256=hashlib.sha256(before).hexdigest(),
                  after_sha256=hashlib.sha256(after).hexdigest(),
                  reference='N38 DDR5.9/300; partial-write failure isolated on 2026-10-20')
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
        if not kind.startswith('DFF') or 'pixel_written' not in name:
            continue
        if routed and not name.removeprefix('\\').startswith('u_accel/u_v1/u_pixels/'):
            continue
        pins = {k: re.sub(r'\s+', '', v).removeprefix('\\')
                for k, v in re.findall(r'\.(\w+)\(([^()]*)\)', ports)}
        cells.append(dict(kind=kind, name=name, pins=pins))
    errors = []
    if len(cells) != 16:
        errors.append('Expected sixteen independent pixel-written registers')
    if len({c['pins'].get('Q') for c in cells}) != 16:
        errors.append('Expected sixteen distinct pixel-written outputs')
    for cell in cells:
        p = cell['pins']
        if not {'D', 'Q', 'CLK'} <= p.keys() or p.get('CE', 'VCC') != 'VCC' or any(p.get(pin, 'GND') != 'GND'
                                            for pin in ('RESET', 'SET', 'CLEAR', 'PRESET')):
            errors.append('Mask register still uses a dynamic CE/reset: '+cell['name'])
    return dict(passed=not errors, errors=errors, registers=cells, routed=routed,
                netlist_sha256=hashlib.sha256(raw).hexdigest())
