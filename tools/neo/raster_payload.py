"""Keep the raster's per-chunk initialization, removing only payload reset.

The state machine, load strobes, byte mask and dirty flag retain reset. Each
normal buffer consumer follows CHUNK, which still clears every payload bit.
Applied only to a frozen Neo source tree; transaction timing is unchanged.
"""
import hashlib
import json
from pathlib import Path
import re
from .gpu_debug import replace_once

RTL = 'tang/rtl/video/gpu_raster.v'
PROFILE = 'tang/boards/neo/gpu_raster_payload.json'
OLD = '''        if(rst)begin color_buf<=0;z_buf<=0;pixel_mask<=-1;chunk_dirty<=0;end
        else if(chunk_init)begin color_buf<=0;z_buf<=0;pixel_mask<=-1;chunk_dirty<=0;end
        else begin
            if(color_load)color_buf<=returned_data;
            else if(store_pixel && visible)color_buf[lane*16+:16]<=blended;
            if(z_load)z_buf<=returned_data;
            else if(store_pixel && visible)z_buf[lane*16+:16]<=depth;
            if(store_pixel && visible)begin pixel_mask[lane*2+:2]<=0;chunk_dirty<=1;end
        end
'''
NEW = '''        if(rst || chunk_init)begin pixel_mask<=-1;chunk_dirty<=0;end
        else if(store_pixel && visible)begin pixel_mask[lane*2+:2]<=0;chunk_dirty<=1;end
    end
    // Payload is private until the next CHUNK has initialized it. Reset
    // still clears the FSM, load strobes, mask and dirty bit. Preserve the
    // per-chunk clear, including bytes disabled by the eventual DDR mask.
    always @(posedge clk)begin
        if(chunk_init)begin color_buf<=0;z_buf<=0;end
        else begin
            if(color_load)color_buf<=returned_data;
            else if(store_pixel && visible)color_buf[lane*16+:16]<=blended;
            if(z_load)z_buf<=returned_data;
            else if(store_pixel && visible)z_buf[lane*16+:16]<=depth;
        end
'''


def freeze(source):
    source = Path(source)
    path = source / RTL
    if (source / PROFILE).exists():
        raise ValueError('Raster payload reset transformation already applied')
    original = path.read_text()
    changed = replace_once(original, OLD, NEW)
    record = dict(profile='neo-raster-chunk-initialized-payload', bits=512,
                  before=hashlib.sha256(original.encode()).hexdigest(),
                  after=hashlib.sha256(changed.encode()).hexdigest(),
                  extra_cycles=0, per_chunk_clear=True)
    path.write_text(changed)
    (source / PROFILE).write_text(json.dumps(record, indent=2) + '\n')
    return record


def audit_mapped(netlist):
    """Require all 512 payload bits to retain their local synchronous clear."""
    raw = Path(netlist).read_bytes()
    modules = re.findall(r'^module gpu_raster\b.*?^endmodule', raw.decode(), re.M | re.S)
    if len(modules) != 1:
        return dict(passed=False, errors=['Missing or ambiguous raster module'])
    cells = [(kind, name, dict(re.findall(r'\.(\w+)\(([^()]*)\)', ports)))
             for kind, name, ports in re.findall(
                 r'^\s*(DFF\w+)\s+((?:color_buf|z_buf)_\d+_s\d+)\s*\((.*?)\);',
                 modules[0], re.M | re.S)]
    errors = []
    expected = {f'{name}[{i}]' for name in ('color_buf', 'z_buf') for i in range(256)}
    if len(cells) != 512 or {p.get('Q') for _, _, p in cells} != expected:
        errors.append('Missing or duplicated raster payload bits')
    for kind, name, ports in cells:
        if kind != 'DFFRE' or ports.get('CLK') != 'gpu_clk' or ports.get('RESET') != 'chunk_init':
            errors.append('Raster payload clear/clock changed: ' + name)
    return dict(passed=not errors, errors=errors, payload_registers=len(cells),
                netlist_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Mapped clock and local synchronous clear; RTL equivalence and reset tests remain required')
