#!/usr/bin/env python3
"""Prepare/build N56r2: four regional INS_LOC additions, same routed-parent netlist.

Preparation has no compiler or hardware access. Building requires the exact SHA
of the prepared manifest, rejects input drift, and reruns the dual-board guard.
No RTL, SDC, DDR, device, frequency or LOCAL_CLOCK change is permitted.
"""
import argparse
from collections import defaultdict
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from board_contract import before_build, record_build
from check_ddr_profile import audit as audit_ddr
from gowin_toolchain import IDE, environment
from build_local_controls import cells, norm

PARENT = ROOT/'tang/impl/console_neo_n56r1'
PREPARED = HERE/'n56r2_placement'
NAME = 'console_neo_n56r2'
SHA_BIT = '426389b02a4c1c240a28a711546569315e5c4d9478199f12e1e38f46009d3d2d'
SHA_NET = 'c05e9b7a4bcafba8cd31e4b985b4ba37ace8ecbd0e4b999745ac60d7a5fb461d'
SHA_SDC = 'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113'
SHA_CST = '1550edcee84be747e17a8bb43c97f52fbdb0531afee39374d02f12bd8d97e047'
TARGETS = {
    'u_gpu_debug/observe_words_s1_49_s0': ('DFFRE', "1'b0", 'R[48:52]C[65:70]'),
    'u_gpu_debug/observe_words_s2_49_s0': ('DFFRE', "1'b0", 'R[48:52]C[65:70]'),
    'u_soc/u_bridge/n63_s0': ('LUT3', "8'h10", 'R[25:40]C[135:150]'),
    'u_accel/u_v1/u_pixels/n22637_s33': ('LUT4', "16'h00bf", 'R[40:50]C[35:45]'),
}
CONTROLS = ('u_accel/u_v1/n56220_6', 'u_gpu_debug/n2835_5', 'u_gpu_debug/mem_up[1]')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
dump = lambda p, v: p.write_text(json.dumps(v, indent=2)+'\n')


def initial_values(text):
    return {norm(n): v.lower() for n, v in re.findall(
        r'^\s*defparam\s+(\\\S+|\w+)\s*\.INIT\s*=\s*([^;]+);', text, re.M)}


