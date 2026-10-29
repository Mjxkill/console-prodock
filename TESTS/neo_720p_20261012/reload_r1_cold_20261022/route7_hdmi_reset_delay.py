#!/usr/bin/env python3
"""R7: increase HDMI reset path delay after the measured R6 removal failure.

R4/R5 regrouped many cells and regressed setup; R5 also failed initial DMI.
Return to route3 constraints and move only HDMI falling reset FFs C160->C140.
R6 C155 measured removal -0.153 ns, recovery +1.045 ns on channel 1;
this is a placement hypothesis, with both bounds still mandatory after route.
Same netlist, DDR5.9/300, clock resources requested, SDC, pins and options.
No hardware access or automatic loading. Original failed builds stay intact.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import route_scan_timing_candidates as r

OUT = r.ROOT / 'tang/impl/console_neo_n56r9_route7_hdmi_c140'
REVIEW = r.HERE / 'route7_prepared.json'


def inputs():
    previous = r.ROOT / 'tang/impl/console_neo_n56r9_route6_hdmi_c155'
    q = json.loads((previous / 'qualification.json').read_text())
    assert q['bitstream_sha256'] == '56f1e975be7ddfe7880130898b0fb248caec7114aec5d1b540e496fd8ae7391e'
    assert r.sha(previous / 'impl/pnr/console_neo.fs') == q['bitstream_sha256']
    assert q['timing_checks_ns'] == dict(setup=-2.599, hold=.124, recovery=.337, removal=-.153)
    assert r.sha(previous / 'impl/pnr/console_neo.tr') == q['timing_sha256']
    for name, wanted in r.HASHES.items():
        assert r.sha(r.PARENT / name) == wanted, name
    old_manifest = json.loads((r.PARENT / 'sources.json').read_text())
    assert old_manifest == {str(p.relative_to(r.PARENT / 'source')): r.sha(p)
                            for p in (r.PARENT / 'source').rglob('*') if p.is_file()}
    old = (r.PARENT / 'source/tang/boards/neo/neo.cst').read_text()
    cst = old
    for channel, row, slot in ((0, 102, 1), (1, 102, 2), (2, 57, 1)):
        name = f'u_hdmi/g_reset[{channel}].reset_sync_fall_s1'
        line = f'INS_LOC "{name}" R{row}C160[{slot}][A];'
        assert cst.count(line) == 1
        cst = cst.replace(line, line.replace('C160[', 'C140['))
    assert r.fixed_constraints(cst) == r.fixed_constraints(old)
    metadata = json.loads((r.PARENT / 'source/tang/boards/neo/timing_closure.json').read_text())
    assert metadata['hdmi_reset_column'] == 160 and metadata['hdmi_dce_site'] == 'SG[4]'
    metadata['hdmi_reset_column'] = 140
    assert r.audit(r.PARENT / 'source', variant='neo-fifo-registers')['passed']
    record = dict(parent=str(r.PARENT), name=OUT.name, netlist_sha256=r.NETSHA,
        source_changes=['tang/boards/neo/neo.cst', 'tang/boards/neo/timing_closure.json'],
        changed_locations=3, old_column=160, new_column=140,
        additional_grouping=False, additional_ce_constraints=False,
        measured_reference=str(previous), measured_checks_ns=q['timing_checks_ns'],
        measured_timing_sha256=q['timing_sha256'],
        measured_channel1=dict(removal_ns=-.153, recovery_ns=1.045,
                               min_route_ns=.596, max_route_ns=1.358),
        hardware_access=False, synthesis=False,
        inputs_sha256={str(p): r.sha(p) for p in [Path(__file__), Path(r.__file__)] +
                        [r.PARENT / n for n in r.HASHES]},
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True), cst.splitlines(True),
                                                    fromfile='route3', tofile='route7')),
        limits='Whole placement/routing changes despite three constraints; no timing or hardware guarantee.')
    return old_manifest, cst, metadata, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    assert not OUT.exists(), 'Do not overwrite builds'
    original, cst, metadata, record = inputs()
    contract = r.before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.check_only:
        with REVIEW.open('x') as f:
            json.dump(record, f, indent=2)
        print(json.dumps(dict(passed=True, changed_locations=3, hardware_access=False)))
        return
    assert record == json.loads(REVIEW.read_text()), 'Prepared inputs changed'
    OUT.mkdir()
    r.record_build(OUT, contract)
    shutil.copytree(r.PARENT / 'source', OUT / 'source')
    (OUT / 'source/tang/boards/neo/neo.cst').write_text(cst)
    (OUT / 'source/tang/boards/neo/timing_closure.json').write_text(json.dumps(metadata, indent=2) + '\n')
    for relative in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
                     'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
        dest = OUT / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r.PARENT / relative, dest)
    actual = {str(f.relative_to(OUT / 'source')): r.sha(f)
              for f in (OUT / 'source').rglob('*') if f.is_file()}
    assert actual.keys() == original.keys()
    assert sorted(k for k in original if original[k] != actual[k]) == record['source_changes']
    (OUT / 'sources.json').write_text(json.dumps(actual, indent=2) + '\n')
    options = [line.replace(str(r.PARENT), str(OUT)) for line in (r.PARENT / 'build.tcl').read_text().splitlines()
               if line.startswith(('set_device ', 'set_option '))]
    (OUT / 'build.tcl').write_text('\n'.join(options + [f'add_file {{{OUT / "console_neo.vg"}}}',
        f'add_file {{{OUT / "source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{OUT / "source/tang/boards/neo/neo.sdc"}}}', 'run pnr', '']))
    (OUT / 'route.json').write_text(json.dumps(record, indent=2) + '\n')
    (OUT / 'constraints.diff').write_text(record['constraints_diff'])
    print('Routing ' + str(OUT), flush=True)
    with (OUT / 'build.log').open('x') as log:
        proc = subprocess.run([str(r.IDE / 'bin/gw_sh'), 'build.tcl'], cwd=OUT,
                              env=r.environment(), stdout=log, stderr=log)
    log_text = (OUT / 'build.log').read_text()
    failed = bool(proc.returncode or re.search(r'^ERROR', log_text, re.M)
                  or 'Bitstream generation completed' not in log_text)
    (OUT / 'route_result.json').write_text(json.dumps(dict(status='ROUTING_FAILED' if failed else
        'ROUTED_NOT_QUALIFIED', returncode=proc.returncode, hardware_access=False), indent=2) + '\n')
    if failed:
        raise SystemExit('Route failed')
    with (OUT / 'qualification_automatic.log').open('x') as log:
        checked = subprocess.run([sys.executable, str(r.ROOT / 'tools/check_neo_timing.py'), str(OUT)],
                                 cwd=r.ROOT, stdout=log, stderr=log, timeout=600)
    r.observer.OUT = OUT
    observed = r.observer.audit()
    (OUT / 'scan_observer_audit.json').write_text(json.dumps(observed, indent=2) + '\n')
    old_routes, routes = r.global_nets(r.PARENT), r.global_nets(OUT)
    _, _, drivers, loads = r.indexed_netlist(OUT / 'impl/pnr/console_neo.vo')
    changes = [dict(net=n, before=old_routes.get(n, 'local'), after=routes.get(n, 'local'),
                    drivers=drivers.get(n), loads=loads.get(n)) for n in sorted(set(old_routes) | set(routes))
               if old_routes.get(n) != routes.get(n)]
    unexpected = {n: routes[n] for n in r.LOCAL + [r.RESET_NET] if n in routes}
    result = dict(qualification_returncode=checked.returncode,
                  strict_observer_audit_passed=observed['passed'],
                  unexpected_global_controls=unexpected, global_changes=changes,
                  hardware_access=False, passed=checked.returncode == 0 and observed['passed']
                  and not unexpected and not changes)
    (OUT / 'automatic_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'global_changes'}), flush=True)


if __name__ == '__main__':
    main()
