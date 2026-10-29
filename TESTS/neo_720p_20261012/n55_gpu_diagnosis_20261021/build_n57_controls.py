#!/usr/bin/env python3
"""Prepare or route isolated N57 USB 3.3/3.5 with proven local control names.

Append eight canonical control CLOCK_LOC lines to the N57 CST, following
Gowin's explicit duplicate-alias rejection. Audit all nine control functions.
Keep all existing top-level reset constraints. No synthesis,
RTL/SDC/DDR/frequency change, hardware access, or implicit qualification.
"""
import argparse
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
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build
from check_ddr_profile import audit as audit_ddr
from gowin_toolchain import IDE, environment

PARENT = ROOT / 'tang/impl/console_neo_n57_usb35_syn'
ORIGINAL = ROOT / 'tang/impl/console_neo_n56_observe'
DEST = ROOT / 'tang/impl/console_neo_n57_usb35_r1'
PREPARED = HERE / 'n57_route_r1_unique_prepared'
PROOF = HERE / 'n57_controls'
RESET_PROOF = HERE / 'n57_reset_aliases'
PARSER_PROOF = HERE / 'n57_parser_resolution'
NET_SHA = '51ed167a714c8c3a3ef5f7a918a850ff4c4163b46c3d9f88b43a96db3b6cd190'
SDC_SHA = 'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113'
IPS = {
    'tang/rtl/usb/usb_device_controller.v':
        'f11307d3e31560be2b04dff32b020c969f0ada2610ef232ab648fef2f198ee2a',
    'tang/rtl/usb/usb2_0_softphy.v':
        '5a1eb8388ad4afe13825dd5f650a3a82628f919e337c93426b9d60e41846abaa',
}
INITIALIZATIONS = {
    'font8x16.hex': '4846bbd5a627479a58a6fc2f7aec106c7566812f8340d82febd21dd8c63d879f',
    'rtl/video/font8x16.hex': '4846bbd5a627479a58a6fc2f7aec106c7566812f8340d82febd21dd8c63d879f',
    'rtl/usbhost/usb_hid_host_rom.hex': '44068d210a20cf987d6cb4eecc43a304919914c32f0f692f1e4a68fce2a97e4a',
}
CONTROLS = {
    'captured_command': ('u_accel/u_v1/n56220_6', 312),
    'held_snapshot': ('u_gpu_debug/n2835_5', 283),
    'memory_alive': ('u_gpu_debug/mem_up[1]', 2),
    'material': ('u_accel/u_v1/n56864_3', 256),
    'camera': ('u_accel/u_v1/n57378_3', 204),
    'face': ('u_accel/u_v1/n59467_5', 246),
    'snapshot_bus': ('u_gpu_debug/n4022_5', 315),
    'pending': ('v1_pending', 8),
    'pending_inverse': ('u_accel/v1_tx_addr_27_12', 317),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def snapshot(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.rglob('*')):
        raise ValueError('Snapshot contains a symbolic link')
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def verified_evidence(path):
    result = json.loads(path.read_text())
    if result.get('passed') is not True:
        raise ValueError('Required evidence failed: ' + str(path))
    for name, checksum in result['sha256'].items():
        if sha(Path(name)) != checksum:
            raise ValueError('Evidence dependency changed: ' + name)
    return result


def inputs():
    sources = json.loads((PARENT / 'sources.json').read_text())
    original = json.loads((ORIGINAL / 'sources.json').read_text())
    if snapshot(PARENT / 'source') != sources or snapshot(ORIGINAL / 'source') != original:
        raise ValueError('A frozen source snapshot changed')
    if set(sources) != set(original) or sorted(k for k in sources if sources[k] != original[k]) != sorted(IPS):
        raise ValueError('Synthesis parent differs by more than the two USB IP files')
    if any(sources[name] != checksum for name, checksum in IPS.items()):
        raise ValueError('Unexpected generated USB IP identity')
    completed = json.loads((PARENT / 'usb_synthesis_result.json').read_text())
    netlist = PARENT / 'impl/gwsynthesis/console_neo.vg'
    if (completed['status'] != 'SYNTHESIZED_NOT_ROUTED' or
            completed['netlist_sha256'] != NET_SHA or sha(netlist) != NET_SHA or
            completed['source_manifest_sha256'] != sha(PARENT / 'sources.json') or
            completed['log_sha256'] != sha(PARENT / 'build.log')):
        raise ValueError('Incomplete or modified synthesis result')
    if sha(PARENT / 'source/tang/boards/neo/neo.sdc') != SDC_SHA:
        raise ValueError('Changed timing constraints')
    for name, checksum in INITIALIZATIONS.items():
        if sha(PARENT / name) != checksum or sha(ORIGINAL / name) != checksum:
            raise ValueError('Changed initialization image: ' + name)
    ddr = audit_ddr(PARENT / 'source', variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('DDR5.9/300 original profile no longer intact')
    resolution = verified_evidence(PROOF / 'resolution.json')
    renames = verified_evidence(PROOF / 'geometry_rename_proof.json')
    review = verified_evidence(HERE / 'n57_builder_review.json')
    reset_aliases = verified_evidence(RESET_PROOF / 'result.json')
    if not renames['whole_module_equal_after_only_these_renames']:
        raise ValueError('Unexpected geometry synthesis differences')
    entries = {entry['label']: entry for entry in resolution['controls']}
    if set(entries) != set(CONTROLS):
        raise ValueError('Unexpected control inventory')
    for label, (net, count) in CONTROLS.items():
        entry = entries[label]
        if (entry['stages']['candidate']['proposed_routed_name'] != net or
                entry['global_load_count'] != count or
                not all(entry[key] for key in ('same_load_set', 'same_combinational_cone', 'same_global_connections')) or
                any(stage['clock_pin_count'] for stage in entry['stages'].values())):
            raise ValueError('Control resolution differs: ' + label)
    cst = (PARENT / 'source/tang/boards/neo/neo.cst').read_text()
    reset = resolution['reset4']
    if (not reset['unchanged'] or reset['stages']['candidate']['top_alias'] != 'gpu_debug_state[48]' or
            cst.count('CLOCK_LOC "gpu_debug_state[48]" LOCAL_CLOCK;') != 1):
        raise ValueError('Reset4 alias or existing constraint changed')
    control_fragment = ''.join(f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n' for net, _ in CONTROLS.values())
    if (PROOF / 'proposed_controls.cst').read_text() != control_fragment:
        raise ValueError('Unreviewed control fragment')
    for net, _ in CONTROLS.values():
        if re.search(r'CLOCK_LOC\s+"' + re.escape(net) + r'"', cst):
            raise ValueError('Refusing to override an existing control constraint: ' + net)
    aliases = reset_aliases['aliases']
    if [entry['index'] for entry in aliases] != list(range(12)):
        raise ValueError('Unexpected reset alias inventory')
    for entry in aliases:
        index = entry['index']
        internal, exported = f'u_accel/gpu_debug_state_{44 + index}', f'gpu_debug_state[{44 + index}]'
        existing = f'CLOCK_LOC "{exported}" LOCAL_CLOCK;'
        addition = f'CLOCK_LOC "{internal}" LOCAL_CLOCK;'
        if (entry['internal_alias'] != internal or entry['exported_alias'] != exported or
                entry['existing_constraint'] != existing or
                entry['proposed_additional_constraint'] != addition or
                entry['clock_pin_count'] != 0 or
                entry['driver'] != f'u_accel/engine_resetn_{index}_s0' or
                cst.splitlines().count(existing) != 1 or addition in cst):
            raise ValueError('Reset alias proof or existing constraint differs')
    alias_fragment = ''.join(entry['proposed_additional_constraint'] + '\n' for entry in aliases)
    if (RESET_PROOF / 'proposed_additions.cst').read_text() != alias_fragment:
        raise ValueError('Unreviewed reset alias fragment')
    # Preserve the rejected experiment and use only its explicitly reported
    # canonical equivalences; never discard unrelated constraints.
    parsed = json.loads((PARSER_PROOF / 'result.json').read_text())
    if (parsed['status'] != 'PARSER_REJECTED_DUPLICATE_CANONICAL_NETS' or
            parsed['exit_code'] != 1 or parsed['placement_started'] or
            parsed['failed_manifest_sha256'] != '76160fdf0a4dd030d79c4b9abb1b1b56bc987fe85a017f2daca150c9196035fd'):
        raise ValueError('Unexpected parser rejection evidence')
    for name, checksum in parsed['sha256'].items():
        if sha(Path(name)) != checksum:
            raise ValueError('Parser rejection evidence changed: ' + name)
    expected_duplicates = [dict(canonical_net='v1_pending',
        constraint='CLOCK_LOC "u_accel/v1_tx_addr_27_12" LOCAL_CLOCK;')]
    expected_duplicates += [dict(canonical_net=entry['exported_alias'],
        constraint=entry['proposed_additional_constraint']) for entry in aliases]
    if [{key: entry[key] for key in ('canonical_net', 'constraint')}
            for entry in parsed['entries']] != expected_duplicates:
        raise ValueError('Canonical alias resolution differs')
    fragment = ''.join(f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n'
        for label, (net, _) in CONTROLS.items() if label != 'pending_inverse')
    if (PARSER_PROOF / 'proposed_unique_controls.cst').read_text() != fragment:
        raise ValueError('Unreviewed canonical control fragment')
    candidate_cst = cst + '\n' + fragment
    parent_tcl = (PARENT / 'build.tcl').read_text()
    if parent_tcl.count('\nrun syn\n') != 1:
        raise ValueError('Expected synthesis-only parent')
    settings = [line.replace(str(PARENT), str(DEST)) for line in parent_tcl.splitlines()
                if line.startswith(('set_device ', 'set_option '))]
    for required in ('set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0',
                     'set_option -place_option 3', 'set_option -route_option 2',
                     'set_option -replicate_resources 0', 'set_option -clock_route_order 1'):
        if settings.count(required) != 1:
            raise ValueError('Unexpected PnR option: ' + required)
    tcl = '\n'.join(settings + [f'add_file {{{DEST / "console_neo.vg"}}}',
        f'add_file {{{DEST / "source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{DEST / "source/tang/boards/neo/neo.sdc"}}}', 'run pnr', ''])
    files = [Path(__file__), PARENT / 'sources.json', PARENT / 'build.tcl',
             PARENT / 'observer_build.json', PARENT / 'usb_synthesis_result.json',
             PARENT / 'usb_integration_manifest.json', PARENT / 'build.log', netlist,
             ORIGINAL / 'sources.json', PROOF / 'resolution.json',
             PROOF / 'geometry_rename_proof.json', PROOF / 'proposed_controls.cst',
             RESET_PROOF / 'result.json', RESET_PROOF / 'proposed_additions.cst',
             PARSER_PROOF / 'result.json', PARSER_PROOF / 'proposed_unique_controls.cst',
             HERE / 'audit_n57_controls.py', HERE / 'audit_geometry_controls.py',
             HERE / 'audit_gpu_control_inventory.py', HERE / 'prove_geometry_controls.py',
             HERE / 'n57_builder_review.json', ROOT / 'tools/board_contract.py',
             ROOT / 'tools/check_ddr_profile.py', ROOT / 'tools/gowin_toolchain.py',
             IDE / 'bin/gw_sh'] + [PARENT / name for name in INITIALIZATIONS]
    return dict(parent=str(PARENT), destination=str(DEST), source_manifest=sources,
        parent_netlist_sha256=NET_SHA, original_cst=cst, candidate_cst=candidate_cst,
        exact_added_lines=[line for line in fragment.splitlines() if line],
        preserved_reset4_constraint=True,
        preserved_reset_constraints=[entry['existing_constraint'] for entry in aliases],
        reset_aliases=[dict(index=entry['index'], internal_alias=entry['internal_alias'],
                           exported_alias=entry['exported_alias']) for entry in aliases],
        removed_duplicate_constraints=expected_duplicates,
        routed_control_constraint_count=8, audited_control_function_count=9,
        tcl=tcl, initializations_sha256=INITIALIZATIONS, ddr_profile=ddr,
        controls={label: dict(net=net, loads=count) for label, (net, count) in CONTROLS.items()},
        inputs_sha256={str(path): sha(path) for path in files},
        scope='PnR only: exact N57 netlist and SDC, eight canonical LOCAL_CLOCK additions; all existing reset constraints preserved',
        limitations=['Local constraints must be verified against post-route resources; exported resets have violated these constraints on earlier routes.',
                     'The new USB IPs and route are unqualified until timing, structural audits and board tests complete.',
                     'All DDR files, memory initializations, pin constraints, frequencies and route options remain unchanged.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare-only', action='store_true')
    modes.add_argument('--build-reviewed', metavar='MANIFEST_SHA256')
    args = parser.parse_args()
    record = inputs()
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        (PREPARED / 'neo.cst').write_text(record['candidate_cst'])
        (PREPARED / 'build.tcl').write_text(record['tcl'])
        (PREPARED / 'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True), record['candidate_cst'].splitlines(True),
            fromfile='N57_synthesis/neo.cst', tofile='N57_usb35_r1/neo.cst')))
        for name in ('resolution.json', 'geometry_rename_proof.json', 'geometry_renames.diff'):
            shutil.copy2(PROOF / name, PREPARED / name)
        for name in ('result.json', 'proposed_additions.cst'):
            shutil.copy2(RESET_PROOF / name, PREPARED / ('reset_aliases_' + name))
        for name in ('result.json', 'proposed_unique_controls.cst'):
            shutil.copy2(PARSER_PROOF / name, PREPARED / ('parser_' + name))
        shutil.copy2(HERE / 'audit_n57_controls.py', PREPARED / 'audit_n57_controls.py')
        record['prepared_sha256'] = {path.name: sha(path) for path in PREPARED.iterdir()}
        dump(PREPARED / 'manifest.json', record)
        print(json.dumps(dict(prepared=str(PREPARED),
            manifest_sha256=sha(PREPARED / 'manifest.json'),
            added=record['exact_added_lines'], compiler_invoked=False), indent=2))
        return
    if sha(PREPARED / 'manifest.json') != args.build_reviewed:
        raise ValueError('Reviewed manifest differs')
    expected = json.loads((PREPARED / 'manifest.json').read_text())
    prepared_hashes = expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation')
    for name, checksum in prepared_hashes.items():
        if sha(PREPARED / name) != checksum:
            raise ValueError('Prepared evidence changed: ' + name)
    DEST.mkdir(exist_ok=False)
    record_build(DEST, contract)
    shutil.copytree(PARENT / 'source', DEST / 'source')
    (DEST / 'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    shutil.copy2(PARENT / 'impl/gwsynthesis/console_neo.vg', DEST / 'console_neo.vg')
    for name, checksum in INITIALIZATIONS.items():
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT / name, target)
        if sha(target) != checksum:
            raise ValueError('Initialization copy differs: ' + name)
    sources = snapshot(DEST / 'source')
    if set(sources) != set(record['source_manifest']) or sorted(
            name for name in sources if sources[name] != record['source_manifest'][name]) != ['tang/boards/neo/neo.cst']:
        raise ValueError('Unexpected copied source change')
    dump(DEST / 'sources.json', sources)
    observer = json.loads((PARENT / 'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(DEST / 'sources.json'), routing_parent=str(PARENT),
                    routing_parent_observer_manifest_sha256=sha(PARENT / 'observer_build.json'))
    dump(DEST / 'observer_build.json', observer)
    dump(DEST / 'route.json', dict(parent=str(PARENT), netlist_sha256=NET_SHA,
                                 controls_manifest_sha256=args.build_reviewed))
    for path in PREPARED.iterdir():
        shutil.copy2(path, DEST / ('controls_' + path.name))
    (DEST / 'build.tcl').write_text(record['tcl'])
    if sha(DEST / 'console_neo.vg') != NET_SHA:
        raise ValueError('Copied netlist changed')
    with (DEST / 'build.log').open('w') as log:
        done = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=DEST,
            env=environment(), stdout=log, stderr=subprocess.STDOUT)
    if done.returncode or re.search(r'^ERROR', (DEST / 'build.log').read_text(), re.M):
        raise SystemExit('Routing failed')
    if (snapshot(DEST / 'source') != sources or sha(DEST / 'console_neo.vg') != NET_SHA or
            (DEST / 'build.tcl').read_text() != record['tcl'] or
            any(sha(DEST / name) != checksum for name, checksum in INITIALIZATIONS.items())):
        raise SystemExit('Inputs changed during routing')
    dump(DEST / 'route_result.json', dict(status='ROUTED_NOT_QUALIFIED',
        netlist_sha256=NET_SHA, source_manifest_sha256=sha(DEST / 'sources.json'),
        bitstream_sha256=sha(DEST / 'impl/pnr/console_neo.fs'), hardware_access=False))
    print(DEST)


if __name__ == '__main__':
    main()
