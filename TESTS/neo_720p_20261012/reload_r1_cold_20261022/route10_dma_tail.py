#!/usr/bin/env python3
"""R10: only two DMA mux LUTs constrained, using exact completed R8 inputs.

Check-only preparation and verification never start Gowin. Routing requires
the separately reviewed --route-reviewed action. No hardware access exists.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import route_scan_timing_candidates as r
import review_route7_paths as review
from route_scan_observer import parameter

BASE = r.ROOT / 'tang/impl/console_neo_n56r9_route8_hdmi_c150'
OUT = r.ROOT / 'tang/impl/console_neo_n56r9_route10_dma_tail_c150'
PREPARED = r.HERE / 'route10_dma_tail_prepared'
PROPOSAL = r.HERE / 'dma_tail_from_r8_proposal'
REGION = 'R[55:75]C[45:65]'
NAMES = ('u_accel/u_dma/n2949_s12', 'u_accel/u_dma/n2949_s17')
PROPOSAL_SHA = '02adc9e25ed16206b789d95b8519308398a74e8811cb8a8ca9fa3b8b8422ea85'
CST_SHA = 'a31b04762587ce60d71e6c0f1bf2d39eef36a514c7f72abe9f90064fe01e1109'
HASHES = {
    'sources.json': '9347bc6f5d7c89ec31cbcc90dc5eed1a6be1850500216c7458e4c0dbbc96d92d',
    'console_neo.vg': r.NETSHA,
    'source/tang/boards/neo/neo.cst': '99fa8e7965b60d9b25e54b3ae16dd67a6900f7eccbbefaccadb310b11f6bd567',
    'source/tang/boards/neo/neo.sdc': r.SDC,
    'source/tang/boards/neo/timing_closure.json': 'c5cad2cb27378b89fc2dc45c7fd7d101b39d324ccd67dc226a82526768221f8c',
    'build.tcl': '935c700d4b752e73159361c86f7c8ba984e084ecae9bbd0f49954c6de3a0d1de',
    'impl/pnr/console_neo.tr': 'b883e99e937cf9bf8cd81fcd6176fe0e81423ad7f9afa5d62f984668c70345ad',
    'impl/pnr/console_neo.vo': '52172657d2c16db8496230e3b1b90dfe0925fef30fca66bcd4cbc5b72c5e09fd',
    'impl/pnr/console_neo.fs': '2772efc295b17758c6e09757ba7085ebbf1b224f3b8d17334934733f3a0c9e03',
    'impl/pnr/console_neo.sdf': 'f75233dde44e97b062793c0f2389ac4894707458c591d511b9ce021a55116917',
}
# Keep even the comment identical to the reviewed proposal: exact CST SHA.
ADDITION = '\n// Proposal only: two DMA position mux LUTs; all R8 constraints preserved.\n' + ''.join(
    f'INS_LOC "{n}" {REGION};\n' for n in NAMES)
COPIED = ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
          'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json')


def normalized(value):
    return json.loads(json.dumps(value))


def statements(text):
    clean = '\n'.join(line.split('//', 1)[0] for line in text.splitlines())
    return [' '.join(s.split()) for s in clean.split(';') if s.strip()]


def validate_delta(base, candidate):
    old, new = statements(base), statements(candidate)
    expected = [f'INS_LOC "{n}" {REGION}' for n in NAMES]
    assert len(NAMES) == len(set(NAMES)) == 2
    assert new == old + expected, 'Only the two explicit additions are allowed'
    anchors = []
    for statement in new:
        if statement.startswith('INS_LOC '):
            match = re.fullmatch(r'INS_LOC "([^"*?]+)" (.+)', statement)
            assert match, 'No wildcard or malformed placement'
            anchors.append(match[1])
    assert len(anchors) == len(set(anchors)), 'Duplicate/overridden placement'
    assert r.fixed_constraints(base) == r.fixed_constraints(candidate)
    for channel, row, slot in ((0, 102, 1), (1, 102, 2), (2, 57, 1)):
        line = f'INS_LOC "u_hdmi/g_reset[{channel}].reset_sync_fall_s1" R{row}C150[{slot}][A]'
        assert old.count(line) == new.count(line) == 1
    return dict(passed=True, added_cells=2, existing_statements_unchanged=len(old),
                hdmi_c150_unchanged=True, clock_io_and_nonplacement_unchanged=True)


def sdf_arcs(path):
    arcs = []
    with path.open() as stream:
        for line in stream:
            if 'INTERCONNECT' not in line or not any(n.rsplit('/', 1)[1] in line for n in NAMES):
                continue
            match = re.fullmatch(r'\s*\(INTERCONNECT (\S+) (\S+) \(([-\d.]+):([-\d.]+):([-\d.]+)\)\)\s*', line)
            assert match, line
            source, destination = (match[i].replace('\\/', '/') for i in (1, 2))
            if source.rsplit('/', 1)[0] in NAMES or destination.rsplit('/', 1)[0] in NAMES:
                arcs.append(dict(source=source, destination=destination, min_ns=float(match[3]),
                                 typ_ns=float(match[4]), max_ns=float(match[5])))
    assert len(arcs) == 9
    assert len({(a['source'], a['destination']) for a in arcs}) == 9
    return arcs


def inputs():
    for name, digest in HASHES.items():
        assert r.sha(BASE / name) == digest, name
    assert r.sha(PROPOSAL / 'review.json') == PROPOSAL_SHA
    assert r.sha(PROPOSAL / 'candidate.cst') == CST_SHA
    proposal = json.loads((PROPOSAL / 'review.json').read_text())
    for path, digest in proposal['input_sha256'].items():
        assert r.sha(Path(path)) == digest, path
    original = json.loads((BASE / 'sources.json').read_text())
    assert original == {str(p.relative_to(BASE / 'source')): r.sha(p)
                        for p in (BASE / 'source').rglob('*') if p.is_file()}
    old = (BASE / 'source/tang/boards/neo/neo.cst').read_text()
    candidate = old + ADDITION
    assert candidate == (PROPOSAL / 'candidate.cst').read_text()
    semantic = validate_delta(old, candidate)
    metadata = json.loads((BASE / 'source/tang/boards/neo/timing_closure.json').read_text())
    assert metadata['hdmi_reset_column'] == 150 and metadata['hdmi_dce_site'] == 'SG[4]'
    ddr = r.audit(BASE / 'source', variant='neo-fifo-registers')
    assert ddr['passed']
    measured = review.read(BASE)
    assert measured['timing_checks_ns'] == dict(setup=-3.494, hold=.124, recovery=-1.337, removal=.347)
    assert sdf_arcs(BASE / 'impl/pnr/console_neo.sdf') == proposal['measured_sdf_arcs']
    cc, params, drivers, loads = r.indexed_netlist(BASE / 'impl/pnr/console_neo.vo')
    bodies = r.modules(BASE / 'console_neo.vg')
    mapped = {name: r.cells(body) for name, body in bodies.items()}
    targets = proposal['targets']
    assert sorted(t['instance'] for t in targets) == list(NAMES)
    for target in targets:
        name = target['instance']
        assert cc[name] == target['routed'] and params[name] == target['parameters']
        parts, module = name.split('/'), 'console_neo'
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        assert mapped[module][parts[-1]] == target['source']
        assert target['source']['kind'] == 'LUT4'
        assert parameter(bodies[module], parts[-1]) == params[name]['INIT'].lower()
        assert len(loads[cc[name]['pins']['F']]) == 1
        for pin, net in cc[name]['pins'].items():
            actual = dict(net=net, drivers=drivers[net], loads=loads[net], fanout=len(loads[net]))
            assert normalized(actual) == target['pins'][pin]
    code = [Path(__file__), r.HERE / 'test_route10_dma_tail.py', Path(review.__file__),
            r.ROOT / 'optimizer/reports.py', r.ROOT / 'tools/check_neo_timing.py']
    code += [Path(m.__file__).resolve() for m in list(sys.modules.values())
             if getattr(m, '__file__', None) and str(Path(m.__file__).resolve()).startswith(str(r.ROOT) + '/')
             and Path(m.__file__).suffix == '.py']
    used = code + [BASE / name for name in set(HASHES) | set(COPIED)]
    used += [Path(p) for p in proposal['input_sha256']]
    used += [p for p in PROPOSAL.iterdir() if p.is_file()]
    used += [BASE / name for name in ('qualification.json', 'automatic_checks.json', 'build.log',
                                     'impl/pnr/console_neo.rpt.txt')]
    used += [r.PARENT / 'impl/pnr/console_neo.rpt.txt']
    record = dict(parent_inputs=str(BASE), measured_motivation=str(BASE), output=str(OUT),
        proposal_sha256=PROPOSAL_SHA, netlist_sha256=r.NETSHA, sdc_sha256=r.SDC,
        semantic_test=semantic, source_changes=['tang/boards/neo/neo.cst'], hdmi_reset_column=150,
        grouped_cells=2, region=REGION, constrained_cells=targets,
        measured_path=proposal['measured_critical_path'], measured_sdf_arcs=proposal['measured_sdf_arcs'],
        immediate_boundary=proposal['immediate_boundary'], ddr_profile=ddr,
        hardware_access=False, synthesis=False, r9_constraints_included=False, predicted_timing=None,
        baseline_timing_ns=measured['timing_checks_ns'],
        region_reason='Near the measured n58 LUTs R54C58 and position3 register R71C34. All existing anchors remain; no registers, observer or R9 eight-cell group are moved.',
        limits=proposal['limits'] + [
            'Full placement/routing is recomputed. Compare all nine SDF arcs, incoming setup paths, recovery/removal and HDMI margins.',
            'R8 remains FAIL: five recovery violations and strict observer reset-alias audit failure are preserved, not waived.',
            'Strict target primitive/pin/INIT and observer audits may reject postroute aliases; any failure requires independent review.',
            'Preparation and route completion are not hardware qualification.'],
        inputs_sha256={str(p): r.sha(p) for p in sorted(set(used))},
        candidate_cst_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True),
                                                    fromfile='R8_C150', tofile='R10_DMA2_C150')))
    return original, candidate, normalized(record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--verify-prepared', action='store_true')
    mode.add_argument('--route-reviewed', action='store_true')
    args = parser.parse_args()
    assert not OUT.exists(), 'Never overwrite a candidate'
    original, candidate, record = inputs()
    contract = r.before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.check_only:
        PREPARED.mkdir(exist_ok=False)
        (PREPARED / 'review.json').write_text(json.dumps(record, indent=2) + '\n')
        (PREPARED / 'candidate.cst').write_text(candidate)
        (PREPARED / 'constraints.diff').write_text(record['constraints_diff'])
        print(json.dumps(dict(passed=True, grouped_cells=2, region=REGION,
                              route_started=False, hardware_access=False, prepared=str(PREPARED))))
        return
    assert record == json.loads((PREPARED / 'review.json').read_text()), 'Prepared inputs changed'
    assert r.sha(PREPARED / 'candidate.cst') == record['candidate_cst_sha256']
    assert (PREPARED / 'constraints.diff').read_text() == record['constraints_diff']
    if args.verify_prepared:
        print(json.dumps(dict(passed=True, prepared_inputs_unchanged=True,
                              route_started=False, hardware_access=False)))
        return
    OUT.mkdir()
    r.record_build(OUT, contract)
    shutil.copytree(BASE / 'source', OUT / 'source')
    (OUT / 'source/tang/boards/neo/neo.cst').write_text(candidate)
    for name in COPIED:
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE / name, dest)
    actual = {str(p.relative_to(OUT / 'source')): r.sha(p)
              for p in (OUT / 'source').rglob('*') if p.is_file()}
    assert actual.keys() == original.keys()
    assert sorted(n for n in original if original[n] != actual[n]) == record['source_changes']
    (OUT / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
    # Exact R8 options and input paths, only rebased into the isolated output.
    (OUT / 'build.tcl').write_text((BASE / 'build.tcl').read_text().replace(str(BASE), str(OUT)))
    (OUT / 'route.json').write_text(json.dumps(record, indent=2) + '\n')
    (OUT / 'constraints.diff').write_text(record['constraints_diff'])
    print('Routing ' + str(OUT), flush=True)
    with (OUT / 'build.log').open('x') as log:
        done = subprocess.run([str(r.IDE / 'bin/gw_sh'), 'build.tcl'], cwd=OUT,
                              env=r.environment(), stdout=log, stderr=log)
    log = (OUT / 'build.log').read_text()
    failed = bool(done.returncode or re.search(r'^ERROR', log, re.M) or 'Bitstream generation completed' not in log)
    (OUT / 'route_result.json').write_text(json.dumps(dict(returncode=done.returncode,
        status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED', hardware_access=False), indent=2) + '\n')
    if failed:
        raise SystemExit('Route failed')
    with (OUT / 'qualification_automatic.log').open('x') as log:
        checked = subprocess.run([sys.executable, str(r.ROOT / 'tools/check_neo_timing.py'), str(OUT)],
                                 cwd=r.ROOT, stdout=log, stderr=log, timeout=600)
    r.observer.OUT = OUT
    observed = r.observer.audit()
    (OUT / 'scan_observer_audit.json').write_text(json.dumps(observed, indent=2) + '\n')
    new_routes = r.global_nets(OUT)
    comparisons = {}
    for label, baseline in (('R3', r.PARENT), ('R8', BASE)):
        old_routes = r.global_nets(baseline)
        comparisons[label] = [dict(net=n, before=old_routes.get(n, 'local'), after=new_routes.get(n, 'local'))
                              for n in sorted(set(old_routes) | set(new_routes)) if old_routes.get(n) != new_routes.get(n)]
    unexpected = {n: new_routes[n] for n in r.LOCAL + [r.RESET_NET] if n in new_routes}
    cc, params, _, _ = r.indexed_netlist(OUT / 'impl/pnr/console_neo.vo')
    changed = [t['instance'] for t in record['constrained_cells']
               if cc.get(t['instance']) != t['routed'] or params.get(t['instance']) != t['parameters']]
    result = dict(qualification_returncode=checked.returncode, strict_observer_audit_passed=observed['passed'],
        global_comparisons=comparisons, unexpected_global_controls=unexpected,
        changed_constrained_primitives=changed, hardware_access=False, independent_review_pending=True,
        passed=checked.returncode == 0 and observed['passed'] and not any(comparisons.values())
               and not unexpected and not changed)
    (OUT / 'automatic_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    # Descriptive timing/branch report cannot turn a failed qualification into PASS.
    new_arcs = sdf_arcs(OUT / 'impl/pnr/console_neo.sdf')
    old_by_edge = {(a['source'], a['destination']): a for a in record['measured_sdf_arcs']}
    branch_comparison = [dict(before=old_by_edge.get((a['source'], a['destination'])), after=a)
                         for a in new_arcs]
    timing = dict(baseline=review.read(BASE), candidate=review.read(OUT),
                  branches=branch_comparison, no_hardware_qualification=True)
    (OUT / 'r8_comparison.json').write_text(json.dumps(timing, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    if not result['passed']:
        raise SystemExit('Candidate requires independent review; no hardware loading')


if __name__ == '__main__':
    main()
