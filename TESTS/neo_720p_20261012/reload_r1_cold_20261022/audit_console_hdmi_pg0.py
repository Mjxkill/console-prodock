#!/usr/bin/env python3
"""Audit R1 with HDMI DCE moved from SG0 to PG0, separately from STA."""
from collections import Counter
import json
from pathlib import Path

import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'n55_gpu_diagnosis_20261021'))
from build_timing_placement import PARENT, SHA_NET, sha
NAME='console_neo_n56r7_hdmi_pg0'
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, CE, pin_base


def main():
    build = ROOT / 'tang/impl' / NAME
    output = build / 'hdmi_pg0_audit.json'
    if output.exists():
        raise ValueError('Existing evidence must not be overwritten')
    manifest_path = build / 'hdmi_pg0_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    route = json.loads((build / 'route.json').read_text())
    if sha(manifest_path) != route['hdmi_pg0_manifest_sha256']:
        raise ValueError('Reviewed manifest differs from build record')
    original = json.loads((PARENT / 'sources.json').read_text())
    current = json.loads((build / 'sources.json').read_text())
    actual = {str(p.relative_to(build / 'source')): sha(p) for p in (build / 'source').rglob('*') if p.is_file()}
    errors = []
    if actual != current or current.keys() != original.keys() or sorted(k for k in current if current[k] != original[k]) != ['tang/boards/neo/neo.cst', 'tang/boards/neo/timing_closure.json']:
        errors.append('Source change beyond CST and matching profile')
    if (build / 'source/tang/boards/neo/neo.cst').read_text() != (PARENT / 'source/tang/boards/neo/neo.cst').read_text().replace('INS_LOC "u_video_fast" SG[0];','INS_LOC "u_video_fast" PG[0];',1):
        errors.append('Different CST delta')
    if sha(build / 'console_neo.vg') != SHA_NET:
        errors.append('Changed synthesized netlist')
    if (build / 'build.tcl').read_text() != manifest['candidate_tcl']:
        errors.append('Changed compilation options')
    for relative in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        if sha(build / relative) != sha(PARENT / relative):
            errors.append('Changed memory initialization: ' + relative)
    old_cells, old_params, old_drivers, old_loads = indexed_netlist(PARENT / 'impl/pnr/console_neo.vo')
    new_cells, new_params, new_drivers, new_loads = indexed_netlist(build / 'impl/pnr/console_neo.vo')
    old_global, new_global = global_nets(PARENT), global_nets(build)
    controls = []
    targets = ('u_accel/u_v1/n56220_6', 'u_gpu_debug/n2835_5', 'u_gpu_debug/mem_up[1]')
    for net in targets:
        issues = []
        if old_drivers[net] != new_drivers[net] or len(new_drivers[net]) != 1:
            issues.append('Driver topology changed')
        if sorted(old_loads[net]) != sorted(new_loads[net]):
            issues.append('Scalar/vector load topology changed')
        if any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in new_loads[net]):
            issues.append('Control drives a clock pin')
        names = {n for n, _, _ in old_drivers[net] + old_loads[net]}
        changed = [n for n in sorted(names) if old_cells[n] != new_cells.get(n) or old_params.get(n) != new_params.get(n)]
        if changed:
            issues.append('Driver/load primitive pins or parameters changed')
        if net in new_global:
            issues.append('Control still on global routing: ' + new_global[net])
        controls.append(dict(net=net, errors=issues, changed_cells=changed,
            drivers=new_drivers[net], load_count=len(new_loads[net]),
            load_pin_counts=dict(Counter(p for _, _, p in new_loads[net]))))
    hdmi_changes = [n for n,c in old_cells.items()
        if (n=='u_video_fast' or n.startswith('u_hdmi/'))
        and (c != new_cells.get(n) or old_params.get(n) != new_params.get(n))]
    if hdmi_changes:
        errors.append('HDMI primitive/pin/parameter changes require review: '+str(hdmi_changes))
    import re
    report=(build/'impl/pnr/console_neo.tr').read_text()
    sites=set(re.findall(r'\s((?:PG|SG)\[\d+\])\s+u_video_fast/(?:CLKIN|CLKOUT)\s*$',report,re.M))
    if sites != {'PG[0]'}:
        errors.append('HDMI routed DCE site is not exclusively PG[0]: '+str(sites))
    old_profile=json.loads((PARENT/'source/tang/boards/neo/timing_closure.json').read_text())
    old_profile['hdmi_dce_site']='PG[0]'
    if old_profile != json.loads((build/'source/tang/boards/neo/timing_closure.json').read_text()):
        errors.append('Timing profile changed beyond HDMI site')
    sequential_changes = [n for n, c in old_cells.items()
        if n.startswith(('u_gpu/', 'u_scan_queue/', 'u_soc/g_ddr.u_ddr/u_gpu_arb/')) and c['kind'].startswith('DFF')
        and (c != new_cells.get(n) or old_params.get(n) != new_params.get(n))]
    if sequential_changes:
        errors.append('Scanout/queue/arbitration DFF logical connections changed; review required')
    added_global = []
    for net, route in sorted(new_global.items()):
        if old_global.get(net) == route:
            continue
        entry = dict(net=net, route=route, drivers=new_drivers[net],
            load_pin_counts=dict(Counter(p for _, _, p in new_loads[net])))
        added_global.append(entry)
        if any(n.startswith(('u_gpu/', 'u_accel/', 'u_gpu_debug/', 'u_scan_queue/'))
               and CE.fullmatch(pin_base(p)) for n, _, p in new_loads[net]):
            errors.append('New GPU/scanout/observer CE global route: ' + net)
    paths = [Path(__file__), manifest_path, build / 'sources.json',
             build / 'console_neo.vg', build / 'build.tcl', build / 'source/tang/boards/neo/neo.cst',
             build / 'source/tang/boards/neo/neo.sdc', build / 'impl/pnr/console_neo.vo',
             build / 'impl/pnr/console_neo.rpt.txt', PARENT / 'impl/pnr/console_neo.vo',
             PARENT / 'impl/pnr/console_neo.rpt.txt', HERE.parent/'n55_gpu_diagnosis_20261021/audit_geometry_controls.py',
             HERE.parent/'n55_gpu_diagnosis_20261021/audit_gpu_control_inventory.py']
    result = dict(passed=not errors and all(not x['errors'] for x in controls), errors=errors,
        controls=controls, scanout_sequential_changes=sequential_changes, hdmi_primitive_changes=hdmi_changes, hdmi_sites=sorted(sites),
        new_global_nets=added_global, all_global_nets=new_global,
        removed_global_nets=sorted(set(old_global) - set(new_global)), hardware_access=False,
        sha256={str(p): sha(p) for p in paths},
        limitations=['Physical timing and board scanout must be evaluated separately.',
                    'R1 geometry material, camera and face controls remain outside this experiment.',
                    'A new routed inverse name may create a structural difference requiring review even with equal logic.'])
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], errors=errors,
        control_errors={x['net']: x['errors'] for x in controls if x['errors']},
        changed_scanout_dffs=len(sequential_changes), new_global_nets=added_global,
        result=str(output)), indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
