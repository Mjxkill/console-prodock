#!/usr/bin/env python3
"""Audit the four N56r3 LOCAL_CLOCK controls after PnR, with no hardware access."""
import json
from pathlib import Path
import re

from build_material_control import PARENT, ROOT, HERE, NET, ADDITION, NAME, sha, dump
from build_timing_placement import CONTROLS, SHA_NET, SHA_SDC, initial_values
from build_local_controls import cells


def audit():
    build = ROOT/'tang/impl'/NAME
    parent_manifest = json.loads((PARENT/'sources.json').read_text())
    manifest = json.loads((build/'sources.json').read_text())
    actual = {str(p.relative_to(build/'source')): sha(p)
              for p in (build/'source').rglob('*') if p.is_file()}
    errors = []
    if actual != manifest:
        errors.append('Frozen candidate sources changed')
    changed = sorted(k for k in manifest if manifest.get(k) != parent_manifest.get(k))
    if set(manifest) != set(parent_manifest) or changed != ['tang/boards/neo/neo.cst']:
        errors.append('Unexpected source changes')
    if sha(build/'console_neo.vg') != SHA_NET or sha(PARENT/'console_neo.vg') != SHA_NET:
        errors.append('Synthesis netlist changed')
    if sha(build/'source/tang/boards/neo/neo.sdc') != SHA_SDC:
        errors.append('SDC changed')
    cst = (build/'source/tang/boards/neo/neo.cst').read_text()
    if cst != (PARENT/'source/tang/boards/neo/neo.cst').read_text()+ADDITION:
        errors.append('CST differs from the single reviewed addition')
    parent_text = (PARENT/'impl/pnr/console_neo.vo').read_text()
    routed_text = (build/'impl/pnr/console_neo.vo').read_text()
    parent_cells, routed_cells = cells(parent_text), cells(routed_text)
    parent_init, routed_init = initial_values(parent_text), initial_values(routed_text)
    physical = (build/'impl/pnr/console_neo.rpt.txt').read_text()
    table = re.search(r'\n6\. Global Clock Signals\n(.*?)\n7\. Pinout by Port Name\n', physical, re.S)
    if not table:
        raise ValueError('Complete global resource table absent')
    def resources(body):
        return [{'net': m[0].strip(), 'resource': m[1], 'location': m[2].strip()}
                for m in re.findall(r'^\s*(\S+)\s*\|\s*(PRIMARY|LW|HCLK)\s*\|\s*(.*?)\s*$', body, re.M)]

    globals_ = resources(table[1])
    parent_table = re.search(r'\n6\. Global Clock Signals\n(.*?)\n7\. Pinout by Port Name\n',
                            (PARENT/'impl/pnr/console_neo.rpt.txt').read_text(), re.S)
    if not parent_table:
        raise ValueError('Complete parent global resource table absent')
    parent_globals = resources(parent_table[1])
    parent_routes = {(r['net'], r['resource']) for r in parent_globals}
    current_routes = {(r['net'], r['resource']) for r in globals_}
    newly_global = []
    for net, resource in sorted(current_routes-parent_routes):
        drivers = [dict(instance=n, **c) for n, c in routed_cells.items()
                   if any(c['pins'].get(p) == net for p in ('F', 'Q', 'O'))]
        load_pins = {}
        for cell in routed_cells.values():
            for pin, value in cell['pins'].items():
                if value == net and pin not in ('F', 'Q', 'O'):
                    load_pins[pin] = load_pins.get(pin, 0)+1
        newly_global.append(dict(net=net, resource=resource, drivers=drivers, load_pin_counts=load_pins))
    results = []
    expected_counts = [312, 283, 2, 253]
    for net, expected_count in zip((*CONTROLS, NET), expected_counts):
        issues = []
        parent_driver = [n for n, c in parent_cells.items()
                         if any(c['pins'].get(p) == net for p in ('F', 'Q', 'O'))]
        candidate_driver = [n for n, c in routed_cells.items()
                            if any(c['pins'].get(p) == net for p in ('F', 'Q', 'O'))]
        if len(parent_driver) != 1 or parent_driver != candidate_driver:
            issues.append('Driver changed')
        name = parent_driver[0]
        if routed_cells.get(name) != parent_cells[name]:
            issues.append('Driver type or pins changed')
        if parent_init.get(name) != routed_init.get(name):
            issues.append('Driver INIT changed')

        def loads(cc):
            return sorted((n, c['kind'], pin) for n, c in cc.items()
                          for pin, value in c['pins'].items()
                          if value == net and pin not in ('F', 'Q', 'O'))

        before, after = loads(parent_cells), loads(routed_cells)
        if before != after or len(after) != expected_count:
            issues.append('Load set changed')
        if any(pin in ('CLK', 'CLKA', 'CLKB', 'CLKIN') for _, _, pin in after):
            issues.append('Control unexpectedly drives a clock input')
        if any(item['net'] == net for item in globals_):
            issues.append('Control still present in global resource table')
        if cst.count(f'CLOCK_LOC "{net}" LOCAL_CLOCK;') != 1:
            issues.append('LOCAL_CLOCK constraint absent or duplicated')
        results.append(dict(net=net, driver=name, primitive=parent_cells[name]['kind'],
            pins=routed_cells.get(name, {}).get('pins'), init=routed_init.get(name),
            loads=len(after), same_complete_load_set=before == after,
            not_in_global_table=not any(item['net'] == net for item in globals_),
            errors=issues))
    paths = [build/'console_neo.vg', build/'impl/pnr/console_neo.vo',
             build/'impl/pnr/console_neo.rpt.txt', build/'sources.json',
             build/'source/tang/boards/neo/neo.cst', build/'source/tang/boards/neo/neo.sdc',
             PARENT/'impl/pnr/console_neo.vo', PARENT/'impl/pnr/console_neo.rpt.txt',
             PARENT/'sources.json', Path(__file__)]
    return dict(passed=not errors and all(not r['errors'] for r in results), errors=errors,
        controls=results, changed_sources=changed, same_synthesis_netlist=sha(build/'console_neo.vg') == SHA_NET,
        global_resources=globals_, newly_global_nets=newly_global,
        removed_global_nets=[dict(net=n, resource=r) for n, r in sorted(parent_routes-current_routes)],
        checks_sha256={str(p.relative_to(ROOT)): sha(p) for p in paths},
        parent=str(PARENT), hardware_access=False,
        limitation='No independent bitstream route decoder; compares PnR primitives and the complete global resource table.')


if __name__ == '__main__':
    result = audit()
    dump(ROOT/'tang/impl'/NAME/'local_controls_audit.json', result)
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit('Material control routing audit failed')
