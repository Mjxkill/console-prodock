#!/usr/bin/env python3
"""Retry only the frozen candidate refused by the sandbox host-ID check.

The previous log/result are preserved. No source regeneration, new candidate,
hardware access, or relaxed timing/observer checks. Requires host networking
introspection for Gowin's license, not a change of license.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import route_scan_timing_candidates as r


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--column', type=int, choices=(150, 155), required=True)
    args = p.parse_args()
    name = 'console_neo_n56r9_route4_c150' if args.column == 150 else 'console_neo_n56r9_route5_c155'
    out = r.ROOT / 'tang/impl' / name
    original, cst, metadata, expected = r.inputs(args.column)
    contract = r.before_build('neo', candidate=True)
    expected['local_regressions'] = contract['local_regressions']
    assert json.loads((out / 'route.json').read_text()) == expected
    assert json.loads((r.PREPARED / f'review_c{args.column}.json').read_text()) == expected
    assert r.sha(out / 'console_neo.vg') == r.NETSHA
    manifest = json.loads((out / 'sources.json').read_text())
    assert manifest == {str(f.relative_to(out / 'source')): r.sha(f)
                        for f in (out / 'source').rglob('*') if f.is_file()}
    assert manifest.keys() == original.keys()
    assert sorted(k for k in original if original[k] != manifest[k]) == sorted(expected['source_changes'])
    assert (out / 'source/tang/boards/neo/neo.cst').read_text() == cst
    assert json.loads((out / 'source/tang/boards/neo/timing_closure.json').read_text()) == metadata
    options = [line.replace(str(r.PARENT), str(out)) for line in (r.PARENT / 'build.tcl').read_text().splitlines()
               if line.startswith(('set_device ', 'set_option '))]
    expected_tcl = '\n'.join(options + [f'add_file {{{out / "console_neo.vg"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.sdc"}}}', 'run pnr', ''])
    assert (out / 'build.tcl').read_text() == expected_tcl
    previous = (out / 'build.log').read_text()
    assert previous == ('Could not create AF_NETLINK socket (Operation not permitted)\n'
                        'License verification failed  License hostid not match.\n')
    assert json.loads((out / 'route_result.json').read_text())['status'] == 'ROUTING_FAILED'
    assert not any((out / ('impl/pnr/console_neo.' + suffix)).exists() for suffix in ('fs', 'vo', 'tr'))
    retry = dict(previous_log_sha256=r.sha(out / 'build.log'),
                 previous_result_sha256=r.sha(out / 'route_result.json'),
                 original_builder_sha256=r.sha(Path(r.__file__)),
                 retry_script_sha256=r.sha(Path(__file__)),
                 netlist_sha256=r.NETSHA, sources_sha256=r.sha(out / 'sources.json'),
                 tcl_sha256=r.sha(out / 'build.tcl'), hardware_access=False,
                 reason='Sandbox denied AF_NETLINK used by license host-ID detection')
    with (out / 'license_retry.json').open('x') as f:
        json.dump(retry, f, indent=2)
    (out / 'build.log').rename(out / 'license_sandbox_attempt.log')
    (out / 'route_result.json').rename(out / 'license_sandbox_result.json')
    print('Retrying unchanged frozen candidate ' + str(out), flush=True)
    with (out / 'build.log').open('x') as log:
        result = subprocess.run([str(r.IDE / 'bin/gw_sh'), 'build.tcl'], cwd=out,
                                env=r.environment(), stdout=log, stderr=log)
    log_text = (out / 'build.log').read_text()
    failed = bool(result.returncode or re.search(r'^ERROR', log_text, re.M)
                  or 'Bitstream generation completed' not in log_text)
    (out / 'route_result.json').write_text(json.dumps(dict(status='ROUTING_FAILED' if failed else
        'ROUTED_NOT_QUALIFIED', returncode=result.returncode, hardware_access=False), indent=2) + '\n')
    if failed:
        raise SystemExit('Route failed')
    with (out / 'qualification_automatic.log').open('x') as log:
        checked = subprocess.run([sys.executable, str(r.ROOT / 'tools/check_neo_timing.py'), str(out)],
                                 cwd=r.ROOT, stdout=log, stderr=log, timeout=600)
    r.observer.OUT = out
    observed = r.observer.audit()
    (out / 'scan_observer_audit.json').write_text(json.dumps(observed, indent=2) + '\n')
    routes = r.global_nets(out)
    unexpected = {n: routes[n] for n in expected['local_controls'] if n in routes}
    _, _, cd, cl = r.indexed_netlist(out / 'impl/pnr/console_neo.vo')
    old_routes = r.global_nets(r.PARENT)
    new_ce = []
    for net, resource in routes.items():
        if old_routes.get(net) == resource:
            continue
        affected = [x for x in cl[net] if x[0].startswith(('u_accel/', 'u_gpu/', 'u_scan_'))
                    and r.CE.fullmatch(r.pin_base(x[2]))]
        if affected:
            new_ce.append(dict(net=net, resource=resource, drivers=cd[net], loads=affected))
    report = dict(qualification_returncode=checked.returncode, unexpected_global_controls=unexpected,
                  new_global_gpu_ce=new_ce, strict_observer_audit_passed=observed['passed'],
                  hardware_access=False, passed=checked.returncode == 0 and not unexpected
                  and not new_ce and observed['passed'])
    (out / 'automatic_checks.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Candidate requires further review')


if __name__ == '__main__':
    main()