def placement_proof():
    vg = (PARENT/'console_neo.vg').read_text()
    vo = (PARENT/'impl/pnr/console_neo.vo').read_text()
    modules = {m[1]: m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule', vg, re.M|re.S)}
    mapped = {name: cells(body) for name, body in modules.items()}
    routed = cells(vo)
    inits = initial_values(vo)
    timing = (PARENT/'impl/pnr/console_neo.tr').read_text()
    setup = timing.split('\n3.3.1 Setup Analysis Report\n')[1].split('\n3.3.2 ')[0]
    paths = []
    for number, body in re.findall(r'\n\t+Path(\d+)\t+\n(.*?)(?=\n\t+Path\d+\t+\n|\Z)', setup, re.S):
        item = {key.lower(): re.search(r'^'+key+r'\s*:\s*(.+)$', body, re.M).group(1)
                for key in ('Slack', 'From', 'To')}
        item.update(number=int(number), slack=float(item['slack']), body=body)
        paths.append(item)
    if len(paths) != 1000 or [p['slack'] for p in paths if p['slack'] < 0] != [-0.440, -0.065, -0.049]:
        raise ValueError('Parent setup report changed')
    locations = {}
    for loc, node in re.findall(r'\b(R\d+C\d+\[\d+\]\[[AB]\])\s+(\S+)', setup):
        locations[node.rsplit('/', 1)[0]] = loc
    drivers, loads = defaultdict(list), defaultdict(list)
    for name, primitive in routed.items():
        for pin, net in primitive['pins'].items():
            (drivers if pin in ('Q', 'F', 'O', 'OF') else loads)[net].append(
                dict(instance=name, primitive=primitive['kind'], pin=pin, reported_location=locations.get(name)))

    def endpoints(net):
        pending, seen, end, unknown = [net], set(), {}, {}
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            for load in loads[current]:
                name, kind = load['instance'], load['primitive']
                if kind.startswith('DFF'):
                    end[(name, load['pin'])] = load
                elif kind.startswith(('LUT', 'MUX')):
                    outputs = [v for p, v in routed[name]['pins'].items() if p in ('F', 'O', 'OF')]
                    if not outputs:
                        unknown[(name, load['pin'])] = load
                    pending += outputs
                else:
                    unknown[(name, load['pin'])] = load
        return dict(sequential=list(end.values()), other_boundaries=list(unknown.values()))

    entries = []
    for name, (kind, init, region) in TARGETS.items():
        parts, module = name.split('/'), 'console_neo'
        for part in parts[:-1]:
            module = mapped[module][part]['kind']
        mapped_cell = mapped[module][parts[-1]]
        if mapped_cell['kind'] != kind or routed[name]['kind'] != kind:
            raise ValueError('Primitive changed: '+name)
        if initial_values(modules[module]).get(parts[-1]) != init or inits.get(name) != init:
            raise ValueError('Primitive INIT changed: '+name)
        adjacent = []
        for pin, net in routed[name]['pins'].items():
            if pin in ('Q', 'F'):
                adjacent.append(dict(pin=pin, net=net, direct_loads=loads[net], endpoints=endpoints(net)))
            elif pin not in ('CLK', 'CE', 'RESET', 'CLEAR'):
                adjacent.append(dict(pin=pin, net=net, direct_drivers=drivers[net]))
        reported = [{k: v for k, v in p.items() if k != 'body'} for p in paths if name+'/' in p['body']]
        entries.append(dict(instance=name, primitive=kind, init=init, region=region,
            reported_location=locations.get(name), mapped_module=module,
            mapped_pins=mapped_cell['pins'], routed_pins=routed[name]['pins'],
            adjacent=adjacent, reported_setup_paths=reported))
    negative = [p for p in paths if p['slack'] < 0]
    if not all(any(name+'/' in p['body'] for name in TARGETS) for p in negative):
        raise ValueError('A negative endpoint is uncovered')
    return dict(targets=entries, negative_paths=negative, negative_paths_covered=3,
        paths_reported=1000, report_command='report_timing -setup -max_paths 1000 -max_common_paths 1',
        limitations=['Unreported paths/locations are unknown, not passing measurements.',
            'Output traversal stops at sequential pins; non LUT/MUX boundaries are listed explicitly.',
            'Regional constraints propose a placement; no predicted timing closure.',
            'Full setup, hold, recovery, removal and structural qualification is required after rerouting.',
            'Geometry material/viewport/face controls still have other LW nets outside this experiment.'])


def inputs():
    manifest = json.loads((PARENT/'sources.json').read_text())
    actual = {str(p.relative_to(PARENT/'source')): sha(p) for p in (PARENT/'source').rglob('*') if p.is_file()}
    if actual != manifest:
        raise ValueError('Parent source tree changed')
    if sha(PARENT/'console_neo.vg') != SHA_NET or sha(PARENT/'source/tang/boards/neo/neo.sdc') != SHA_SDC:
        raise ValueError('Parent netlist/SDC changed')
    cst = PARENT/'source/tang/boards/neo/neo.cst'
    if sha(cst) != SHA_CST:
        raise ValueError('Parent CST changed')
    q = json.loads((PARENT/'qualification.json').read_text())
    if q['bitstream_sha256'] != SHA_BIT:
        raise ValueError('Different parent bitstream')
    controls = json.loads((PARENT/'local_controls_audit.json').read_text())
    if controls['passed'] is not True or controls['same_synthesis_netlist'] is not True:
        raise ValueError('Parent local control proof failed')
    for name, expected in controls['checks_sha256'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Changed local control evidence: '+name)
    ddr = audit_ddr(PARENT/'source', variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('Parent DDR profile differs')
    original = cst.read_text()
    for net in CONTROLS:
        if original.count(f'CLOCK_LOC "{net}" LOCAL_CLOCK;') != 1:
            raise ValueError('Local control changed: '+net)
    if any(re.search(r'INS_LOC\s+"'+re.escape(name)+'"', original) for name in TARGETS):
        raise ValueError('Would override existing placement')
    addition = '\n'+''.join(f'INS_LOC "{name}" {region};\n' for name, (_, _, region) in TARGETS.items())
    paths = [PARENT/p for p in ('sources.json', 'console_neo.vg', 'build.tcl', 'qualification.json',
        'observer_build.json', 'local_controls_audit.json', 'impl/pnr/console_neo.vo',
        'impl/pnr/console_neo.tr', 'impl/pnr/console_neo.rpt.txt', 'source/tang/boards/neo/neo.cst',
        'source/tang/boards/neo/neo.sdc', 'font8x16.hex', 'rtl/video/font8x16.hex',
        'rtl/usbhost/usb_hid_host_rom.hex')]
    paths += [Path(__file__), HERE/'build_local_controls.py', IDE/'bin/gw_sh']
    return dict(parent=str(PARENT), name=NAME, hardware_access=False, synthesis=False,
        parent_bitstream_sha256=SHA_BIT, parent_inputs_sha256={str(p): sha(p) for p in paths},
        source_manifest=manifest, original_cst=original, candidate_cst=original+addition,
        exact_added_lines=addition.strip().splitlines(), unchanged_local_controls=list(CONTROLS),
        changed_source_files=['tang/boards/neo/neo.cst'], ddr_profile=ddr,
        compiler=str(IDE/'bin/gw_sh'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--build-reviewed', metavar='MANIFEST_SHA256')
    args = parser.parse_args()
    record = inputs()
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        (PREPARED/'neo.cst').write_text(record['candidate_cst'])
        (PREPARED/'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True), record['candidate_cst'].splitlines(True),
            fromfile='N56r1/neo.cst', tofile='N56r2/neo.cst')))
        dump(PREPARED/'placement_proof.json', placement_proof())
        record['prepared_sha256'] = {p.name: sha(p) for p in PREPARED.iterdir()}
        dump(PREPARED/'manifest.json', record)
        print(json.dumps(dict(prepared=str(PREPARED), manifest_sha256=sha(PREPARED/'manifest.json'),
                              added=record['exact_added_lines']), indent=2))
        return
    if sha(PREPARED/'manifest.json') != args.build_reviewed:
        raise ValueError('Different prepared manifest; review required')
    reviewed = json.loads((PREPARED/'manifest.json').read_text())
    expected = dict(reviewed)
    prepared_hashes = expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation; review required')
    for name, checksum in prepared_hashes.items():
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
        timing_placement_manifest_sha256=args.build_reviewed))
    for name in ('manifest.json', 'placement_proof.json', 'constraints.diff'):
        shutil.copy2(PREPARED/name, out/('placement_'+name))
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
