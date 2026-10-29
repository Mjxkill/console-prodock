#!/usr/bin/env python3
"""N56r9 route2: regroup measured blitter paths, retaining the exact synthesis.

Only regional INS_LOC entries change. No board access, RTL, SDC, frequency,
DDR, reset or clock-allocation change. A routed result is not a qualification.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from prepare_scan_observer import ROOT, HERE, sha, replace
from route_scan_observer import NETSHA, modules, cells, parameter, proof

sys.path.insert(0, str(ROOT/'tools'))
from board_contract import before_build, record_build
from check_ddr_profile import audit
from gowin_toolchain import IDE, PRIMITIVES, environment
sys.path.insert(0, str(ROOT/'optimizer'))
from reports import fixed_constraints
from audit_gpu_control_inventory import global_nets
from build_timing_placement import initial_values

PARENT = ROOT/'tang/impl/console_neo_n56r9_route1'
OUT = ROOT/'tang/impl/console_neo_n56r9_route2'
PREPARED = HERE/'n56r9_route2_prepared'
ANCHOR = 'u_accel/gpu_debug_state_102_s0'
REGION = 'R[1:25]C[140:175]'
MANIFEST = 'ee048afa956773741ef9a69a4ea8b22a558876b934f0ec00809ca9c794ec660f'
REPORT = '793241f9ee3c9aa65e2d54f2c2405e1a82435d3281f468ccafa30943c46d40ba'
CST = '61ed0d9121e9e01ba8245703c1f3510000fed656a5f8efd3ba8cc7f1d6316047'
SDC = 'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113'
LOCAL = ['u_accel/u_v1/n56220_6', 'u_gpu_debug/n2835_5', 'scan_debug_live[224]']


def inputs():
    for filename, digest in {'sources.json': MANIFEST, 'console_neo.vg': NETSHA,
            'impl/pnr/console_neo.tr': REPORT, 'source/tang/boards/neo/neo.cst': CST,
            'source/tang/boards/neo/neo.sdc': SDC}.items():
        assert sha(PARENT/filename) == digest, filename
    original = json.loads((PARENT/'sources.json').read_text())
    assert original == {str(p.relative_to(PARENT/'source')): sha(p)
        for p in (PARENT/'source').rglob('*') if p.is_file()}
    proposal = json.loads((PREPARED/'optimizer.json').read_text())
    assert proposal['build'] == str(PARENT)
    assert proposal['report_sha256'] == REPORT and proposal['netlist_sha256'] == NETSHA
    assert proposal['base_cst_sha256'] == CST and proposal['region'] == REGION
    assert sha(PREPARED/'optimizer.cst') == proposal['candidate_cst_sha256']
    assert len(proposal['cells']) == 28 and ANCHOR not in proposal['cells']
    old = (PARENT/'source/tang/boards/neo/neo.cst').read_text()
    proposed = (PREPARED/'optimizer.cst').read_text()
    expected = old.rstrip()+'\n\n// Experimental placement; full routing and qualification required.\n'
    expected += ''.join(f'INS_LOC "{name}" {REGION};\n' for name in sorted(proposal['cells']))
    assert proposed == expected
    candidate = replace(proposed, f'INS_LOC "{ANCHOR}" R[45:65]C[45:65];',
        f'INS_LOC "{ANCHOR}" {REGION};')
    assert fixed_constraints(old) == fixed_constraints(candidate)
    for name in LOCAL:
        assert old.count(f'CLOCK_LOC "{name}" LOCAL_CLOCK;') == 1
    # Verify targets exist before P&R; route-only replicas cannot be constrained.
    bodies = modules(PARENT/'console_neo.vg')
    mapped = {name: cells(body) for name, body in bodies.items()}
    routed_text = (PARENT/'impl/pnr/console_neo.vo').read_text()
    routed = cells(routed_text)
    routed_init = initial_values(routed_text)
    dffre = re.search(r'^module DFFRE\b.*?^endmodule', PRIMITIVES.read_text(), re.M|re.S)[0]
    default_init = re.search(r'parameter\s+INIT\s*=\s*([^;]+);', dffre)[1].strip().lower()
    assert default_init == "1'b0"
    targets = []
    for name in sorted(set(proposal['cells']) | {ANCHOR}):
        parts, module = name.split('/'), 'console_neo'
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        cell = mapped[module][parts[-1]]
        assert cell['kind'] == routed[name]['kind']
        assert cell['kind'].startswith(('DFF', 'LUT', 'ALU'))
        init = parameter(bodies[module], parts[-1])
        effective_init = default_init if init is None and cell['kind'] == 'DFFRE' else init
        assert effective_init == routed_init.get(name), name
        targets.append(dict(instance=name, primitive=cell['kind'], explicit_init=init,
            effective_init=effective_init, routed_init=routed_init.get(name),
            mapped_pins=cell['pins'], region=REGION))
    analysis = json.loads((PREPARED/'timing_analysis.json').read_text())
    assert analysis['report_sha256'] == REPORT
    worst = analysis['paths'][0]
    assert worst['slack_ns'] == -4.103
    assert worst['launch_clock'] == worst['clock'] == 'ddr3_sys_clk:[R]'
    assert [a['delay_ns'] for a in worst['arcs'] if a['kind'] == 'tNET' and
        a['cell'] in (ANCHOR, 'u_accel/u_blitter/wp_6_s3')] == [5.605, 6.469]
    ddr = audit(PARENT/'source', variant='neo-fifo-registers')
    assert ddr['passed']
    sim_path = HERE/'scan_observer_sim/result.json'
    sim = json.loads(sim_path.read_text())
    assert sim['passed']
    for name, digest in sim['sources_sha256'].items():
        assert sha(Path(name)) == digest
    mapping = proof()
    assert mapping == json.loads((PARENT/'constraint_mapping.json').read_text())
    paths = [Path(__file__), HERE/'route_scan_observer.py', PRIMITIVES,
        ROOT/'optimizer/placement.py', ROOT/'optimizer/reports.py',
        PREPARED/'optimizer.cst', PREPARED/'optimizer.json', PREPARED/'timing_analysis.json',
        PARENT/'console_neo.vg', PARENT/'impl/pnr/console_neo.vo',
        PARENT/'impl/pnr/console_neo.tr', PARENT/'sources.json', PARENT/'build.tcl',
        PARENT/'source/tang/boards/neo/neo.cst', PARENT/'source/tang/boards/neo/neo.sdc', sim_path]
    return original, candidate, dict(parent=str(PARENT), netlist_sha256=NETSHA,
        source_manifest_sha256=MANIFEST, source_files_changed=['tang/boards/neo/neo.cst'],
        replaced_anchor=ANCHOR, added_regional_constraints=28, targets=targets,
        worst_parent_path=worst, constraint_mapping=mapping, ddr_profile=ddr,
        inputs_sha256={str(p): sha(p) for p in paths},
        constraints_diff=''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True),
            fromfile='N56r9_route1', tofile='N56r9_route2')),
        hardware_access=False, synthesis=False,
        limits=['Physical placement experiment; full static timing and mapping review required.',
                'Does not establish the cause of the N56r8 framebuffer stall.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    assert not OUT.exists(), 'Never overwrite a previous build'
    original, candidate, record = inputs()
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.check_only:
        (PREPARED/'review.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps({k: record[k] for k in ('parent', 'netlist_sha256',
            'replaced_anchor', 'added_regional_constraints', 'hardware_access')}, indent=2))
        return
    reviewed = json.loads((PREPARED/'review.json').read_text())
    assert record == reviewed, 'Inputs changed since review; check again'
    OUT.mkdir()
    record_build(OUT, contract)
    shutil.copytree(PARENT/'source', OUT/'source')
    (OUT/'source/tang/boards/neo/neo.cst').write_text(candidate)
    for name in ('console_neo.vg', 'font8x16.hex', 'rtl/video/font8x16.hex',
            'rtl/usbhost/usb_hid_host_rom.hex', 'constraint_mapping.json'):
        dest = OUT/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT/name, dest)
    updated = {str(p.relative_to(OUT/'source')): sha(p)
        for p in (OUT/'source').rglob('*') if p.is_file()}
    assert set(updated) == set(original)
    assert {n for n in original if original[n] != updated[n]} == {'tang/boards/neo/neo.cst'}
    assert sha(OUT/'console_neo.vg') == NETSHA
    (OUT/'sources.json').write_text(json.dumps(updated, indent=2)+'\n')
    settings = [line.replace(str(PARENT), str(OUT)) for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ', 'set_option '))]
    (OUT/'build.tcl').write_text('\n'.join(settings+[
        f'add_file {{{OUT/"console_neo.vg"}}}', f'add_file {{{OUT/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{OUT/"source/tang/boards/neo/neo.sdc"}}}', 'run pnr', '']))
    (OUT/'route.json').write_text(json.dumps(record, indent=2)+'\n')
    (OUT/'constraints.diff').write_text(record['constraints_diff'])
    print('Routing '+str(OUT), flush=True)
    with (OUT/'build.log').open('x') as log:
        result = subprocess.run([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=OUT,
            env=environment(), stdout=log, stderr=log)
    log = (OUT/'build.log').read_text()
    failed = bool(result.returncode or re.search(r'^ERROR', log, re.M) or 'Bitstream generation completed' not in log)
    (OUT/'route_result.json').write_text(json.dumps(dict(returncode=result.returncode,
        status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED', hardware_access=False), indent=2)+'\n')
    if failed:
        raise SystemExit('Route failed; retained logs at '+str(OUT))
    with (OUT/'qualification_automatic.log').open('x') as log:
        checked = subprocess.run([sys.executable, str(ROOT/'tools/check_neo_timing.py'), str(OUT)],
            cwd=ROOT, stdout=log, stderr=log, timeout=600)
    globals_used = global_nets(OUT)
    unexpected = {n: globals_used[n] for n in LOCAL if n in globals_used}
    report = dict(qualification_returncode=checked.returncode, local_controls=LOCAL,
        unexpected_global_controls=unexpected, passed=checked.returncode == 0 and not unexpected,
        hardware_access=False, note='Routed observer mapping/reset review is still required before hardware load.')
    (OUT/'automatic_checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Qualification or local-control route audit failed')


if __name__ == '__main__':
    main()
