#!/usr/bin/env python3
"""Reproduce bounded facts used to correct the GLM review, without tools/hardware.

Direct reset fanout is counted from exact routed DFF primitive pins. This is
not a CDC proof: buffered/derived descendants and analog behaviour are outside
the count. Vendor simulation models establish RESET versus CLEAR semantics.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
BUILD = ROOT/'tang/impl/prodock_sd_boot_20261029_r5'
PRIMITIVES = Path('/home/michael/gowin/IDE/simlib/gw5a/prim_tsim.v')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(text, name):
    start = re.search(r'^module '+re.escape(name)+r'\s*\(', text, re.M)
    assert start, name
    return text[start.start():text.index('endmodule', start.start())]


def main():
    vo_path = next((BUILD/'impl/pnr').glob('*.vo'))
    assert digest(vo_path) == '7d6150318d7d69d81c6e7f58438dea3f149fd8157ab63c7916cbdf1931052e23'
    vo = vo_path.read_text()
    models = PRIMITIVES.read_text()
    dffre = module(models, 'DFFRE')
    dffce = module(models, 'DFFCE')
    assert 'always @(posedge CLK)' in dffre and 'if (RESET)' in dffre
    assert '$recrem' not in dffre
    assert '$setuphold (posedge CLK, negedge RESET' in dffre
    assert '$recrem (negedge CLEAR, posedge CLK' in dffce
    assert 'always @(gsrt or CLEAR)' in dffce
    cells = []
    for match in re.finditer(r'^(DFF\w+)\s+(\\\S+|\w+)\s+\(\s*(.*?)\)\s*;', vo, re.S|re.M):
        prim, name, body = match.groups()
        ports = {k:v.strip() for k,v in re.findall(r'\.(\w+)\(\s*(.*?)\s*\)', body)}
        for pin in ('CLEAR', 'PRESET', 'RESET'):
            if ports.get(pin) in ('n6_5', 'phy_lock_reset'):
                cells.append({'primitive':prim, 'instance':name, 'pin':pin, **ports})
    counts = dict(Counter(r[r['pin']]+'|'+r['CLK'] for r in cells))
    assert counts == {'n6_5|vid_hclk':161, 'n6_5|phy_clk':105, 'phy_lock_reset|phy_clk':9}
    source = BUILD/'source/tang/rtl/usb/usb_msc_port.v'
    msc = source.read_text()
    assert 'if (hreset || quad_done) gathered <= 3\'d0;' in msc
    assert 'gather <= 32\'d0' in msc
    assert '8\'h04: hrdata <= {level_h' in msc
    result = {
        'hardware':False, 'checks':'PASS', 'vo_sha256':digest(vo_path),
        'direct_fanout_count':len(cells), 'by_net_clock':counts,
        'DFFRE_RESET':'synchronous; reset precedence over CE',
        'DFFCE_CLEAR':'asynchronous; recrem specify check not CE-qualified',
        'gathered_and_gather_are_distinct':True,
        'MSC_status_bits':{'seen_bus_reset':2, 'seen_bot_reset':3, 'quiet_h':4,
                           'online':5, 'highspeed':6, 'lost':7, 'owner_h':8, 'serve':9},
        'source_sha256':digest(source), 'official_model_sha256':digest(PRIMITIVES),
        'scope':'direct named primitive pin inventory; no analog/MTBF or full reset-cone qualification',
    }
    (HERE/'raw_reset_fanout.json').write_text(json.dumps({'hardware':False,'vo':str(vo_path),
        'vo_sha256':digest(vo_path),'count':len(cells),'cells':cells},indent=2)+'\n')
    (HERE/'facts.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
