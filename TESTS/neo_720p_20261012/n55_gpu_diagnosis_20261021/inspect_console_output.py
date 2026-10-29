#!/usr/bin/env python3
"""Read-only comparison of the routed BL616 output relay, N56 versus N56r1."""
from collections import Counter
import json
from pathlib import Path

from resolve_n57_controls import cells
from prove_geometry_controls import parameters
from audit_gpu_control_inventory import global_nets, primitive_directions
from build_timing_placement import ROOT, HERE, sha


def inspect(build):
    path = build / 'impl/pnr/console_neo.vo'
    raw = path.read_text()
    cc, pp = cells(raw), parameters(raw)
    model = primitive_directions()
    selected = {n: dict(c, parameters=pp.get(n, {})) for n, c in cc.items()
                if n.startswith('u_console_output/')}
    pins = ('CLK', 'CE', 'RESET', 'SET', 'CLEAR', 'PRESET')
    counts = {pin: dict(Counter(c['pins'][pin] for c in selected.values()
                               if pin in c['pins'])) for pin in pins}
    dependencies = {'vid_hclk', 'ae350_rst_sync[1]', 'ae350_rst_sync[0]',
                    'n3587_7', 'pll_ae350_lock', 'ae350_tx_d', 'uart_tx_d'}
    drivers = {}
    for net in sorted(dependencies):
        found = {name: dict(cell, parameters=pp.get(name, {}))
                 for name, cell in cc.items()
                 if any(value == net and model.get(cell['kind'], {}).get(pin) == 'output'
                        for pin, value in cell['pins'].items())}
        drivers[net] = found
    global_routes = global_nets(build)
    used_controls = set().union(*(set(counts[p]) for p in pins if p != 'CLK'))
    io = {name: cell for name, cell in cc.items()
          if cell['kind'] in ('IBUF', 'OBUF') and
          set(cell['pins'].values()) & {'uart_tx', 'uart_rx', 'ae350_tx'}}
    paths = [path, build / 'impl/pnr/console_neo.rpt.txt',
             build / 'source/tang/boards/neo/console_neo.v',
             build / 'source/tang/boards/neo/neo.cst',
             build / 'source/tang/boards/neo/neo.sdc',
             build / 'source/tang/boards/neo/vendor/uart_console_bridge.v',
             build / 'source/tang/boards/neo/vendor/uart_tx.v',
             build / 'source/tang/boards/neo/vendor/uart_rx.v']
    return dict(build=str(build), cells=selected, cell_count=len(selected),
                control_pin_counts=counts, external_drivers=drivers, io=io,
                relay_controls_on_global_routes={n: global_routes[n]
                    for n in sorted(used_controls & global_routes.keys())},
                clock_routes={n: global_routes.get(n) for n in counts['CLK']},
                sha256={str(p): sha(p) for p in paths})


def main():
    out = HERE / 'console_output_review'
    if out.exists():
        raise ValueError('Existing evidence must not be overwritten')
    stages = {label: inspect(ROOT / 'tang/impl' / name) for label, name in
              [('parent', 'console_neo_n56_observe'), ('candidate', 'console_neo_n56r1')]}
    old, new = stages['parent'], stages['candidate']
    changes = [name for name in sorted(old['cells'].keys() | new['cells'].keys())
               if old['cells'].get(name) != new['cells'].get(name)]
    result = dict(scope=__doc__, stages=stages, changed_relay_cells=changes,
                  relay_primitives_and_parameters_unchanged=not changes,
                  external_drivers_unchanged=old['external_drivers'] == new['external_drivers'],
                  io_unchanged=old['io'] == new['io'],
                  hardware_access=False,
                  limitations=[
                      'No electrical observation or board access; a silent host console is not explained by this comparison.',
                      'A functional netlist comparison does not establish routed timing or absence of glitches.',
                      'Clock/reset logic identity does not prove the observed electrical levels.',
                      'The input console path uses the USB PHY domain and is outside this output-relay comparison.'],
                  tool_sha256={str(Path(__file__)): sha(Path(__file__))})
    out.mkdir()
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    summary = {k: result[k] for k in ('relay_primitives_and_parameters_unchanged',
                                     'external_drivers_unchanged', 'io_unchanged')}
    summary.update(cell_count=new['cell_count'],
                   controls_on_global_routes=new['relay_controls_on_global_routes'],
                   clock_routes=new['clock_routes'])
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
