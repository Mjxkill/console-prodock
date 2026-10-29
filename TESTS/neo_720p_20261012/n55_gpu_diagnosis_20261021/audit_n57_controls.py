#!/usr/bin/env python3
"""Audit N57 routed control/reset topology and global resources; no hardware.

R5 is an unchanged-logic reference, not a timing-qualified reference. The
N57 synthesis proofs establish the module identity used by this comparison.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, pin_base, CLOCK
from build_timing_placement import ROOT, HERE, sha

SYNTH = ROOT / 'tang/impl/console_neo_n57_usb35_syn'
REFERENCE = ROOT / 'tang/impl/console_neo_n56r5'
NET_SHA = '51ed167a714c8c3a3ef5f7a918a850ff4c4163b46c3d9f88b43a96db3b6cd190'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    if build.parent != ROOT / 'tang/impl':
        raise ValueError('Expected an isolated build under tang/impl')
    result_path = build / 'gpu_local_controls_audit.json'
    if result_path.exists():
        raise ValueError('Existing evidence must not be overwritten')
    proof_path = HERE / 'n57_controls/resolution.json'
    proof = json.loads(proof_path.read_text())
    alias_path = HERE / 'n57_reset_aliases/result.json'
    aliases = json.loads(alias_path.read_text())
    rename_path = HERE / 'n57_controls/geometry_rename_proof.json'
    renamed = json.loads(rename_path.read_text())
    for record in (proof, aliases, renamed):
        if not record['passed']:
            raise ValueError('Required synthesis proof failed')
        for name, checksum in record['sha256'].items():
            if sha(Path(name)) != checksum:
                raise ValueError('Changed evidence dependency: ' + name)
    errors = []
    if sha(build / 'console_neo.vg') != NET_SHA:
        errors.append('Different synthesized N57 netlist')
    source = json.loads((build / 'sources.json').read_text())
    original = json.loads((SYNTH / 'sources.json').read_text())
    actual = {str(p.relative_to(build / 'source')): sha(p)
              for p in (build / 'source').rglob('*') if p.is_file()}
    if actual != source or set(source) != set(original) or sorted(
            name for name in source if source[name] != original[name]) != ['tang/boards/neo/neo.cst']:
        errors.append('Source snapshot differs beyond the CST')
    reviewed = json.loads((build / 'controls_manifest.json').read_text())
    if (build / 'source/tang/boards/neo/neo.cst').read_text() != reviewed['candidate_cst']:
        errors.append('CST differs from the reviewed manifest')
    for name, checksum in reviewed['initializations_sha256'].items():
        if sha(build / name) != checksum:
            errors.append('Changed initialization image: ' + name)
    old_cells, old_params, old_drivers, old_loads = indexed_netlist(REFERENCE / 'impl/pnr/console_neo.vo')
    new_cells, new_params, new_drivers, new_loads = indexed_netlist(build / 'impl/pnr/console_neo.vo')
    old_global, new_global = global_nets(REFERENCE), global_nets(build)
    targets = [(entry['label'], entry['stages']['candidate']['proposed_routed_name'])
               for entry in proof['controls']]
    targets += [(f'reset{entry["index"]}', entry['exported_alias']) for entry in aliases['aliases']]
    entries = []
    for label, net in targets:
        issues = []
        if old_drivers[net] != new_drivers[net] or len(new_drivers[net]) != 1:
            issues.append('Driver topology differs')
        if sorted(old_loads[net]) != sorted(new_loads[net]):
            issues.append('Scalar/vector load topology differs')
        if any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in new_loads[net]):
            issues.append('Target control drives a clock pin')
        affected = {name for name, _, _ in old_drivers[net] + old_loads[net]}
        changes = [name for name in sorted(affected)
                   if old_cells[name] != new_cells.get(name) or old_params.get(name) != new_params.get(name)]
        if changes:
            issues.append('Driver/load primitive, pins or parameters changed')
        if net in new_global:
            issues.append('Target control uses global routing: ' + new_global[net])
        entries.append(dict(label=label, net=net, drivers=new_drivers[net],
            load_count=len(new_loads[net]), load_pin_counts=dict(Counter(p for _, _, p in new_loads[net])),
            errors=issues, changed_cells=changes,
            primitive_pins_and_parameters_unchanged=not changes))
    new_routes = []
    unreviewed_ce = []
    for net, resource in sorted(new_global.items()):
        if old_global.get(net) == resource:
            continue
        entry = dict(net=net, resource=resource, drivers=new_drivers[net],
                     load_pin_counts=dict(Counter(p for _, _, p in new_loads[net])))
        new_routes.append(entry)
        if net.startswith(('u_accel/', 'u_gpu/', 'u_gpu_debug/', 'gpu_debug_state[')):
            clock_loads = [p for _, _, p in new_loads[net] if CLOCK.fullmatch(pin_base(p))]
            enable_loads = [p for _, _, p in new_loads[net] if pin_base(p) in ('CE', 'CEA', 'CEB', 'OCE', 'OCEA', 'OCEB')]
            if enable_loads and not clock_loads:
                unreviewed_ce.append(entry)
    if unreviewed_ce:
        errors.append('Additional GPU/observer CE controls moved to global routing; review required')
    paths = [Path(__file__), proof_path, alias_path, rename_path,
             HERE / 'audit_geometry_controls.py', HERE / 'audit_gpu_control_inventory.py',
             build / 'controls_manifest.json', build / 'sources.json', build / 'console_neo.vg',
             build / 'source/tang/boards/neo/neo.cst', build / 'source/tang/boards/neo/neo.sdc',
             build / 'impl/pnr/console_neo.vo', build / 'impl/pnr/console_neo.rpt.txt',
             REFERENCE / 'impl/pnr/console_neo.vo', REFERENCE / 'impl/pnr/console_neo.rpt.txt']
    result = dict(passed=not errors and all(not entry['errors'] for entry in entries),
        errors=errors, controls=entries, new_global_nets=new_routes,
        new_gpu_ce_global_controls=unreviewed_ce,
        removed_global_nets=sorted(set(old_global) - set(new_global)), all_global_nets=new_global,
        sha256={str(p): sha(p) for p in paths}, hardware_access=False,
        limitations=['Structural identity does not replace setup/hold/recovery/removal qualification.',
                    'R5 is used only for mapped topology, not as a qualified timing or hardware reference.',
                    'The official USB IP behavior requires separate simulation and board validation.'])
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], errors=errors,
        control_errors={e['label']: e['errors'] for e in entries if e['errors']},
        new_global_nets=new_routes, result=str(result_path)), indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
