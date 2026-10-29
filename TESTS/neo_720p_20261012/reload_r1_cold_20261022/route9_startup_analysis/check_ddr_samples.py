#!/usr/bin/env python3
"""Independent small-path check of DDR SDF; no imports from main extractor.

Walks DQ0, DQS0, CK and A0 PAD paths directly. Records primary DQ receiver
and extra taps separately. Numerical sums are route/primitive sums, not STA.
"""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'u_soc/g_ddr.u_ddr/u_ip/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/'
BUILDS = dict(n56r8='console_neo_n56r8_hdmi_sg4', r2='console_neo_n56r9_route2',
              r9='console_neo_n56r9_route9_dma_c150')
PADS = {
    'ddr_dq[0]': (PREFIX + 'dq_iobuf_gen[0].dq_iobuf', 'IO'),
    'ddr_dqs[0]': (PREFIX + 'dqs_iobuf_gen[0].dqs_iobuf', 'IO'),
    'ddr_dqs_n[0]': (PREFIX + 'dqs_iobuf_gen[0].dqs_iobuf', 'IOB'),
    'ddr_ck': (PREFIX + 'u_clk_gen', 'O'),
    'ddr_ck_n': (PREFIX + 'u_clk_gen', 'OB'),
    'ddr_addr[0]': (PREFIX + 'cmd_line_obuf_gen[6].cmd_line_obuf', 'O')}


def values(text):
    triplets = re.findall(r'\(([-\d.:]+)\)', text)
    assert len(triplets) in (1, 2)
    triplets = [[round(float(n) * 1000) for n in t.split(':')] for t in triplets]
    assert all(len(t) == 3 for t in triplets)
    return dict(rise_ps=triplets[0], fall_ps=triplets[-1])


def sums(parts, inverted=False):
    result = {}
    for edge in ('rise', 'fall'):
        reverse = 'fall' if edge == 'rise' else 'rise'
        result[edge+'_ps'] = [sum(p[(reverse if inverted and j < len(parts)-1 else edge)+'_ps'][i]
            for j, p in enumerate(parts)) for i in range(3)]
    return result


def extract(path):
    io, routes, instance = {}, {}, None
    with path.open() as f:
        for number, line in enumerate(f, 1):
            line = re.sub(r'\\(.)', r'\1', line.strip())
            m = re.fullmatch(r'\(INSTANCE (.+)\)', line)
            if m:
                instance = m[1]
            m = re.fullmatch(r'\(IOPATH (\S+) (\S+) (.+)\)', line)
            if m and instance and instance.startswith(PREFIX):
                io[(instance, m[1], m[2])] = dict(source=instance+'/'+m[1],
                    destination=instance+'/'+m[2], line=number, **values(m[3]))
            m = re.fullmatch(r'\(INTERCONNECT (\S+) (\S+) (.+)\)', line)
            if m and (PREFIX in m[1] or PREFIX in m[2]):
                assert (m[1], m[2]) not in routes
                routes[(m[1], m[2])] = dict(source=m[1], destination=m[2],
                                           line=number, **values(m[3]))

    def incoming(node):
        found = [v for (s, d), v in routes.items() if d == node]
        assert len(found) == 1, (node, found)
        return found[0]

    def outgoing(node):
        return [v for (s, d), v in routes.items() if s == node]

    rows = {}
    for pad, (buf, pin) in PADS.items():
        upstream = incoming(buf+'/I')
        parts = [upstream, io[(buf, 'I', pin)]]
        inverse = pin in ('OB', 'IOB')
        rows[pad+':out'] = dict(segments=parts, **sums(parts, inverse))
        drv, qpin = upstream['source'].rsplit('/', 1)
        launches = [v for (c, s, d), v in io.items()
                    if c == drv and d == qpin and s in ('FCLK', 'PCLK', 'TCLK')]
        assert len(launches) == 1
        parts = launches+parts
        rows[pad+':launch'] = dict(segments=parts, **sums(parts, inverse))
        if pin not in ('IO', 'IOB'):
            continue
        next_arcs = outgoing(buf+'/O')
        assert len(next_arcs) == 1
        parts = [io[(buf, pin, 'O')], next_arcs[0]]
        receiver, receiver_pin = parts[-1]['destination'].rsplit('/', 1)
        if (receiver, receiver_pin, 'DO') in io:
            delay_arc = io[(receiver, receiver_pin, 'DO')]
            branches = outgoing(receiver+'/DO')
            primary = [v for v in branches if v['destination'].endswith('u_ides8_mem/D')]
            assert len(primary) == 1
            rows[pad+':extra_receivers'] = [v for v in branches if v != primary[0]]
            parts += [delay_arc, primary[0]]
        rows[pad+':in'] = dict(segments=parts, **sums(parts))
    return rows


def main():
    data = dict(hardware_access=False, timing_qualification=False,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), builds={})
    for label, directory in BUILDS.items():
        sdf = ROOT/'tang/impl'/directory/'impl/pnr/console_neo.sdf'
        rows = extract(sdf)
        main_result = json.loads((HERE.parent/'route9_ddr_io_compare'/(label+'.json')).read_text())
        checked = 0
        for name, row in rows.items():
            if name.endswith(':extra_receivers'):
                continue
            for edge in ('rise_ps', 'fall_ps'):
                assert row[edge] == main_result['paths'][name][edge], (label, name, edge)
            checked += 1
        data['builds'][label] = dict(sdf=str(sdf), sdf_sha256=hashlib.sha256(sdf.read_bytes()).hexdigest(),
            main_result_sha256=hashlib.sha256((HERE.parent/'route9_ddr_io_compare'/(label+'.json')).read_bytes()).hexdigest(),
            independently_checked_paths=checked, samples=rows)
        print(label, checked, 'paths match', flush=True)
    data['passed'] = True
    (HERE/'independent_ddr_samples.json').write_text(json.dumps(data, indent=2)+'\n')


if __name__ == '__main__':
    main()
