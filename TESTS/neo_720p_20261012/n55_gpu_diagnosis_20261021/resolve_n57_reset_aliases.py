#!/usr/bin/env python3
"""Prove internal/exported reset aliases; do not apply any CST or invoke Gowin."""
import json
from pathlib import Path
import re

from resolve_n57_controls import (modules_for, cells, global_connections,
                                 IndexedModule, CANDIDATE, HERE, ROOT, sha)
from audit_gpu_control_inventory import CLOCK, pin_base, global_nets


def main():
    out = HERE / 'n57_reset_aliases'
    if out.exists():
        raise ValueError('Existing evidence must not be overwritten')
    path = CANDIDATE / 'impl/gwsynthesis/console_neo.vg'
    names, bodies, top, _ = modules_for(path)
    indexed = IndexedModule(bodies['accel'])
    cst_path = CANDIDATE / 'source/tang/boards/neo/neo.cst'
    cst = cst_path.read_text()
    aliases = []
    for index in range(12):
        name = f'engine_resetn_{index}_s0'
        cell = indexed.cells[name]
        local = cell['pins']['Q']
        exported = top['u_accel']['pins'].get(local)
        expected_local, expected_exported = f'gpu_debug_state_{44 + index}', f'gpu_debug_state[{44 + index}]'
        if (local != expected_local or exported != expected_exported or
                cell['kind'] != 'DFFCE' or indexed.params[name] != {'INIT': "1'b0"} or
                cell['pins'] != dict(Q=local, D='gpu_debug_state_42', CLK='gpu_clk',
                                    CLEAR='n3932_6', CE='VCC')):
            raise ValueError('Unexpected reset driver/port alias: ' + name)
        declaration = 'output ' + local + ';'
        if bodies['accel'].splitlines().count(declaration) != 1:
            raise ValueError('Reset alias is not the expected scalar output')
        top_constraint = f'CLOCK_LOC "{exported}" LOCAL_CLOCK;'
        internal_constraint = f'CLOCK_LOC "u_accel/{local}" LOCAL_CLOCK;'
        if cst.splitlines().count(top_constraint) != 1 or internal_constraint in cst:
            raise ValueError('Unexpected existing reset constraints')
        aliases.append(dict(index=index, driver='u_accel/' + name,
            internal_alias='u_accel/' + local, exported_alias=exported,
            driver_cell=cell, driver_parameters=indexed.params[name],
            module=names['accel'], module_port_declaration=declaration,
            existing_constraint=top_constraint, proposed_additional_constraint=internal_constraint))
    connections = global_connections(path, {entry['exported_alias'] for entry in aliases})
    r5 = ROOT / 'tang/impl/console_neo_n56r5'
    routed_path = r5 / 'impl/pnr/console_neo.vo'
    routed = cells(routed_path.read_text())
    resource = global_nets(r5)
    for entry in aliases:
        net = entry['exported_alias']
        pins = connections[net]
        if pins['drivers'] != [(entry['driver'], 'DFFCE', 'Q')]:
            raise ValueError('Global alias has an unexpected driver')
        clock_pins = [pin for pin in pins['loads'] if CLOCK.fullmatch(pin_base(pin[2]))]
        if clock_pins:
            raise ValueError('Reset alias feeds a clock')
        if routed[entry['driver']]['pins']['Q'] != net:
            raise ValueError('Reference routed alias differs')
        entry.update(global_connections=pins, global_load_count=len(pins['loads']),
                     clock_pin_count=0, r5_resource=resource.get(net),
                     r5_exported_net_at_same_driver=True)
    result = dict(passed=True, scope=__doc__, aliases=aliases,
        hardware_access=False, compiler_invoked=False, cst_changed=False,
        limitations=[
            'The internal scalar aliases are proven at the synthesized hierarchical boundary; post-route canonical names are the exported bus bits.',
            'The local documentation specifies net names but does not establish which alias CLOCK_LOC matches before flattening.',
            'These additional lines are a proposed experiment, not proof of constraint enforcement; root review is required.',
            'Post-route reset/global-route audits remain mandatory and must not be bypassed by this alias proof.'],
        sha256={str(p): sha(p) for p in [Path(__file__), path, cst_path, routed_path,
                 r5 / 'impl/pnr/console_neo.rpt.txt', HERE / 'resolve_n57_controls.py']})
    out.mkdir()
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'proposed_additions.cst').write_text(''.join(
        entry['proposed_additional_constraint'] + '\n' for entry in aliases))
    print(json.dumps(dict(passed=True, output=str(out),
        aliases=[{key: entry[key] for key in ('index', 'internal_alias', 'exported_alias',
                                            'global_load_count', 'r5_resource')} for entry in aliases]), indent=2))


if __name__ == '__main__':
    main()
