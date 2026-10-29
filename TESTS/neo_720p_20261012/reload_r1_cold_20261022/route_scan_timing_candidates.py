#!/usr/bin/env python3
"""Two frozen Neo placement candidates following route3, without hardware.

Same HDL, DDR5.9/300, synthesis and SDC. Both keep scanout reset local,
prevent the newly promoted geometry CE from using LW, and regroup measured
setup paths. Only the three HDMI reset FF columns differ between candidates.
"""
import argparse
from collections import Counter
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from route_observed_scan_reset import ROOT, HERE, NETSHA, SDC, sha, modules, cells
from route_scan_observer_placement import before_build, record_build, IDE, environment, audit, LOCAL
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, CE, pin_base
from reports import fixed_constraints
import audit_scan_observer as observer

PARENT = ROOT / 'tang/impl/console_neo_n56r9_route3_scan_reset'
PREPARED = HERE / 'scan_timing_candidates'
CE_NET = 'u_accel/u_v1/n57378_3'
RESET_NET = 'scan_debug_live_178[1]'
ARB = 'u_soc/g_ddr.u_ddr/u_gpu_arb/n50_s2'
ARB_REGION = 'R[55:75]C[100:115]'
HASHES = {
    'sources.json': 'b64ed4906476f6695ae626aba42baf4f14d0945b01c095e8244ea7b6d1da66f6',
    'console_neo.vg': NETSHA,
    'source/tang/boards/neo/neo.cst': '583037fa38352fa5baeabbb6b61380ddfc5b66e056c3e164ad5b96bccd345c62',
    'source/tang/boards/neo/neo.sdc': SDC,
    'source/tang/boards/neo/timing_closure.json': 'cb09d9616a9dc15eb40b876f330fe461554a6c9a29412ebdb1afddfc4d493407',
    'impl/pnr/console_neo.vo': '7cf78fb953d1257f07cc83490a6abca84bd33bb1490bee8301cb3cd1f0335b17',
    'impl/pnr/console_neo.tr': 'e3d73ef7d4573b952d540b42965c081daecc39e0a5d0dc88b23794e6a83e5a36',
    'impl/pnr/console_neo.fs': '42c4edc4a079c1ed3f9759a860ccbf30bb8d4ecfa041e2699870fcc8072e2f4a',
}


