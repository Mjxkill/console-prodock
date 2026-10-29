#!/usr/bin/env python3
"""Follow all 32 DQ PAD taps through LUTs to the first calibration FF.

Read-only inputs; no hardware or timing qualification. LUT polarity is proven
from INIT for the selected input. Arithmetic SDF sums end at D, not Q.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from route_scan_timing_candidates import cells
from prove_geometry_controls import parameters

PREFIX = 'u_soc/g_ddr.u_ddr/u_ip/gw3_top/u_ddr_phy_top/u_ddr_phy_wds/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    io, routes, instance = {}, {}, None
    with path.open() as f:
        for number, line in enumerate(f, 1):
            line = re.sub(r'\\(.)', r'\1', line.strip())
            m = re.fullmatch(r'\(INSTANCE (.+)\)', line)
            if m:
                instance = m[1]
            m = re.fullmatch(r'\(IOPATH ([^\s()]+) ([^\s()]+)\s*(\(.+)\)', line)
            if m and instance and instance.startswith(PREFIX):
                source, dest = instance+'/'+m[1], instance+'/'+m[2]
                target = io
            else:
                m = re.fullmatch(r'\(INTERCONNECT (\S+) (\S+) (.+)\)', line)
                if not m or not (PREFIX in m[1] or PREFIX in m[2]):
                    continue
                source, dest, target = m[1], m[2], routes
            triplets = re.findall(r'\(([-\d.:]+)\)', m[3])
            assert len(triplets) in (1, 2), line
            vv = [[round(float(n)*1000) for n in t.split(':')] for t in triplets]
            assert all(len(v) == 3 for v in vv)
            assert (source, dest) not in target
            target[source, dest] = dict(source=source, destination=dest, line=number,
                rise_ps=vv[0], fall_ps=vv[-1], polarity='positive',
                kind='cell' if target is io else 'route')
    return io, routes


def polarity(cell, pin, params):
    count = int(cell['kind'][3:])
    bit = int(pin[1:])
    assert pin == 'I'+str(bit) and 0 <= bit < count
    m = re.fullmatch(r"(\d+)'h([a-fA-F0-9]+)", params['INIT'])
    assert m and int(m[1]) == 1 << count
    value = int(m[2], 16)
    directions = set()
    for state in range(1 << count):
        if state & (1 << bit):
            continue
        a, b = (value >> state) & 1, (value >> (state | (1 << bit))) & 1
        if a != b:
            directions.add('positive' if b > a else 'negative')
    assert len(directions) == 1, (cell, pin, params, directions)
    return directions.pop()


def total(parts, edge):
    accum = [0, 0, 0]
    for part in reversed(parts):
        accum = [a+b for a, b in zip(accum, part[edge+'_ps'])]
        if part['polarity'] == 'negative':
            edge = 'fall' if edge == 'rise' else 'rise'
    return accum, edge


def main():
    result = dict(scope='PAD to first calibration FF D pin, conditional SDF sums only',
                  hardware_access=False, timing_qualification=False, builds={})
    for label in ('n56r8', 'r2', 'r9'):
        main_json = HERE.parent/'route9_ddr_io_compare'/(label+'.json')
        base = json.loads(main_json.read_text())
        build = Path(base['build'])
        vo, sdf = (build/'impl/pnr'/('console_neo.'+suffix) for suffix in ('vo', 'sdf'))
        assert sha(vo) == base['identities']['impl/pnr/console_neo.vo']
        assert sha(sdf) == base['identities']['impl/pnr/console_neo.sdf']
        text = vo.read_text()
        cc, pp = cells(text), parameters(text)
        io, routes = parse(sdf)
        outgoing = {}
        for (s, d), arc in routes.items():
            outgoing.setdefault(s, []).append(arc)
        paths = {}
        for bit in range(32):
            key = f'ddr_dq[{bit}]:in_fabric_tap0'
            original = base['paths'][key]
            parts = []
            for part in original['segments']:
                selected = (io if part['type'] == 'cell' else routes)[part['source'], part['destination']]
                for edge in ('rise_ps', 'fall_ps'):
                    assert selected[edge] == part[edge]
                parts.append(dict(selected))
            lut_cells = []
            visited = set()
            while True:
                name, pin = parts[-1]['destination'].rsplit('/', 1)
                assert name not in visited
                visited.add(name)
                cell = cc[name]
                if cell['kind'].startswith('DFF'):
                    assert pin == 'D'
                    endpoint = dict(name=name, cell=cell, parameters=pp.get(name, {}),
                                    clock_net=cell['pins']['CLK'])
                    break
                assert cell['kind'].startswith('LUT')
                selected = dict(io[name+'/'+pin, name+'/F'])
                selected['polarity'] = polarity(cell, pin, pp[name])
                parts.append(selected)
                lut_cells.append(dict(name=name, pin=pin, cell=cell, parameters=pp[name],
                                      selected_input_polarity=selected['polarity']))
                next_arcs = outgoing[name+'/F']
                assert len(next_arcs) == 1, (name, next_arcs)
                parts.append(dict(next_arcs[0]))
            assert len(lut_cells) == 2 and all(c['selected_input_polarity'] == 'negative' for c in lut_cells)
            rising, rise_pad = total(parts, 'rise')
            falling, fall_pad = total(parts, 'fall')
            assert rise_pad == 'rise' and fall_pad == 'fall'
            paths[f'ddr_dq[{bit}]'] = dict(endpoint=endpoint, lut_cells=lut_cells,
                segments=parts, rise_ps=rising, fall_ps=falling, net_polarity='positive',
                condition='Other bits of the byte held low sensitize the NOR/NAND reduction path')
        result['builds'][label] = dict(paths=paths, input_sha256={str(vo):sha(vo), str(sdf):sha(sdf),
            str(main_json):sha(main_json)}, max_endpoint_rise_ps=max(p['rise_ps'][2] for p in paths.values()),
            max_endpoint_fall_ps=max(p['fall_ps'][2] for p in paths.values()))
        print(label, '32 paths', result['builds'][label]['max_endpoint_rise_ps'], 'ps max', flush=True)
    for label in ('n56r8', 'r2'):
        for bit, row in result['builds'][label]['paths'].items():
            reference = result['builds']['r9']['paths'][bit]
            assert row['endpoint'] == reference['endpoint']
            assert row['lut_cells'] == reference['lut_cells']
    result['same_luts_and_endpoints_all_builds'] = True
    result['limits'] = ['Not setup/hold slack: stops at D and excludes capture-clock timing.',
        'NOR/NAND arcs are sensitized only for appropriate stable other inputs; no hazards or analog margins modeled.',
        'No measured DDR training states, PCB flight time or DRAM timing is included.']
    result['script_sha256'] = sha(Path(__file__))
    (HERE/'calibration_taps.json').write_text(json.dumps(result, indent=2)+'\n')
    with (HERE/'calibration_taps.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['pad', 'first_ff', 'clock_net']+[f'{label}_{edge}_{corner}_ps'
            for label in result['builds'] for edge in ('rise', 'fall') for corner in ('min', 'typ', 'max')])
        for bit in range(32):
            name=f'ddr_dq[{bit}]'; endpoint=result['builds']['r9']['paths'][name]['endpoint']
            w.writerow([name, endpoint['name'], endpoint['clock_net']] + [v for label in result['builds']
                for edge in ('rise', 'fall') for v in result['builds'][label]['paths'][name][edge+'_ps']])


if __name__ == '__main__':
    main()
