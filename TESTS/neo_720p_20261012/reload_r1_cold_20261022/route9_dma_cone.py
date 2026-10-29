#!/usr/bin/env python3
"""R9: eight DMA cells only, exact R8 synthesis/SDC/HDMI C150 inputs.

Preparation never starts Gowin or writes in R8. Routing is a separate explicit
--route-reviewed action, requiring the exact saved preparation and board guard.
R7 timing motivates the region; R8 results are neither required nor predicted.
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
MEASURED = r.ROOT / 'tang/impl/console_neo_n56r9_route7_hdmi_c140'
OUT = r.ROOT / 'tang/impl/console_neo_n56r9_route9_dma_c150'
PREPARED = r.HERE / 'route9_dma_prepared'
REGION = 'R[40:65]C[65:90]'
NAMES = tuple('u_accel/u_dma/' + n for n in (
    'n66_s4', 'c_ack_s2', 'n84_s1', 'n76_s2',
    'c_ack_s0', 'f_done_s0', 'w_done_s0', 'write_accepted_s0'))
HASHES = {
    'sources.json': '9347bc6f5d7c89ec31cbcc90dc5eed1a6be1850500216c7458e4c0dbbc96d92d',
    'console_neo.vg': r.NETSHA,
    'source/tang/boards/neo/neo.cst': '99fa8e7965b60d9b25e54b3ae16dd67a6900f7eccbbefaccadb310b11f6bd567',
    'source/tang/boards/neo/neo.sdc': r.SDC,
    'source/tang/boards/neo/timing_closure.json': 'c5cad2cb27378b89fc2dc45c7fd7d101b39d324ccd67dc226a82526768221f8c',
    'build.tcl': '935c700d4b752e73159361c86f7c8ba984e084ecae9bbd0f49954c6de3a0d1de',
}
MEASURED_HASHES = {
    'console_neo.vg': r.NETSHA,
    'impl/pnr/console_neo.tr': '7727550c6d134de0974785e55602fef807a03d8a6f740a06264a83007d9a70af',
    'impl/pnr/console_neo.vo': '4d4a5af77b850a2e194b8932c3e6a546db6cfe0a07e7e7f04e338e9d29816832',
    'impl/pnr/console_neo.fs': '941305b0e2df43cfc8eb9acd06ff220a807ad9af068f964e6e964459d62eda79',
}
ADDITION = '\n// R9: eight DMA cells only; R8 HDMI C150 and all other anchors unchanged.\n' + ''.join(
    f'INS_LOC "{name}" {REGION};\n' for name in sorted(NAMES))
COPIED = ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
          'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json')


def statements(text):
    clean = '\n'.join(line.split('//', 1)[0] for line in text.splitlines())
    return [' '.join(s.split()) for s in clean.split(';') if s.strip()]


def validate_delta(base, candidate):
    """Check all CST statements, including existing placement and hidden IOs."""
    old, new = statements(base), statements(candidate)
    expected = [f'INS_LOC "{n}" {REGION}' for n in sorted(NAMES)]
    assert len(NAMES) == len(set(NAMES)) == 8
    assert new == old + expected, 'Only the eight explicit additions are allowed'
    anchors = []
    for s in new:
        if s.startswith('INS_LOC '):
            match = re.fullmatch(r'INS_LOC "([^"*?]+)" (.+)', s)
            assert match, 'No wildcard or malformed placement'
            anchors.append(match[1])
    assert len(anchors) == len(set(anchors)), 'Duplicate/overridden placement'
    assert r.fixed_constraints(base) == r.fixed_constraints(candidate)
    for channel, row, slot in ((0, 102, 1), (1, 102, 2), (2, 57, 1)):
        line = f'INS_LOC "u_hdmi/g_reset[{channel}].reset_sync_fall_s1" R{row}C150[{slot}][A]'
        assert old.count(line) == new.count(line) == 1
    assert not any('u_scan_observe' in s for s in expected)
    return {'passed': True, 'added_cells': 8, 'existing_statements_unchanged': len(old),
            'hdmi_c150_unchanged': True, 'clock_io_and_nonplacement_unchanged': True}


def inputs():
    for base, identities in ((BASE, HASHES), (MEASURED, MEASURED_HASHES)):
        for name, digest in identities.items():
            assert r.sha(base / name) == digest, str(base / name)
    original = json.loads((BASE / 'sources.json').read_text())
    assert original == {str(p.relative_to(BASE / 'source')): r.sha(p)
                        for p in (BASE / 'source').rglob('*') if p.is_file()}
    old = (BASE / 'source/tang/boards/neo/neo.cst').read_text()
    candidate = old + ADDITION
    semantic = validate_delta(old, candidate)
    metadata = json.loads((BASE / 'source/tang/boards/neo/timing_closure.json').read_text())
    assert metadata['hdmi_reset_column'] == 150 and metadata['hdmi_dce_site'] == 'SG[4]'
    ddr = r.audit(BASE / 'source', variant='neo-fifo-registers')
    assert ddr['passed']
    measured = review.read(MEASURED)
    assert measured['timing_checks_ns'] == dict(setup=-3.447, hold=.124, recovery=-.759, removal=.277)
    timing = (MEASURED / 'impl/pnr/console_neo.tr').read_text()
    paths = review.paths(review.section(timing, '1'))
    selected = [min((p for p in paths if p['destination'] == 'u_accel/u_dma/' + leaf),
                    key=lambda p: p['slack_ns'])
                for leaf in ('c_ack_s0', 'f_done_s0', 'w_done_s0', 'write_accepted_s0')]
    assert [p['slack_ns'] for p in selected] == [-3.447, -3.334, -2.695, 1.298]
    assert all(p['source'] == 'u_accel/engine_resetn_3_s0' and
               p['launch_clock'] == p['latch_clock'] == 'ddr3_sys_clk:[R]' for p in selected)
    cc, params, drivers, loads = r.indexed_netlist(MEASURED / 'impl/pnr/console_neo.vo')
    bodies = r.modules(BASE / 'console_neo.vg')
    mapped = {name: r.cells(body) for name, body in bodies.items()}
    targets, boundary = [], {}
    for name in sorted(NAMES):
        module = 'console_neo'
        parts = name.split('/')
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        synth = mapped[module][parts[-1]]
        assert synth['kind'] == cc[name]['kind'] and synth['kind'].startswith(('LUT', 'DFFRE'))
        init = parameter(bodies[module], parts[-1])
        assert (init or "1'b0") == params[name]['INIT'].lower()
        locations = sorted({row['location'] for p in paths for row in p['data_rows']
                            if row['node'].rsplit('/', 1)[0] == name})
        targets.append(dict(instance=name, synthesis=synth, explicit_init=init,
                            routed=cc[name], parameters=params[name], measured_locations=locations,
                            region=REGION))
        for pin, net in cc[name]['pins'].items():
            if net in ('VCC', 'GND') or pin == 'CLK':
                continue
            boundary[net] = dict(drivers=drivers[net], loads=loads[net],
                load_count=len(loads[net]), outside_loads=[x for x in loads[net] if x[0] not in NAMES],
                outside_drivers=[x for x in drivers[net] if x[0] not in NAMES])
    # Small internal LUT fanouts; moving the four FFs also moves their output routes.
    expected_counts = {'n66_10': 2, 'c_ack_4': 3, 'n84_5': 1, 'n76_6': 1, 'write_accepted': 21}
    for net, count in expected_counts.items():
        assert boundary['u_accel/u_dma/' + net]['load_count'] == count
    for net, count in [('u_accel/c_ack_Z', 16), ('u_accel/f_done_Z', 15), ('u_accel/w_done_Z', 16)]:
        assert boundary[net]['load_count'] == count
    code = [Path(__file__), r.HERE / 'test_route9_dma_cone.py', Path(review.__file__),
            r.ROOT / 'optimizer/reports.py', r.ROOT / 'tools/check_neo_timing.py']
    # Record every local imported helper, not only the top-level constructor.
    code += [Path(m.__file__).resolve() for m in list(sys.modules.values())
             if getattr(m, '__file__', None) and str(Path(m.__file__).resolve()).startswith(str(r.ROOT) + '/')
             and Path(m.__file__).suffix == '.py']
    used = code + [BASE / n for n in set(HASHES) | set(COPIED)]
    used += [MEASURED / n for n in set(MEASURED_HASHES) | {'qualification.json', 'automatic_checks.json', 'build.log'}]
    used += [r.PARENT / 'impl/pnr/console_neo.rpt.txt']
    record = dict(parent_inputs=str(BASE), measured_motivation=str(MEASURED), output=str(OUT),
        netlist_sha256=r.NETSHA, sdc_sha256=r.SDC, semantic_test=semantic,
        source_changes=['tang/boards/neo/neo.cst'], hdmi_reset_column=150,
        grouped_cells=8, region=REGION, constrained_cells=targets, boundary_nets=boundary,
        measured_paths=selected, ddr_profile=ddr, hardware_access=False, synthesis=False,
        r8_result_required_for_preparation=False, predicted_timing=None,
        region_reason='Between R7 reset R60C90, DMA LUTs R62..65 C38..40 and completion FFs R16..35 C75..88; no source reset/state FF or observer anchor is moved.',
        limits=['R8 is an independent baseline, possibly still routing. Its inputs are immutable; its future timing is not predicted.',
                'Full placement/routing is recomputed. A small constraint delta can worsen unrelated paths and HDMI recovery/removal.',
                'State[0..2] remains at R7 C38..39 and may acquire longer routes. External completion loads and synchronous reset inputs must be reviewed.',
                'STA reports reset-source fanout663; the indexed postroute net alias gpu_debug_state[47] has20 direct pins. These are distinct report views, not interchangeable counts.',
                'Existing R3/R8 global geometry CE is preserved as a baseline limitation, not newly qualified.'],
        inputs_sha256={str(p): r.sha(p) for p in sorted(set(used))},
        candidate_cst_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True),
                                                    fromfile='R8_C150', tofile='R9_DMA8_C150')))
    # Pin tuples become JSON arrays: compare the same representation at review
    # and launch, rather than rejecting an unchanged preparation on reload.
    return original, candidate, json.loads(json.dumps(record))


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
        print(json.dumps(dict(passed=True, grouped_cells=8, region=REGION,
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
    # Exact parent TCL; only absolute paths change to the isolated output.
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
    old_routes, new_routes = r.global_nets(r.PARENT), r.global_nets(OUT)
    changes = [dict(net=n, before=old_routes.get(n, 'local'), after=new_routes.get(n, 'local'))
               for n in sorted(set(old_routes) | set(new_routes)) if old_routes.get(n) != new_routes.get(n)]
    unexpected = {n: new_routes[n] for n in r.LOCAL + [r.RESET_NET] if n in new_routes}
    cc, params, _, _ = r.indexed_netlist(OUT / 'impl/pnr/console_neo.vo')
    changed_targets = [t['instance'] for t in record['constrained_cells']
                       if cc.get(t['instance']) != t['routed'] or params.get(t['instance']) != t['parameters']]
    result = dict(qualification_returncode=checked.returncode, strict_observer_audit_passed=observed['passed'],
        global_reference=str(r.PARENT), global_changes=changes, unexpected_global_controls=unexpected,
        changed_constrained_primitives=changed_targets, hardware_access=False,
        r8_comparison_pending=True, passed=checked.returncode == 0 and observed['passed']
        and not changes and not unexpected and not changed_targets)
    (OUT / 'automatic_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    if not result['passed']:
        raise SystemExit('Candidate requires independent review; no hardware loading')


if __name__ == '__main__':
    main()
