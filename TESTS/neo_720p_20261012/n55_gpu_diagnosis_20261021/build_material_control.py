#!/usr/bin/env python3
"""N56r3 A/B experiment: N56r1 plus one material-capture LOCAL_CLOCK.

No N56r2 placements, synthesis, RTL, DDR, SDC, frequency or hardware change.
--prepare-only creates evidence; --build-reviewed requires its exact manifest.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_timing_placement import (
    HERE, ROOT, PARENT, SHA_NET, IDE, environment, sha, dump,
    inputs as frozen_parent_inputs, initial_values, before_build, record_build,
)
from build_local_controls import cells

NAME = 'console_neo_n56r3'
PREPARED = HERE/'n56r3_material_control'
NET = 'u_accel/u_v1/n56864_3'
DRIVER = 'u_accel/u_v1/n56864_s0'
ADDITION = f'\nCLOCK_LOC "{NET}" LOCAL_CLOCK;\n'


def material_proof():
    vg = (PARENT/'console_neo.vg').read_text()
    vo = (PARENT/'impl/pnr/console_neo.vo').read_text()
    modules = {m[1]: m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule', vg, re.M|re.S)}
    top = cells(modules['console_neo'])
    accel = cells(modules[top['u_accel']['kind']])
    if accel['u_v1']['kind'] != 'gpu_geometry':
        raise ValueError('Geometry hierarchy changed')
    stages = {}
    for stage, text, prefix in (('synthesis', modules['gpu_geometry'], ''),
                                ('routed', vo, 'u_accel/u_v1/')):
        cc = cells(text)
        net, name = prefix+'n56864_3', prefix+'n56864_s0'
        drivers = [n for n, c in cc.items() if any(c['pins'].get(p) == net for p in ('Q', 'F', 'O'))]
        if drivers != [name] or cc[name]['kind'] != 'LUT3':
            raise ValueError('Material driver changed: '+stage)
        if initial_values(text).get(name) != "8'h80":
            raise ValueError('Material LUT INIT changed: '+stage)
        loads = [dict(instance=n, primitive=c['kind'], pin=p)
                 for n, c in cc.items() for p, v in c['pins'].items()
                 if v == net and p not in ('Q', 'F', 'O')]
        expected = {prefix+f'material_{i}_s0' for i in range(256) if i not in (29, 30, 31)}
        if len(loads) != 253 or {x['instance'] for x in loads} != expected:
            raise ValueError('Material capture load set changed: '+stage)
        if any(x['pin'] != 'CE' or x['primitive'] != 'DFFRE' for x in loads):
            raise ValueError('Unexpected material control pin: '+stage)
        expected_pins = ({'I0': 'gpu_debug_state_46', 'I1': 'state[67]',
                          'I2': 'n56864_4', 'F': 'n56864_3'} if stage == 'synthesis' else
                         {'I0': 'gpu_debug_state[46]', 'I1': 'u_accel/u_v1/state[67]',
                          'I2': 'u_accel/u_v1/n56864_4', 'F': NET})
        if cc[name]['pins'] != expected_pins:
            raise ValueError('Material LUT inputs differ: '+stage)
        stages[stage] = dict(driver=name, primitive='LUT3', init="8'h80",
                             pins=cc[name]['pins'], loads=loads)
    route_report = (PARENT/'impl/pnr/console_neo.rpt.txt').read_text()
    line = re.search(r'^\s*'+re.escape(NET)+r'\s*\|\s*LW\s*\|.*$', route_report, re.M)
    if not line:
        raise ValueError('Expected material LW route absent from N56r1')
    return dict(net=NET, parent_route='LW', parent_report_line=line[0].strip(),
        stages=stages, load_count=253, all_loads_are_material_ce=True,
        clock_pin_load_count=0, absent_material_flop_bits=[29, 30, 31],
        logic_change=False, limitations=[
            'Parent hardware symptom is consistent with missing material capture, not proof by itself.',
            'Physical placement/routing is recomputed even with the same netlist.',
            'Only n56864_3 changes routing class; viewport and face LW controls remain unchanged.',
            'Reaudit driver, pins, INIT, load set and global resource table after routing.',
            'The candidate requires full timing qualification before any release claim.'])


def inputs():
    # Reuse only the read-only N56r1 integrity checks, never N56r2 preparation/build.
    record = frozen_parent_inputs()
    original = record['original_cst']
    if re.search(r'CLOCK_LOC\s+"'+re.escape(NET)+'"', original):
        raise ValueError('Refusing to override existing material constraint')
    record.update(name=NAME, candidate_cst=original+ADDITION,
        exact_added_lines=ADDITION.strip().splitlines(), experiment='single_material_ce_routing_class',
        new_local_control=NET, parent_is_n56r1=True, n56r2_placements_included=False)
    record['parent_inputs_sha256'][str(Path(__file__))] = sha(Path(__file__))
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--build-reviewed', metavar='MANIFEST_SHA256')
    a = p.parse_args()
    record = inputs()
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if a.prepare_only:
        proof = material_proof()
        PREPARED.mkdir(exist_ok=False)
        (PREPARED/'neo.cst').write_text(record['candidate_cst'])
        (PREPARED/'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True), record['candidate_cst'].splitlines(True),
            fromfile='N56r1/neo.cst', tofile='N56r3/neo.cst')))
        dump(PREPARED/'material_proof.json', proof)
        record['prepared_sha256'] = {p.name: sha(p) for p in PREPARED.iterdir()}
        dump(PREPARED/'manifest.json', record)
        print(json.dumps(dict(prepared=str(PREPARED), manifest_sha256=sha(PREPARED/'manifest.json'),
            added=record['exact_added_lines'], load_count=proof['load_count']), indent=2))
        return
    if sha(PREPARED/'manifest.json') != a.build_reviewed:
        raise ValueError('Different prepared manifest; review required')
    reviewed = json.loads((PREPARED/'manifest.json').read_text())
    expected = dict(reviewed)
    hashes = expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation; review required')
    for name, checksum in hashes.items():
        if sha(PREPARED/name) != checksum:
            raise ValueError('Prepared evidence changed: '+name)
    out = ROOT/'tang/impl'/NAME
    out.mkdir(exist_ok=False)
    record_build(out, contract)
    shutil.copytree(PARENT/'source', out/'source')
    (out/'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    shutil.copy2(PARENT/'console_neo.vg', out/'console_neo.vg')
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        target = out/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT/name, target)
    updated = {str(p.relative_to(out/'source')): sha(p) for p in (out/'source').rglob('*') if p.is_file()}
    old = record['source_manifest']
    if set(updated) != set(old) or sorted(k for k in updated if updated[k] != old[k]) != record['changed_source_files']:
        raise ValueError('Unexpected source changes')
    dump(out/'sources.json', updated)
    observer = json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(out/'sources.json'), routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT/'observer_build.json'))
    dump(out/'observer_build.json', observer)
    dump(out/'route.json', dict(parent=str(PARENT), netlist_sha256=SHA_NET,
        material_control_manifest_sha256=a.build_reviewed))
    for name in ('manifest.json', 'material_proof.json', 'constraints.diff'):
        shutil.copy2(PREPARED/name, out/('material_'+name))
    shutil.copy2(PARENT/'local_controls_audit.json', out/'parent_local_controls_audit.json')
    settings = [line.replace(str(PARENT), str(out)) for line in (PARENT/'build.tcl').read_text().splitlines()
                if line.startswith(('set_device ', 'set_option '))]
    (out/'build.tcl').write_text('\n'.join(settings+[
        f'add_file {{{out/"console_neo.vg"}}}', f'add_file {{{out/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out/"source/tang/boards/neo/neo.sdc"}}}', 'run pnr', '']))
    with (out/'build.log').open('w') as log:
        done = subprocess.run([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=out, env=environment(),
                              stdout=log, stderr=subprocess.STDOUT)
    if done.returncode or re.search(r'^ERROR', (out/'build.log').read_text(), re.M):
        raise SystemExit('Routing failed')
    print(out)


if __name__ == '__main__':
    main()
