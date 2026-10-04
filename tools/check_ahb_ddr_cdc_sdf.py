#!/usr/bin/env python3
"""Measure AHB, GPU command or passive USB trace Gray crossings in routed SDF.

Reports clock-to-Q plus interconnect to the first synchronizer D, including
all three PVT values. This is not an analog metastability/MTBF simulation.
The asynchronous clock-group cuts remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    kind = p.add_mutually_exclusive_group()
    kind.add_argument('--usb-idle', action='store_true', help='audit the 18 passive USB trace Gray bits')
    kind.add_argument('--gpu', action='store_true', help='audit the 16 GPU command FIFO Gray bits')
    a = p.parse_args()
    base = a.stage/'impl/pnr'/('console_'+a.stage.name)
    sdf = base.with_suffix('.sdf')
    fs = base.with_suffix('.fs')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    text = sdf.read_text().replace('\\/', '/').replace('\\.', '.')
    if '(TIMESCALE 1 ns)' not in text:
        raise SystemExit('Expected SDF in ns')
    prefix = 'u_accel/' if a.gpu else 'u_usb_idle_trace/' if a.usb_idle else 'u_soc/g_ddr.u_ddr/u_bridge/'
    fifos = {'u_commands':8} if a.gpu else {'u_commands':3, 'u_replies':6} if a.usb_idle else {'u_requests':3, 'u_responses':3}
    cells = {}
    for block in text.split('\n  (CELL\n')[1:]:
        name = re.search(r'\(INSTANCE ([^\s)]+)\)', block)
        if not name or not name[1].startswith(prefix):
            continue
        typ = re.search(r'\(CELLTYPE "([^"]+)"\)', block)
        cq = re.search(r'\(IOPATH CLK Q \(([^)]+)\)\)', block)
        if typ and cq:
            cells[name[1]] = (typ[1], [float(v) for v in cq[1].split(':')])
    rows = []
    expected = {(fifo, direction, bit) for fifo, bits in fifos.items()
                for direction in ('rd', 'wr') for bit in range(bits)}
    for src, dst, delay in re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([^)]+)\)\)', text):
        match = re.fullmatch(re.escape(prefix)+'('+'|'.join(fifos)+r')/(rd|wr)_gray_s1_([0-9])_s\d+/D', dst)
        if not match:
            continue
        key = (match[1], match[2], int(match[3]))
        if key not in expected:
            raise SystemExit('Duplicate Gray first-stage destination: '+dst)
        expected.remove(key)
        cell, port = src.rsplit('/', 1)
        typ, cq = cells.get(cell, ('', []))
        if port != 'Q' or not typ.startswith('DFF') or len(cq) != 3:
            raise SystemExit('Gray source is not a registered Q: '+src)
        net = [float(v) for v in delay.split(':')]
        if len(net) != 3:
            raise SystemExit('Expected three PVT values: '+delay)
        total = [round(x+y, 3) for x,y in zip(cq, net)]
        rows.append(dict(fifo=key[0], direction=key[1], bit=key[2], source=src,
                         destination=dst, clock_to_q_ns=cq, net_ns=net, total_ns=total))
    if expected:
        raise SystemExit('Missing Gray bits: '+repr(expected))
    # Conservative common bound: shortest period of either domain.
    # AHB is 80 MHz and DDR UI is 75 MHz; the passive USB trace also crosses
    # to 80 MHz. Use the shorter period for both directions of either FIFO.
    limit = 1000/80
    groups = []
    for fifo in fifos:
        for direction in ('wr', 'rd'):
            group = [r for r in rows if (r['fifo'],r['direction'])==(fifo,direction)]
            delays = [x for r in group for x in r['total_ns']]
            groups.append(dict(fifo=fifo,direction=direction,max_total_ns=max(delays),
                               conservative_spread_ns=round(max(delays)-min(delays),3)))
    ok = all(g['max_total_ns'] < limit and g['conservative_spread_ns'] < limit for g in groups)
    report = dict(stage=str(a.stage), sdf_sha256=sha(sdf), bitstream_sha256=sha(fs),
                  bound_ns=limit, pass_routed_gray_bound=ok, groups=groups, paths=rows,
                  limits=['Official routed SDF; no alteration of clock-group cuts',
                          'PVT delay bound only, not an analog metastability or MTBF proof',
                          'Does not validate PHY-internal CDC or every other system crossing'])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':ok,'paths':len(rows),'groups':groups}))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
