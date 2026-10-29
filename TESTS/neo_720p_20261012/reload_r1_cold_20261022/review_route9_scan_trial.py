#!/usr/bin/env python3
"""Exact R9 structural evidence for a stopped-CPU scanout diagnostic.

Never loads hardware or alters qualification/audit failures. The resulting
passed flag describes these checks only; timing remains explicitly FAIL.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys

import route_scan_timing_candidates as r
import review_route7_paths as review
from audit_gpu_control_inventory import CLOCK, pin_base

BASE = r.ROOT / 'tang/impl/console_neo_n56r9_route8_hdmi_c150'
OUT = r.ROOT / 'tang/impl/console_neo_n56r9_route9_dma_c150'
FS_SHA = '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde'
EXPECTED = {
    'console_neo.vg': r.NETSHA,
    'impl/pnr/console_neo.fs': FS_SHA,
    'impl/pnr/console_neo.tr': '8615fb10bf487512a859e2bfa0566d636644d5ce3b40025f46df5bb52af92b72',
    'impl/pnr/console_neo.vo': 'd3888d979ae0195b6e0f806e4baa0c255fa5ce288953541090f85d0dc4736b77',
    'impl/pnr/console_neo.rpt.txt': 'e2b858f8c7b7074d652fa4d028447f4171af29dd952bb6eb6b4ad3c68cff39f1',
    'qualification.json': '97f109fff807d0d78274e210c4bbc27fac067b736803f97e034b549834c37307',
    'source/tang/boards/neo/neo.cst': 'e08dd2bd88b2074a758a828a91393cbbbd5a870e77f99c7bc34071cf41a82c89',
    'source/tang/boards/neo/neo.sdc': r.SDC,
}
GLOBAL_DELTA = {
    'gpu_debug_state[48]': ('local', 'LW'),
    'u_accel/u_v1/n59467_5': ('LW', 'local'),
    'u_accel/u_v1/n60439_3': ('LW', 'local'),
    'u_accel/u_v1/n61613_3': ('local', 'LW'),
}


def main():
    target = OUT / 'scan_reset_route9_trial_review.json'
    assert not target.exists(), 'Preserve previous evidence'
    for path, digest in EXPECTED.items():
        assert r.sha(OUT / path) == digest, path
    assert r.sha(BASE / 'impl/pnr/console_neo.vo') == '52172657d2c16db8496230e3b1b90dfe0925fef30fca66bcd4cbc5b72c5e09fd'
    assert r.sha(BASE / 'console_neo.vg') == r.NETSHA
    q = json.loads((OUT / 'qualification.json').read_text())
    assert q['status'] == 'FAIL'
    assert q['timing_checks_ns'] == dict(setup=-.849, hold=.124, recovery=-.360, removal=.196)
    failed = {name: item['errors'] for name, item in q['synthesis_audits'].items() if not item['passed']}
    assert failed == {'gpu_reset_tree': ['Reset 4 still uses a global routing resource']}
    alias_path = OUT / 'scan_observer_reset_alias_proof.json'
    alias = json.loads(alias_path.read_text())
    assert alias['passed'] and alias['all_other_register_fields_identical']
    assert alias['reset_alias_count'] == {'CLEAR': 2, 'RESET': 372}
    assert alias['timing_qualification'] == 'FAIL'
    assert alias['reset_function'] == '!vid_hrstn'
    for path, digest in alias['sha256'].items():
        assert r.sha(Path(path)) == digest, path
    strict = json.loads((OUT / 'scan_observer_audit.json').read_text())
    assert strict['register_changes'] == json.loads((BASE / 'scan_observer_audit.json').read_text())['register_changes']
    assert not strict['global_scanout_ce'] and not any(c['errors'] for c in strict['controls'])
    automatic = json.loads((OUT / 'automatic_checks.json').read_text())
    assert automatic['qualification_returncode'] == 1 and not automatic['passed']
    assert not automatic['changed_constrained_primitives'] and not automatic['unexpected_global_controls']
    old_sources = json.loads((BASE / 'sources.json').read_text())
    new_sources = json.loads((OUT / 'sources.json').read_text())
    for build, manifest in ((BASE, old_sources), (OUT, new_sources)):
        assert manifest == {str(p.relative_to(build / 'source')): r.sha(p)
                            for p in (build / 'source').rglob('*') if p.is_file()}
    assert old_sources.keys() == new_sources.keys()
    assert [name for name in old_sources if old_sources[name] != new_sources[name]] == ['tang/boards/neo/neo.cst']
    cc, params, drivers, loads = r.indexed_netlist(OUT / 'impl/pnr/console_neo.vo')
    old_cc, old_params, old_drivers, old_loads = r.indexed_netlist(BASE / 'impl/pnr/console_neo.vo')
    names = ['u_soc/vid_hrstn_r_s0']
    names += [f'{prefix}/{stem}_{n}_s0' for prefix, stem, count in (
        ('u_gpu', 'mrst', 2), ('u_gpu', 'prst', 2), ('u_accel', 'mrst', 2),
        ('u_accel', 'engine_resetn', 12), ('u_scan_observe', 'up', 2)) for n in range(count)]
    stages = {}
    for name in names:
        assert cc[name] == old_cc[name] and params[name] == old_params[name], name
        assert cc[name]['kind'].startswith('DFF')
        stages[name] = dict(cell=cc[name], parameters=params[name])
    assert len(stages) == 21
    assert cc['u_accel/engine_resetn_4_s0'] == dict(kind='DFFCE', pins=dict(
        D='gpu_debug_state[42]', CLK='gpu_clk', CE='VCC',
        CLEAR='u_scan_observe/gowin_split_inv_from_n6_s2_onet', Q='gpu_debug_state[48]'))
    globals_before, globals_after = r.global_nets(BASE), r.global_nets(OUT)
    delta = {net: (globals_before.get(net, 'local'), globals_after.get(net, 'local'))
             for net in set(globals_before) | set(globals_after) if globals_before.get(net) != globals_after.get(net)}
    assert delta == GLOBAL_DELTA
    changes = []
    for net, (before, after) in sorted(delta.items()):
        assert drivers[net] == old_drivers[net] and sorted(loads[net]) == sorted(old_loads[net])
        assert len(drivers[net]) == 1
        name, kind, pin = drivers[net][0]
        assert cc[name] == old_cc[name] and params.get(name) == old_params.get(name)
        assert not any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in loads[net])
        changes.append(dict(net=net, before=before, after=after, drivers=drivers[net],
            driver_cell=cc[name], driver_parameters=params.get(name), fanout=len(loads[net]),
            loads=loads[net], load_pin_counts=dict(Counter(pin for _, _, pin in loads[net])),
            direct_clock_loads=0, function_and_direct_loads_unchanged=True))
    inverse = 'u_accel/u_v1/u_pixels/gowin_split_inv_from_n1617_s2_onet'
    assert drivers[inverse] == [('u_accel/u_v1/u_pixels/gowin_split_inv_from_n1617_s2', 'INV', 'O')]
    assert cc[drivers[inverse][0][0]] == dict(kind='INV', pins=dict(I='gpu_debug_state[48]', O=inverse))
    assert sorted(loads[inverse]) == sorted(old_loads[inverse])
    assert all(name.startswith('u_accel/u_v1/u_pixels/') and pin in ('RESET', 'SET') for name, _, pin in loads[inverse])
    assert len(loads[inverse]) == 2650
    assert Counter(pin for _, _, pin in loads[inverse]) == {'RESET': 2612, 'SET': 38}
    text = (OUT / 'impl/pnr/console_neo.tr').read_text()
    sections = {n: review.paths(review.section(text, n)) for n in ('1', '2', '3.1', '3.2', '4.1', '4.2')}
    negative_recovery = [p for p in sections['3.1'] if p['slack_ns'] < 0]
    assert {p['destination'] for p in negative_recovery} == {'u_gpu/prst_0_s0', 'u_gpu/prst_1_s0'}
    assert len(negative_recovery) == 2 and all(p['slack_ns'] == -.360 for p in negative_recovery)
    assert all(p['source'] == 'u_soc/vid_hrstn_r_s0' and p['route_ns'] == 7.425 for p in negative_recovery)
    hdmi = review.read(OUT)['hdmi_channels']
    assert [(p['recovery']['slack_ns'], p['removal']['slack_ns']) for p in hdmi] == [(.816,.196),(.706,.263),(.658,.298)]
    files = [OUT / n for n in EXPECTED] + [BASE / 'impl/pnr/console_neo.vo', BASE / 'console_neo.vg',
             BASE / 'sources.json', BASE / 'impl/pnr/console_neo.rpt.txt', BASE / 'scan_observer_audit.json',
             OUT / 'automatic_checks.json', OUT / 'scan_observer_audit.json', OUT / 'sources.json', alias_path, Path(__file__)]
    files += [Path(p) for p in alias['sha256']]
    files += [Path(m.__file__).resolve() for m in list(sys.modules.values())
              if getattr(m, '__file__', None) and str(Path(m.__file__).resolve()).startswith(str(r.ROOT)+'/')
              and Path(m.__file__).suffix == '.py']
    result = dict(passed=True, bitstream_sha256=FS_SHA, qualification_status='FAIL',
        scope='Stopped-CPU scanout reset/RGB diagnostic only', reset_stages_unchanged=True,
        reset_stages=stages, global_route_changes=changes,
        reset4_inverse=dict(net=inverse, loads=loads[inverse], direct_clock_loads=0,
                            function='!engine_resetn[4]', all_2650_loads_are_pixel_shader_reset_or_set=True,
                            load_pin_counts={'RESET': 2612, 'SET': 38}),
        original_synthesis_audit_failures=failed, strict_observer_alias_proof=str(alias_path),
        timing_ns=q['timing_checks_ns'], hdmi_channels=hdmi, negative_recovery=negative_recovery,
        recovery_for_reset_stages=[p for p in sections['3.1'] if p['destination'] in names],
        printed_path_counts={n:dict(total=len(v), negative=sum(p['slack_ns']<0 for p in v),
                                   negative_destinations=len({p['destination'] for p in v if p['slack_ns']<0})) for n,v in sections.items()},
        worst_setup=sorted(sections['1'],key=lambda p:p['slack_ns'])[:20],
        input_sha256={str(p.resolve()):r.sha(p) for p in sorted(set(files))}, hardware_access=False,
        limits=['PASS applies only to the exact structural and identity checks in this document, never to timing or hardware qualification.',
                'The two pixel-domain prst recovery violations remain real. Unchanged reset logic does not prove reliable physical reset release.',
                'Reset4 moved onto LW and feeds the pixel shader through a 2650-load inverter. The original gpu_reset_tree FAIL is retained.',
                'Three geometry CE nets changed local/LW allocation. No direct clock-pin load exists, but this is not a geometry/pixel-engine qualification.',
                'Only a user-authorized stopped-CPU scanout reset/RGB diagnostic may use this evidence. No CPU resume, Linux or GPU commands are covered.',
                'No constraints, validator or failed qualification were modified. Hardware restoration and diagnostic sequencing belong to the sole Neo operator.',
                'Limited printed STA paths cannot prove unprinted endpoints passed. Structural equivalence is not full formal equivalence.'])
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, qualification_status='FAIL', output=str(target),
                         unchanged_reset_stages=len(stages), global_changes=len(changes),
                         negative_recovery=2, hardware_access=False)))


if __name__ == '__main__':
    main()
