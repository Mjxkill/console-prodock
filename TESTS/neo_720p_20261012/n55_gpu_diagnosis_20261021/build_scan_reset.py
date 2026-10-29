#!/usr/bin/env python3
"""Prepare isolated R1 + one scanout reset LOCAL_CLOCK; never access hardware.

Same netlist, RTL, DDR, SDC, frequencies, pins and route options as R1.
Preparation never invokes Gowin. A build requires the reviewed manifest SHA.
"""
import argparse
from collections import Counter, defaultdict
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_timing_placement import (HERE, ROOT, PARENT, SHA_NET, SHA_BIT,
    IDE, environment, sha, dump, inputs as frozen_parent_inputs,
    initial_values, before_build, record_build)
from build_local_controls import cells
from audit_gpu_control_inventory import bit_expander, primitive_directions, global_nets, CLOCK, pin_base
from prove_geometry_controls import parameters

NAME = 'console_neo_n56r6_scan_reset'
PREPARED = HERE / 'n56r6_scan_reset_prepared'
NET = 'u_gpu/mrst[1]'
ADDITION = f'\nCLOCK_LOC "{NET}" LOCAL_CLOCK;\n'


def index(text):
    cc, expand, directions = cells(text), bit_expander(text), primitive_directions()
    drivers, loads = defaultdict(list), defaultdict(list)
    for name, cell in cc.items():
        for port, expression in cell['pins'].items():
            bits = expand(expression)
            vector = len(bits) > 1 or expression.startswith('{')
            for i, net in enumerate(bits):
                pin = f'{port}[{len(bits)-1-i}]' if vector else port
                (drivers if directions.get(cell['kind'], {}).get(port) == 'output' else loads)[net].append((name, cell['kind'], pin))
    return cc, parameters(text), drivers, loads, directions