def inputs(column):
    for name, wanted in HASHES.items():
        assert sha(PARENT / name) == wanted, name
    original = json.loads((PARENT / 'sources.json').read_text())
    assert original == {str(p.relative_to(PARENT / 'source')): sha(p)
                        for p in (PARENT / 'source').rglob('*') if p.is_file()}
    q = json.loads((PARENT / 'qualification.json').read_text())
    assert q['status'] == 'FAIL'
    assert q['timing_checks_ns'] == dict(setup=-1.656, hold=.124, recovery=.437, removal=-.150)
    comparison = json.loads((PARENT / 'scan_reset_route_comparison.json').read_text())
    assert comparison['errors'] == ['Additional global routing changes need independent review']
    assert all(not s['changed_cells'] for s in comparison['reset_stages'])
    assert comparison['new_global_nets'] == [dict(net=CE_NET, before=None, after='LW',
        drivers=[['u_accel/u_v1/n57378_s0', 'LUT3', 'F']], load_pins=dict(CE=204))]
    for name, wanted in comparison['sha256'].items():
        assert sha(Path(name)) == wanted, name

    cc, params, drivers, loads = indexed_netlist(PARENT / 'impl/pnr/console_neo.vo')
    assert drivers[CE_NET] == [('u_accel/u_v1/n57378_s0', 'LUT3', 'F')]
    assert params['u_accel/u_v1/n57378_s0'] == dict(INIT="8'h80")
    assert len(loads[CE_NET]) == 204
    assert Counter(pin for _, _, pin in loads[CE_NET]) == {'CE': 198, 'CE[1]': 2, 'CE[0]': 4}
    assert not any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in loads[CE_NET])
    assert global_nets(PARENT)[CE_NET] == 'LW' and RESET_NET not in global_nets(PARENT)

    old = (PARENT / 'source/tang/boards/neo/neo.cst').read_text()
    proposal = json.loads((PREPARED / 'groups.json').read_text())
    grouped = (PREPARED / 'groups.cst').read_text()
    assert proposal['build'] == str(PARENT)
    assert proposal['report_sha256'] == HASHES['impl/pnr/console_neo.tr']
    assert proposal['netlist_sha256'] == NETSHA
    assert proposal['base_cst_sha256'] == HASHES['source/tang/boards/neo/neo.cst']
    assert proposal['candidate_cst_sha256'] == sha(PREPARED / 'groups.cst')
    assert len(proposal['cells']) == 61 and not proposal['skipped_route_created_cells']
    assert grouped == old.rstrip() + '\n\n// Independent path groups; full routing and qualification required.\n' + ''.join(
        f'INS_LOC "{name}" {item["region"]};\n' for name, item in sorted(proposal['cells'].items()))
    assert ARB not in proposal['cells'] and f'INS_LOC "{ARB}"' not in old
    candidate = grouped + f'INS_LOC "{ARB}" {ARB_REGION};\n'
    extra = f'CLOCK_LOC "{CE_NET}" LOCAL_CLOCK;\n'
    assert f'CLOCK_LOC "{CE_NET}"' not in old
    candidate += extra
    for channel, row, slot in ((0, 102, 1), (1, 102, 2), (2, 57, 1)):
        name = f'u_hdmi/g_reset[{channel}].reset_sync_fall_s1'
        old_line = f'INS_LOC "{name}" R{row}C160[{slot}][A];'
        new_line = f'INS_LOC "{name}" R{row}C{column}[{slot}][A];'
        assert candidate.count(old_line) == 1
        candidate = candidate.replace(old_line, new_line)
    assert fixed_constraints(candidate.replace(extra, '')) == fixed_constraints(old)
    for net in LOCAL + [RESET_NET]:
        assert candidate.count(f'CLOCK_LOC "{net}" LOCAL_CLOCK;') == 1
    metadata = json.loads((PARENT / 'source/tang/boards/neo/timing_closure.json').read_text())
    assert metadata['hdmi_reset_column'] == 160 and metadata['hdmi_dce_site'] == 'SG[4]'
    metadata['hdmi_reset_column'] = column

    bodies = modules(PARENT / 'console_neo.vg')
    mapped = {name: cells(body) for name, body in bodies.items()}
    targets = []
    for name in sorted(set(proposal['cells']) | {ARB, 'u_accel/u_v1/n57378_s0'}):
        module = 'console_neo'
        parts = name.split('/')
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        cell = mapped[module][parts[-1]]
        assert cell['kind'] == cc[name]['kind'] and cell['kind'].startswith(('DFF', 'LUT', 'ALU')), name
        targets.append(dict(instance=name, source_cell=cell, routed_cell=cc[name], parameters=params.get(name)))
    ddr = audit(PARENT / 'source', variant='neo-fifo-registers')
    assert ddr['passed']
    paths = [Path(__file__), PREPARED / 'groups.cst', PREPARED / 'groups.json',
             PARENT / 'qualification.json', PARENT / 'scan_reset_route_comparison.json',
             ROOT / 'optimizer/placement.py', ROOT / 'optimizer/reports.py',
             Path(observer.__file__), PARENT / 'build.tcl']
    paths += [PARENT / name for name in HASHES]
    record = dict(parent=str(PARENT), hdmi_reset_column=column, netlist_sha256=NETSHA,
        source_changes=['tang/boards/neo/neo.cst', 'tang/boards/neo/timing_closure.json'],
        local_controls=LOCAL + [RESET_NET, CE_NET], grouped_cells=61, arbiter_cell=ARB,
        arbiter_region=ARB_REGION, constrained_cell_proof=targets,
        ce_driver=cc['u_accel/u_v1/n57378_s0'], ce_loads=[list(x) for x in loads[CE_NET]],
        ddr_profile=ddr, hardware_access=False, synthesis=False,
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True),
            fromfile='route3', tofile=f'candidate_c{column}')),
        inputs_sha256={str(p): sha(p) for p in paths},
        limits=['A placement experiment cannot guarantee min/max reset delay or setup timing.',
                'No SDC, HDL, DDR, pin, frequency or HDMI SG4 change. Both candidates require full review.',
                'Grouping is based on measured paths, not a congestion model.'])
    return original, candidate, metadata, record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--column', type=int, choices=(150, 155), required=True)
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    name = 'console_neo_n56r9_route4_c150' if args.column == 150 else 'console_neo_n56r9_route5_c155'
    out = ROOT / 'tang/impl' / name
    assert not out.exists(), 'Never overwrite a candidate'
    original, candidate, metadata, record = inputs(args.column)
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    review = PREPARED / f'review_c{args.column}.json'
    if args.check_only:
        review.write_text(json.dumps(record, indent=2) + '\n')
        (PREPARED / f'candidate_c{args.column}.diff').write_text(record['constraints_diff'])
        print(json.dumps(dict(passed=True, column=args.column, regional_cells=62, hardware_access=False)))
        return
    assert record == json.loads(review.read_text()), 'Review/input drift'
    out.mkdir()
    record_build(out, contract)
    shutil.copytree(PARENT / 'source', out / 'source')
    (out / 'source/tang/boards/neo/neo.cst').write_text(candidate)
    (out / 'source/tang/boards/neo/timing_closure.json').write_text(json.dumps(metadata, indent=2) + '\n')
    for relative in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
                     'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
        dest = out / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT / relative, dest)
    actual = {str(f.relative_to(out / 'source')): sha(f)
              for f in (out / 'source').rglob('*') if f.is_file()}
    assert actual.keys() == original.keys()
    assert sorted(k for k in original if original[k] != actual[k]) == sorted(record['source_changes'])
    (out / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
    options = [line.replace(str(PARENT), str(out)) for line in (PARENT / 'build.tcl').read_text().splitlines()
               if line.startswith(('set_device ', 'set_option '))]
    (out / 'build.tcl').write_text('\n'.join(options + [f'add_file {{{out / "console_neo.vg"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.sdc"}}}', 'run pnr', '']))
    (out / 'route.json').write_text(json.dumps(record, indent=2) + '\n')
    (out / 'constraints.diff').write_text(record['constraints_diff'])
    print('Routing ' + str(out), flush=True)
    with (out / 'build.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=out,
                                env=environment(), stdout=log, stderr=log)
    log_text = (out / 'build.log').read_text()
    failed = bool(result.returncode or re.search(r'^ERROR', log_text, re.M)
                  or 'Bitstream generation completed' not in log_text)
    (out / 'route_result.json').write_text(json.dumps(dict(status='ROUTING_FAILED' if failed else
        'ROUTED_NOT_QUALIFIED', returncode=result.returncode, hardware_access=False), indent=2) + '\n')
    if failed:
        raise SystemExit('Route failed')
    with (out / 'qualification_automatic.log').open('x') as log:
        checked = subprocess.run([sys.executable, str(ROOT / 'tools/check_neo_timing.py'), str(out)],
                                 cwd=ROOT, stdout=log, stderr=log, timeout=600)
    observer.OUT = out
    observed = observer.audit()
    (out / 'scan_observer_audit.json').write_text(json.dumps(observed, indent=2) + '\n')
    routes = global_nets(out)
    unexpected = {n: routes[n] for n in record['local_controls'] if n in routes}
    _, _, cd, cl = indexed_netlist(out / 'impl/pnr/console_neo.vo')
    old_routes = global_nets(PARENT)
    new_ce = []
    for net, resource in routes.items():
        if old_routes.get(net) == resource:
            continue
        affected = [x for x in cl[net] if x[0].startswith(('u_accel/', 'u_gpu/', 'u_scan_'))
                    and CE.fullmatch(pin_base(x[2]))]
        if affected:
            new_ce.append(dict(net=net, resource=resource, drivers=cd[net], loads=affected))
    record = dict(qualification_returncode=checked.returncode, unexpected_global_controls=unexpected,
                  new_global_gpu_ce=new_ce, strict_observer_audit_passed=observed['passed'],
                  hardware_access=False, passed=checked.returncode == 0 and not unexpected
                  and not new_ce and observed['passed'])
    (out / 'automatic_checks.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2), flush=True)
    if not record['passed']:
        raise SystemExit('Candidate requires further review')


if __name__ == '__main__':
    main()
