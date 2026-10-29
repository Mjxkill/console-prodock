#!/usr/bin/env python3
"""Compare the completed route3 reset distribution with route2, without hardware.

The logical netlist stays fixed. This audit does not qualify a bitstream or
excuse setup/recovery failures; those remain in qualification.json.
"""
from collections import Counter
import json
from pathlib import Path

from route_observed_scan_reset import PARENT, OUT, NET, NETSHA, ADDITION, sha
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, pin_base


def main():
    assert (OUT / 'automatic_checks.json').is_file(), 'Build checks incomplete'
    errors = []
    old_manifest = json.loads((PARENT / 'sources.json').read_text())
    new_manifest = json.loads((OUT / 'sources.json').read_text())
    actual = {str(p.relative_to(OUT / 'source')): sha(p)
              for p in (OUT / 'source').rglob('*') if p.is_file()}
    if actual != new_manifest or new_manifest.keys() != old_manifest.keys():
        errors.append('Source manifest differs from source tree or parent file set')
    changed = sorted(k for k in old_manifest if old_manifest[k] != new_manifest.get(k))
    if changed != ['tang/boards/neo/neo.cst']:
        errors.append('Unexpected source change')
    cst = 'source/tang/boards/neo/neo.cst'
    if (OUT / cst).read_text() != (PARENT / cst).read_text() + ADDITION:
        errors.append('Unexpected constraint change')
    if sha(OUT / 'console_neo.vg') != NETSHA:
        errors.append('Synthesis netlist changed')

    pc, pp, pd, pl = indexed_netlist(PARENT / 'impl/pnr/console_neo.vo')
    cc, cp, cd, cl = indexed_netlist(OUT / 'impl/pnr/console_neo.vo')
    old_global, new_global = global_nets(PARENT), global_nets(OUT)
    if old_global.get(NET) != 'LW' or NET in new_global:
        errors.append('The selected reset did not change from LW to local routing')
    stages = []
    for i, count in ((0, 2), (1, 21)):
        net = f'scan_debug_live_178[{i}]'
        name = f'u_gpu/mrst_{i}_s0'
        if pd[net] != cd[net] or cd[net] != [(name, 'DFFCE', 'Q')]:
            errors.append('Reset stage driver changed: ' + net)
        if len(cl[net]) != count or sorted(pl[net]) != sorted(cl[net]):
            errors.append('Reset stage load set changed: ' + net)
        if any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in cl[net]):
            errors.append('Reset stage feeds a clock input: ' + net)
        affected = {n for n, _, _ in pd[net] + pl[net]}
        differences = [dict(instance=n, before=pc[n], after=cc.get(n),
                            before_parameters=pp.get(n), after_parameters=cp.get(n))
                       for n in sorted(affected)
                       if pc[n] != cc.get(n) or pp.get(n) != cp.get(n)]
        if differences:
            errors.append('Reset driver or load primitive changed: ' + net)
        stages.append(dict(net=net, driver=cc.get(name), parameters=cp.get(name),
                           before_route=old_global.get(net, 'local'),
                           after_route=new_global.get(net, 'local'),
                           loads=cl[net], load_pins=dict(Counter(pin_base(p) for _, _, p in cl[net])),
                           changed_cells=differences))

    promoted = [dict(net=n, before=old_global.get(n), after=r, drivers=cd[n],
                     load_pins=dict(Counter(pin_base(p) for _, _, p in cl[n])))
                for n, r in sorted(new_global.items()) if old_global.get(n) != r]
    removed = sorted(set(old_global) - set(new_global))
    if promoted or removed != [NET]:
        errors.append('Additional global routing changes need independent review')
    q = json.loads((OUT / 'qualification.json').read_text())
    paths = [Path(__file__), OUT / 'sources.json', OUT / cst,
             OUT / 'console_neo.vg', OUT / 'qualification.json',
             OUT / 'automatic_checks.json',
             OUT / 'impl/pnr/console_neo.vo', OUT / 'impl/pnr/console_neo.rpt.txt',
             PARENT / 'sources.json', PARENT / cst,
             PARENT / 'impl/pnr/console_neo.vo', PARENT / 'impl/pnr/console_neo.rpt.txt']
    result = dict(passed=not errors, errors=errors, changed_sources=changed,
                  reset_stages=stages, new_global_nets=promoted,
                  removed_global_nets=removed, all_global_nets=new_global,
                  qualification_status=q['status'], timing_checks_ns=q['timing_checks_ns'],
                  bitstream_sha256=q['bitstream_sha256'], hardware_access=False,
                  sha256={str(p): sha(p) for p in paths},
                  limits='Targeted structural comparison only; no timing or hardware waiver.')
    with (OUT / 'scan_reset_route_comparison.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('passed', 'errors', 'new_global_nets',
                                            'removed_global_nets', 'qualification_status',
                                            'timing_checks_ns')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
