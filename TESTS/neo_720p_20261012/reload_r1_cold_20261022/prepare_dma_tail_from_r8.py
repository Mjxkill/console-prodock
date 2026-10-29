#!/usr/bin/env python3
"""Prepare a two-LUT CST experiment from completed R8; never launch Gowin.

No RTL, existing constraint, build directory or board is modified. The SDF
costs are observations of R8, not predictions for the proposed placement.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

import route_scan_timing_candidates as r
import review_route7_paths as review
from route_scan_observer import parameter

BASE = r.ROOT / 'tang/impl/console_neo_n56r9_route8_hdmi_c150'
NAMES = ('u_accel/u_dma/n2949_s17', 'u_accel/u_dma/n2949_s12')
REGION = 'R[55:75]C[45:65]'
HASHES = {
    'sources.json': '9347bc6f5d7c89ec31cbcc90dc5eed1a6be1850500216c7458e4c0dbbc96d92d',
    'console_neo.vg': r.NETSHA,
    'source/tang/boards/neo/neo.cst': '99fa8e7965b60d9b25e54b3ae16dd67a6900f7eccbbefaccadb310b11f6bd567',
    'source/tang/boards/neo/neo.sdc': r.SDC,
    'impl/pnr/console_neo.tr': 'b883e99e937cf9bf8cd81fcd6176fe0e81423ad7f9afa5d62f984668c70345ad',
    'impl/pnr/console_neo.fs': '2772efc295b17758c6e09757ba7085ebbf1b224f3b8d17334934733f3a0c9e03',
    'impl/pnr/console_neo.vo': '52172657d2c16db8496230e3b1b90dfe0925fef30fca66bcd4cbc5b72c5e09fd',
    'impl/pnr/console_neo.sdf': 'f75233dde44e97b062793c0f2389ac4894707458c591d511b9ce021a55116917',
}
ADDITION = '\n// Proposal only: two DMA position mux LUTs; all R8 constraints preserved.\n' + ''.join(
    f'INS_LOC "{n}" {REGION};\n' for n in sorted(NAMES))


def statements(text):
    clean = '\n'.join(line.split('//', 1)[0] for line in text.splitlines())
    return [' '.join(s.split()) for s in clean.split(';') if s.strip()]


def validate_delta(old, new):
    before, after = statements(old), statements(new)
    assert after == before + [f'INS_LOC "{n}" {REGION}' for n in sorted(NAMES)]
    anchors = [re.fullmatch(r'INS_LOC "([^"*?]+)" (.+)', s)[1]
               for s in after if s.startswith('INS_LOC ')]
    assert len(anchors) == len(set(anchors))
    assert r.fixed_constraints(old) == r.fixed_constraints(new)


def semantic_tests(old, new):
    validate_delta(old, new)
    wrong = [new + 'IO_LOC "clk" A1;', new + 'CLOCK_LOC "gpu_clk" LOCAL_CLOCK;',
             new.replace('R102C150[1][A]', 'R102C149[1][A]'),
             new.replace('R[60:80]C[90:110]', 'R[60:80]C[89:110]'),
             new + f'INS_LOC "u_accel/u_dma/c_ack_s0" {REGION};',
             new + f'INS_LOC "{NAMES[0]}" {REGION};',
             new.replace(REGION, 'R[55:75]C[44:65]'),
             new.replace(f'INS_LOC "{NAMES[0]}" {REGION};', ''),
             new.replace(NAMES[0], 'u_accel/u_dma/n2949_s*')]
    for candidate in wrong:
        assert candidate != new
        try:
            validate_delta(old, candidate)
        except (AssertionError, TypeError):
            continue
        raise AssertionError('Unexpected CST mutation accepted')
    return dict(passed=True, rejected_mutations=len(wrong), positive_cases=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Preserve existing proposals'
    for name, digest in HASHES.items():
        assert r.sha(BASE / name) == digest, name
    qualified = review.read(BASE)
    assert qualified['timing_checks_ns'] == dict(setup=-3.494, hold=.124, recovery=-1.337, removal=.347)
    source_manifest = json.loads((BASE / 'sources.json').read_text())
    assert source_manifest == {str(p.relative_to(BASE / 'source')): r.sha(p)
                               for p in (BASE / 'source').rglob('*') if p.is_file()}
    old = (BASE / 'source/tang/boards/neo/neo.cst').read_text()
    candidate = old + ADDITION
    tests = semantic_tests(old, candidate)
    anchors = dict(re.findall(r'INS_LOC\s+"([^"*?]+)"\s+([^;]+);', old))
    cc, params, drivers, loads = r.indexed_netlist(BASE / 'impl/pnr/console_neo.vo')
    text = (BASE / 'impl/pnr/console_neo.tr').read_text()
    locations = {}
    row = re.compile(r'\s*[-\d.]+\s+[-\d.]+\s+t\w+\s+\w+\s+\d+\s+(\S+)\s+(\S+)\s*$')
    for line in text.splitlines():
        m = row.match(line)
        if m:
            locations.setdefault(m[2].rsplit('/', 1)[0], set()).add(m[1])
    setup = review.paths(review.section(text, '1'))
    critical = min((p for p in setup if p['destination'] == 'u_accel/u_dma/position_3_s1'),
                   key=lambda p: p['slack_ns'])
    assert critical['slack_ns'] == -3.494
    bodies = r.modules(BASE / 'console_neo.vg')
    mapped = {name: r.cells(body) for name, body in bodies.items()}
    targets = []
    for name in NAMES:
        parts, module = name.split('/'), 'console_neo'
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        source = mapped[module][parts[-1]]
        assert source['kind'] == cc[name]['kind'] == 'LUT4'
        assert parameter(bodies[module], parts[-1]) == params[name]['INIT'].lower()
        assert len(loads[cc[name]['pins']['F']]) == 1
        pins = {}
        for pin, net in cc[name]['pins'].items():
            pins[pin] = dict(net=net, drivers=drivers[net], loads=loads[net], fanout=len(loads[net]))
        targets.append(dict(instance=name, source=source, routed=cc[name], parameters=params[name],
                            locations=sorted(locations.get(name, [])), pins=pins, proposed_region=REGION))
    # Restrict the direct-anchor claim to all immediate source drivers and
    # destinations of the two LUTs; unrelated loads are documented separately.
    immediate = set(NAMES)
    for name in NAMES:
        for pin, net in cc[name]['pins'].items():
            if pin == 'F':
                immediate.update(n for n, _, _ in loads[net])
            else:
                immediate.update(n for n, _, _ in drivers[net])
    direct = {name: anchors[name] for name in immediate if name in anchors}
    assert not direct
    boundary = {name: dict(cell=cc[name], parameters=params.get(name),
                           locations=sorted(locations.get(name, [])), constraint=anchors.get(name))
                for name in sorted(immediate - set(NAMES))}
    # The SDF contains the otherwise unprinted incoming branches. Its max
    # values match the four critical route delays printed in the STA report.
    arcs = []
    sdf = BASE / 'impl/pnr/console_neo.sdf'
    with sdf.open() as stream:
        for line in stream:
            if 'INTERCONNECT' not in line or not any(n.rsplit('/', 1)[-1] in line for n in NAMES):
                continue
            m = re.fullmatch(r'\s*\(INTERCONNECT (\S+) (\S+) \(([-\d.]+):([-\d.]+):([-\d.]+)\)\)\s*', line)
            assert m, line
            source, dest = (m[i].replace('\\/', '/') for i in (1, 2))
            if source.rsplit('/', 1)[0] in NAMES or dest.rsplit('/', 1)[0] in NAMES:
                arcs.append(dict(source=source, destination=dest, min_ns=float(m[3]),
                                 typ_ns=float(m[4]), max_ns=float(m[5])))
    assert len(arcs) == 9
    for name in NAMES:
        assert {a['destination'].rsplit('/', 1)[1] for a in arcs if a['destination'].rsplit('/', 1)[0] == name} == {'I0', 'I1', 'I2', 'I3'}
    for node, delay in [('n2949_s17/I2', 4.489), ('n2949_s12/I0', 1.989), ('position_3_s1/D', 7.328)]:
        assert next(a['max_ns'] for a in arcs if a['destination'] == 'u_accel/u_dma/' + node) == delay
    contract = r.before_build('neo', candidate=True)
    files = [BASE / n for n in HASHES] + [BASE / 'impl/pnr/console_neo.vo', sdf,
             BASE / 'qualification.json', BASE / 'automatic_checks.json', Path(__file__)]
    files += [Path(m.__file__).resolve() for m in list(sys.modules.values())
              if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py'
              and str(Path(m.__file__).resolve()).startswith(str(r.ROOT) + '/')]
    record = dict(status='PROPOSAL_NOT_ROUTED', hardware_access=False, route_started=False,
        base=str(BASE), netlist_sha256=r.NETSHA, sdc_sha256=r.SDC,
        changed_files=['tang/boards/neo/neo.cst'], existing_constraints_unchanged=True,
        targets=targets, immediate_boundary=boundary, direct_constraints_on_targets_and_boundary=direct,
        related_blitter_anchors={n: anchors[n] for n in anchors if n.startswith('u_accel/u_blitter/')
                                and anchors[n] == 'R[1:25]C[140:175]'},
        measured_critical_path=critical, measured_sdf_arcs=arcs, cst_tests=tests,
        local_regressions=contract['local_regressions'],
        candidate_cst_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        input_sha256={str(p): r.sha(p) for p in sorted(set(files))},
        limits=['No timing gain predicted. Two LUT outputs have one sink each, but all input fanouts and whole-design routing can change.',
                's_addr3 at R3C149 is not anchored; its proximity to the existing FIFO/blitter region is correlation, not proof of causation.',
                'Unknown locations mean absent from the printed STA paths; encrypted placement databases were not decoded.',
                'SDF min/typ/max describe R8 at its tool corners, not path slack or the proposed experiment.',
                'No R9 eight-cell constraints are included; this is an independent proposal from R8.'])
    args.out.mkdir()
    (args.out / 'review.json').write_text(json.dumps(record, indent=2) + '\n')
    (args.out / 'candidate.cst').write_text(candidate)
    (args.out / 'constraints.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True), fromfile='R8_C150', tofile='DMA_tail_two_LUTs')))
    print(json.dumps(dict(passed=True, added_cells=2, rejected_cst_mutations=tests['rejected_mutations'],
                          direct_anchors=len(direct), measured_sdf_arcs=len(arcs), route_started=False)))


if __name__ == '__main__':
    main()