def reset_proof():
    vg = (PARENT / 'console_neo.vg').read_text()
    modules = {m[1]: m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule', vg, re.M | re.S)}
    top = cells(modules['console_neo'])
    if top['u_gpu']['kind'] != 'gpu_scanout':
        raise ValueError('Unexpected scanout hierarchy')
    if 'mrst' in top['u_gpu']['pins'] or any('mrst' in p for p in top['u_gpu']['pins']):
        raise ValueError('Scan reset unexpectedly exported through a port')
    stages = {}
    for stage, text, prefix in [('synthesis', modules['gpu_scanout'], ''),
                                ('routed', (PARENT / 'impl/pnr/console_neo.vo').read_text(), 'u_gpu/')]:
        cc, pp, dd, ll, directions = index(text)
        target = prefix + 'mrst[1]'
        name = prefix + 'mrst_1_s0'
        first = prefix + 'mrst_0_s0'
        if dd[target] != [(name, 'DFFCE', 'Q')]:
            raise ValueError('Second reset-stage driver differs: ' + stage)
        expected_clear = 'n3932_6' if stage == 'synthesis' else 'u_gpu_debug/gowin_split_inv_from_n3932_s2_onet'
        expected = {'D': prefix + 'mrst[0]', 'CLK': 'gpu_clk', 'CE': 'VCC', 'CLEAR': expected_clear, 'Q': target}
        if cc[name]['pins'] != expected or initial_values(text).get(name) != "1'b0":
            raise ValueError('Second reset-stage pins/INIT differ: ' + stage)
        expected_first = dict(expected, D='VCC', Q=prefix + 'mrst[0]')
        if cc[first]['kind'] != 'DFFCE' or cc[first]['pins'] != expected_first or initial_values(text).get(first) != "1'b0":
            raise ValueError('First reset-stage pins/INIT differ: ' + stage)
        if any(CLOCK.fullmatch(pin_base(p)) for _, _, p in ll[target]):
            raise ValueError('Scan reset drives a clock pin')
        if stage == 'routed':
            inv = cc['u_gpu_debug/gowin_split_inv_from_n3932_s2']
            if inv != {'kind': 'INV', 'pins': {'I': 'vid_hrstn', 'O': expected_clear}}:
                raise ValueError('Async reset source differs')
            if len(ll[target]) != 20:
                raise ValueError('Unexpected direct routed reset fanout')
        todo, seen, leaves, unknown = [target], set(), set(), set()
        while todo:
            net = todo.pop()
            if net in seen:
                continue
            seen.add(net)
            for n, kind, pin in ll[net]:
                if kind.startswith(('LUT', 'MUX')) or kind in ('INV', 'BUF'):
                    todo += [v for p, v in cc[n]['pins'].items() if directions.get(kind, {}).get(p) == 'output']
                elif kind.startswith('DFF'):
                    leaves.add((n, kind, pin))
                else:
                    unknown.add((n, kind, pin))
        stages[stage] = dict(net=target, driver=name, first_stage=first,
            synchronizers={n: dict(cc[n], parameters=pp.get(n, {})) for n in (first, name)},
            direct_loads=ll[target], direct_load_pin_counts=dict(Counter(p for _, _, p in ll[target])),
            combinationally_reachable_dff_pins=sorted(leaves), other_boundaries=sorted(unknown),
            interpretation='Combinational influence only; no claim that every reached pin is a reset.')
    routes = global_nets(PARENT)
    if routes.get(NET) != 'LW':
        raise ValueError('Expected scanout LW absent')
    paths = [PARENT / 'console_neo.vg', PARENT / 'impl/pnr/console_neo.vo',
             PARENT / 'impl/pnr/console_neo.rpt.txt', PARENT / 'source/tang/boards/neo/neo.cst',
             PARENT / 'source/tang/rtl/video/gpu_scanout.v', Path(__file__),
             HERE / 'audit_gpu_control_inventory.py', HERE / 'prove_geometry_controls.py']
    return dict(net=NET, parent_route='LW', stages=stages,
        cst_name_basis='Exact hierarchical internal signal in synthesis, routed netlist and global-resource report; no top-level alias.',
        parser_status='Not invoked during preparation; CST acceptance remains required.',
        clock_pin_load_count=0, hardware_access=False,
        sha256={str(p): sha(p) for p in paths},
        limitations=['No electrical observation of mrst; LW route is a hypothesis, not an established cause.',
                    'The Pro Dock reference also routes its scanout reset on LW.',
                    'Changing one constraint recomputes whole placement/routing; recheck all timing and control audits.',
                    'R1 material/camera/face controls stay unchanged and remain unqualified for complete 3D.'])


def inputs():
    r = frozen_parent_inputs()
    if sha(PARENT / 'impl/pnr/console_neo.fs') != SHA_BIT:
        raise ValueError('R1 bitstream changed')
    if re.search(r'CLOCK_LOC\s+"' + re.escape(NET) + '"', r['original_cst']):
        raise ValueError('Existing scanout-reset constraint would be overridden')
    r.update(name=NAME, candidate_cst=r['original_cst'] + ADDITION,
        exact_added_lines=ADDITION.strip().splitlines(), experiment='single_scanout_reset_routing_class',
        new_local_control=NET, parent_is_n56r1=True, n56r2_placements_included=False)
    paths = [Path(__file__), HERE / 'audit_gpu_control_inventory.py', HERE / 'prove_geometry_controls.py',
             PARENT / 'impl/pnr/console_neo.fs']
    r['parent_inputs_sha256'].update({str(p): sha(p) for p in paths})
    out = ROOT / 'tang/impl' / NAME
    settings = [line.replace(str(PARENT), str(out)) for line in (PARENT / 'build.tcl').read_text().splitlines()
                if line.startswith(('set_device ', 'set_option '))]
    r['candidate_tcl'] = '\n'.join(settings + [f'add_file {{{out / "console_neo.vg"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out / "source/tang/boards/neo/neo.sdc"}}}', 'run pnr', ''])
    return r


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
        proof = reset_proof()
        PREPARED.mkdir(exist_ok=False)
        (PREPARED / 'neo.cst').write_text(record['candidate_cst'])
        (PREPARED / 'build.tcl').write_text(record['candidate_tcl'])
        (PREPARED / 'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True), record['candidate_cst'].splitlines(True),
            fromfile='N56r1/neo.cst', tofile='N56r6_scan_reset/neo.cst')))
        dump(PREPARED / 'reset_proof.json', proof)
        record['prepared_sha256'] = {p.name: sha(p) for p in PREPARED.iterdir()}
        dump(PREPARED / 'manifest.json', record)
        print(json.dumps(dict(prepared=str(PREPARED), manifest_sha256=sha(PREPARED / 'manifest.json'),
                              added=record['exact_added_lines']), indent=2))
        return
    if sha(PREPARED / 'manifest.json') != a.build_reviewed:
        raise ValueError('Different prepared manifest; review required')
    reviewed = json.loads((PREPARED / 'manifest.json').read_text())
    expected = dict(reviewed)
    hashes = expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation; review required')
    for name, checksum in hashes.items():
        if sha(PREPARED / name) != checksum:
            raise ValueError('Prepared evidence changed: ' + name)
    proof = json.loads((PREPARED / 'reset_proof.json').read_text())
    for path, checksum in proof['sha256'].items():
        if sha(Path(path)) != checksum:
            raise ValueError('Proof input changed: ' + path)
    out = ROOT / 'tang/impl' / NAME
    out.mkdir(exist_ok=False)
    record_build(out, contract)
    shutil.copytree(PARENT / 'source', out / 'source')
    (out / 'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    shutil.copy2(PARENT / 'console_neo.vg', out / 'console_neo.vg')
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT / name, target)
        if sha(target) != sha(PARENT / name):
            raise ValueError('Initialization copy differs: ' + name)
    updated = {str(p.relative_to(out / 'source')): sha(p) for p in (out / 'source').rglob('*') if p.is_file()}
    old = record['source_manifest']
    if set(updated) != set(old) or sorted(k for k in updated if updated[k] != old[k]) != record['changed_source_files']:
        raise ValueError('Unexpected source changes')
    if sha(out / 'console_neo.vg') != SHA_NET:
        raise ValueError('Netlist copy differs')
    dump(out / 'sources.json', updated)
    observer = json.loads((PARENT / 'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(out / 'sources.json'), routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT / 'observer_build.json'))
    dump(out / 'observer_build.json', observer)
    dump(out / 'route.json', dict(parent=str(PARENT), netlist_sha256=SHA_NET,
        scan_reset_manifest_sha256=a.build_reviewed))
    for path in PREPARED.iterdir():
        shutil.copy2(path, out / ('scan_reset_' + path.name))
    (out / 'build.tcl').write_text(record['candidate_tcl'])
    with (out / 'build.log').open('w') as log:
        done = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=out, env=environment(),
                              stdout=log, stderr=subprocess.STDOUT)
    failed = bool(done.returncode or re.search(r'^ERROR', (out / 'build.log').read_text(), re.M))
    dump(out / 'route_result.json', dict(status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',
        child_returncode=done.returncode, manifest_sha256=a.build_reviewed, hardware_access=False))
    if failed:
        raise SystemExit('Routing failed')
    print(out)


if __name__ == '__main__':
    main()
