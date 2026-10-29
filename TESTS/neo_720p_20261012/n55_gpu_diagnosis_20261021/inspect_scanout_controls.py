#!/usr/bin/env python3
"""Read-only netlist inventory of R1 scanout clocks, reset and queue controls."""
from collections import Counter
import json
from pathlib import Path

from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, pin_base, CE
from build_timing_placement import ROOT, HERE, sha


def main():
    build = ROOT / 'tang/impl/console_neo_n56r1'
    vo = build / 'impl/pnr/console_neo.vo'
    cc, pp, drivers, loads = indexed_netlist(vo)
    globals_ = global_nets(build)
    prefixes = ('u_gpu/', 'u_scan_queue/', 'u_soc/g_ddr.u_ddr/u_gpu_arb/')
    selected = {n: c for n, c in cc.items() if n.startswith(prefixes)}
    groups = {}
    for prefix in prefixes:
        cells = {n: c for n, c in selected.items() if n.startswith(prefix)}
        controls = {}
        for pin in ('CLK', 'CE', 'CLEAR', 'RESET', 'PRESET', 'SET'):
            controls[pin] = dict(Counter(c['pins'][pin] for c in cells.values()
                                        if pin in c['pins']))
        groups[prefix] = dict(cell_count=len(cells), control_pin_counts=controls)
    nets = set()
    for n in globals_:
        if any(x[0].startswith(prefixes) for x in loads[n] + drivers[n]):
            nets.add(n)
    nets.update(('u_gpu/mrst[1]', 'u_gpu/mrst[0]', 'vid_hrstn'))
    queue_up = {n: cc[n] for n in ('u_scan_queue/up_0_s0', 'u_scan_queue/up_1_s0')}
    nets.update(c['pins']['Q'] for c in queue_up.values())
    # The flattened names are aliases: up[1] and u_scan_queue/up_0[0].
    # Resolve from the preserved synchronizer cells, not guessed RTL names.
    for prefix, g in groups.items():
        if not g['cell_count']:
            raise ValueError('Missing exact group: ' + prefix)
    details = {}
    for net in sorted(nets):
        details[net] = dict(global_route=globals_.get(net),
            drivers=[dict(instance=n, primitive=k, port=p, cell=cc[n], parameters=pp.get(n, {}))
                     for n, k, p in drivers[net]],
            load_pin_counts=dict(Counter(p for _, _, p in loads[net])),
            load_prefix_counts=dict(Counter(n.split('/')[0] for n, _, _ in loads[net])),
            clock_loads=[x for x in loads[net] if CLOCK.fullmatch(pin_base(x[2]))],
            ce_loads=[x for x in loads[net] if CE.fullmatch(pin_base(x[2]))],
            loads=loads[net])
    paths = (vo, build / 'impl/pnr/console_neo.rpt.txt',
             build / 'source/tang/boards/neo/neo.cst',
             build / 'source/tang/boards/neo/neo.sdc', Path(__file__))
    result = dict(build=str(build), groups=groups, queue_up_cells=queue_up, global_and_reset_details=details,
                  sha256={str(p): sha(p) for p in paths}, hardware_access=False,
                  limitations=['Structural inventory only: no assertion about physical levels or waveform.',
                               'Global routing of reset alone is not proof of malfunction.',
                               'No scanout state or outstanding transaction is observable in this inventory.'])
    out = HERE / 'scanout_review/control_inventory_v2.json'
    if out.exists():
        raise ValueError('Existing evidence must not be overwritten')
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({n: dict(route=d['global_route'], loads=sum(d['load_pin_counts'].values()),
                              pins=d['load_pin_counts'], drivers=[x['instance'] for x in d['drivers']])
                      for n, d in details.items()}, indent=2))


if __name__ == '__main__':
    main()
