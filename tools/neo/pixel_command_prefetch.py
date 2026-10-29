"""Decouple private pixel command capture from START and global reset.

The packet is sampled on the accepting IDLE edge exactly as before, and
held throughout the busy interval. Earlier idle samples are private. State,
valid descriptors, counters and external request ownership retain reset.
Only a frozen Neo tree is edited; the shared Pro Dock RTL is unchanged.
"""
import hashlib
import json
from pathlib import Path
import re
from .gpu_debug import replace_once

RTL = 'tang/rtl/video/gpu_v1.v'
PROFILE = 'tang/boards/neo/gpu_pixel_command_prefetch.json'
DECL = '    reg [255:0] packet /* synthesis syn_preserve=1 */;'
CAPTURE = '''
    // Packet writes during IDLE are private. The last such edge also
    // accepts START; every consuming state sees the same held command.
    always @(posedge clk)if(state[IDLE])packet<=command;
'''


def freeze(source):
    source = Path(source)
    path = source / RTL
    if (source / PROFILE).exists():
        raise ValueError('Pixel command prefetch already applied')
    original = path.read_text()
    changed = replace_once(original, '            packet<=0;plane_write<=0;',
                           '            plane_write<=0;')
    changed = replace_once(changed,
        "state[IDLE]:if(start)begin packet<=command;state<=58'b1<<DECODE_WAIT;end",
        "state[IDLE]:if(start)begin state<=58'b1<<DECODE_WAIT;end")
    changed = replace_once(changed, DECL, DECL + CAPTURE)
    if len(re.findall(r'\bpacket\s*<=', changed)) != 1:
        raise ValueError('Unexpected additional packet assignment')
    record = dict(profile='neo-pixel-idle-command-prefetch', registers=256,
                  extra_cycles=0, before=hashlib.sha256(original.encode()).hexdigest(),
                  after=hashlib.sha256(changed.encode()).hexdigest())
    path.write_text(changed)
    (source / PROFILE).write_text(json.dumps(record, indent=2) + '\n')
    return record


def audit_mapped(netlist):
    raw = Path(netlist).read_bytes()
    modules = re.findall(r'^module gpu_v1\b.*?^endmodule', raw.decode(), re.M | re.S)
    if len(modules) != 1:
        return dict(passed=False, errors=['Missing or ambiguous pixel module'])
    cells = [(kind, name, dict(re.findall(r'\.(\w+)\(([^()]*)\)', ports)))
             for kind, name, ports in re.findall(
                 r'^\s*(DFF\w+)\s+(packet_\d+_s\d+)\s*\((.*?)\);',
                 modules[0], re.M | re.S)]
    errors = []
    if len(cells) != 256 or {p.get('Q') for _, _, p in cells} != {f'packet[{i}]' for i in range(256)}:
        errors.append('Missing or merged pixel packet registers')
    for kind, name, ports in cells:
        if (kind != 'DFFRE' or ports.get('CLK') != 'gpu_clk' or
                ports.get('RESET') != 'GND' or ports.get('CE') != 'state[0]'):
            errors.append('Unexpected packet clock/reset/enable: ' + name)
    return dict(passed=not errors, errors=errors, registers=len(cells),
                netlist_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Mapped packet capture structure; functional and physical checks remain required')
