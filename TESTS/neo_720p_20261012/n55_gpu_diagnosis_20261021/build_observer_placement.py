#!/usr/bin/env python3
"""Prepare N56r4 from N56r3: seven regional placements, no RTL/SDC change.

Compilation is separate and requires the exact reviewed preparation manifest.
This constructor never accesses a board and never qualifies a build implicitly.
"""
import argparse
from collections import defaultdict
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_timing_placement import (
    HERE, ROOT, SHA_NET, SHA_SDC, IDE, environment, sha, dump,
    initial_values, before_build, record_build, audit_ddr,
)
from build_local_controls import cells

PARENT = ROOT/'tang/impl/console_neo_n56r3'
PREPARED = HERE/'n56r4_placement'
NAME = 'console_neo_n56r4'
SHA_BIT = '77a76cdc6d16aaa34a939296cc74ed7f6e29980682ac2756b6b2658ae443fbe2'
SHA_CST = '7fbd06897c96b3d291421c87cbf7f421bec3e1856c54fe3ca0979aaf914122ea'
CONTROLS = ('u_accel/u_v1/n56220_6', 'u_gpu_debug/n2835_5',
            'u_gpu_debug/mem_up[1]', 'u_accel/u_v1/n56864_3')
TARGETS = {
    'u_gpu_debug/observe_words_s1_57_s0': ('DFFRE', "1'b0", 'R[35:45]C[38:48]'),
    'u_gpu_debug/observe_words_s2_57_s0': ('DFFRE', "1'b0", 'R[35:45]C[38:48]'),
    'u_gpu_debug/observe_words_s1_49_s0': ('DFFRE', "1'b0", 'R[47:55]C[38:48]'),
    'u_gpu_debug/observe_words_s2_49_s0': ('DFFRE', "1'b0", 'R[47:55]C[38:48]'),
    'u_accel/engine_resetn_4_s0': ('DFFCE', "1'b0", 'R[18:30]C[45:60]'),
    'u_gpu_debug/held_48_s0': ('DFFRE', "1'b0", 'R[18:30]C[45:60]'),
    'u_gpu_debug/snapshot_48_s0': ('DFFRE', "1'b0", 'R[18:30]C[45:60]'),
}
ADDITION = '\n'+''.join(f'INS_LOC "{n}" {r};\n' for n, (_, _, r) in TARGETS.items())


def proof():
    vg = (PARENT/'console_neo.vg').read_text()
    vo = (PARENT/'impl/pnr/console_neo.vo').read_text()
    modules = {m[1]: m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule', vg, re.M|re.S)}
    mapped = {n: cells(body) for n, body in modules.items()}
    routed = cells(vo)
    inits = initial_values(vo)
    timing = (PARENT/'impl/pnr/console_neo.tr').read_text()
    setup = timing.split('\n3.3.1 Setup Analysis Report\n')[1].split('\n3.3.2 ')[0]
    paths = []
    for number, body in re.findall(r'\n\t+Path(\d+)\t+\n(.*?)(?=\n\t+Path\d+\t+\n|\Z)', setup, re.S):
        item = {k.lower(): re.search(r'^'+k+r'\s*:\s*(.+)$', body, re.M).group(1)
                for k in ('Slack', 'From', 'To')}
        item.update(number=int(number), slack=float(item['slack']), body=body)
        paths.append(item)
    negative = [p for p in paths if p['slack'] < 0]
    if len(paths) != 1000 or [p['slack'] for p in negative] != [-0.453, -0.278]:
        raise ValueError('Parent timing report differs')
    locations = {}
    for loc, node in re.findall(r'\b(R\d+C\d+\[\d+\]\[[AB]\])\s+(\S+)', timing):
        locations[node.rsplit('/', 1)[0]] = loc
    drivers, loads = defaultdict(list), defaultdict(list)
    for name, cell in routed.items():
        for pin, net in cell['pins'].items():
            (drivers if pin in ('Q', 'F', 'O', 'OF') else loads)[net].append(
                dict(instance=name, primitive=cell['kind'], pin=pin, reported_location=locations.get(name)))

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
                elif kind.startswith(('LUT', 'MUX')) or kind == 'INV':
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
        cell = mapped[module][parts[-1]]
        if cell['kind'] != kind or routed[name]['kind'] != kind:
            raise ValueError('Primitive differs: '+name)
        if initial_values(modules[module]).get(parts[-1]) != init or inits.get(name) != init:
            raise ValueError('INIT differs: '+name)
        adjacent = []
        for pin, net in routed[name]['pins'].items():
            if pin in ('Q', 'F'):
                adjacent.append(dict(pin=pin, net=net, direct_loads=loads[net], endpoints=endpoints(net)))
            elif pin not in ('CLK', 'CE', 'RESET', 'CLEAR'):
                adjacent.append(dict(pin=pin, net=net, direct_drivers=drivers[net]))
        entries.append(dict(instance=name, primitive=kind, init=init, region=region,
            reported_location=locations.get(name), mapped_module=module,
            mapped_pins=cell['pins'], routed_pins=routed[name]['pins'], adjacent=adjacent,
            reported_setup_paths=[{k:v for k,v in p.items() if k != 'body'}
                                  for p in paths if name+'/' in p['body']]))
    if not all(p['to'] in TARGETS for p in negative):
        raise ValueError('A negative endpoint is not covered')
    reset_net = 'gpu_debug_state[48]'
    reset_loads = loads[reset_net]
    if len(reset_loads) != 9 or [x['instance'] for x in reset_loads if x['pin']=='D'] != ['u_gpu_debug/held_48_s0']:
        raise ValueError('Reset4 observation load differs')
    if routed['u_gpu_debug/snapshot_48_s0']['pins']['D'] != routed['u_gpu_debug/held_48_s0']['pins']['Q']:
        raise ValueError('Reset4 snapshot connection differs')
    if locations['u_accel/engine_resetn_4_s0'] != 'R22C52[2][B]':
        raise ValueError('Reset4 driver moved in parent evidence')
    return dict(targets=entries, negative_paths=negative, negative_paths_covered=2,
        reset4_direct_loads=reset_loads, reset4_sequential_cone=endpoints(reset_net),
        reset4_lw_placement_hypothesis_only=True,
        reset4_observation_path=['u_gpu_debug/held_48_s0','u_gpu_debug/snapshot_48_s0'],
        reset4_driver_location_same_as_n56r1='R22C52[2][B]',
        paths_reported=1000, limitations=[
            'Held48/snapshot48 locations are absent from published paths; their distance is unknown.',
            'Regional placement does not guarantee that Gowin will stop promoting reset4 to LW.',
            'Held48 and snapshot48 form a held-data snapshot path, not a two-flop per-bit synchronizer.',
            'Observe_words bit48 observes pixel packet bit16, not reset4; it is not moved.',
            'Unknown locations and unreported paths are not passing timing results.',
            'Full timing/DDR/structural audits must pass after routing; no exception is changed.',
            'Viewport/near-Z and face CE nets remain outside this placement experiment.'])


def inputs():
    manifest = json.loads((PARENT/'sources.json').read_text())
    actual = {str(p.relative_to(PARENT/'source')):sha(p) for p in (PARENT/'source').rglob('*') if p.is_file()}
    if actual != manifest:
        raise ValueError('Parent source drift')
    if sha(PARENT/'console_neo.vg') != SHA_NET or sha(PARENT/'source/tang/boards/neo/neo.sdc') != SHA_SDC:
        raise ValueError('Parent netlist/SDC drift')
    cst = PARENT/'source/tang/boards/neo/neo.cst'
    if sha(cst) != SHA_CST:
        raise ValueError('Parent CST drift')
    q = json.loads((PARENT/'qualification.json').read_text())
    if q['bitstream_sha256'] != SHA_BIT or sha(PARENT/'impl/pnr/console_neo.fs') != SHA_BIT:
        raise ValueError('Parent bitstream drift')
    failures = {k:v.get('errors') for k,v in q['synthesis_audits'].items() if not v['passed']}
    if failures != {'gpu_reset_tree':['Reset 4 still uses a global routing resource']}:
        raise ValueError('Unexpected parent audit failures')
    controls = json.loads((PARENT/'local_controls_audit.json').read_text())
    if not controls['passed'] or not controls['same_synthesis_netlist']:
        raise ValueError('Parent local-control proof failed')
    for name, expected in controls['checks_sha256'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Changed local-control evidence: '+name)
    ddr = audit_ddr(PARENT/'source', variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('Parent DDR drift')
    original = cst.read_text()
    for net in (*CONTROLS, 'gpu_debug_state[48]'):
        if original.count(f'CLOCK_LOC "{net}" LOCAL_CLOCK;') != 1:
            raise ValueError('Required LOCAL_CLOCK differs: '+net)
    if any(re.search(r'INS_LOC\s+"'+re.escape(n)+'"', original) for n in TARGETS):
        raise ValueError('Would override an existing placement')
    paths = [PARENT/p for p in ('sources.json','console_neo.vg','build.tcl','qualification.json',
        'observer_build.json','local_controls_audit.json','impl/pnr/console_neo.vo',
        'impl/pnr/console_neo.tr','impl/pnr/console_neo.rpt.txt',
        'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc',
        'font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex')]
    paths += [Path(__file__),HERE/'build_timing_placement.py',HERE/'build_local_controls.py',IDE/'bin/gw_sh']
    return dict(parent=str(PARENT),name=NAME,hardware_access=False,synthesis=False,
        parent_bitstream_sha256=SHA_BIT,parent_inputs_sha256={str(p):sha(p) for p in paths},
        source_manifest=manifest,original_cst=original,candidate_cst=original+ADDITION,
        exact_added_lines=ADDITION.strip().splitlines(),unchanged_local_controls=list(CONTROLS),
        changed_source_files=['tang/boards/neo/neo.cst'],ddr_profile=ddr,
        compiler=str(IDE/'bin/gw_sh'),parent_qualification='FAIL: two observer CDC paths and reset4 LW',
        experiment='regional_observer_pairs_and_reset4_snapshot_cluster')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only',action='store_true')
    mode.add_argument('--build-reviewed',metavar='MANIFEST_SHA256')
    a = p.parse_args()
    record = inputs()
    contract = before_build('neo',candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if a.prepare_only:
        evidence = proof()
        PREPARED.mkdir(exist_ok=False)
        (PREPARED/'neo.cst').write_text(record['candidate_cst'])
        (PREPARED/'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True),record['candidate_cst'].splitlines(True),
            fromfile='N56r3/neo.cst',tofile='N56r4/neo.cst')))
        dump(PREPARED/'placement_proof.json',evidence)
        record['prepared_sha256']={x.name:sha(x) for x in PREPARED.iterdir()}
        dump(PREPARED/'manifest.json',record)
        print(json.dumps(dict(prepared=str(PREPARED),manifest_sha256=sha(PREPARED/'manifest.json'),
                              added=record['exact_added_lines']),indent=2))
        return
    if sha(PREPARED/'manifest.json') != a.build_reviewed:
        raise ValueError('Different preparation manifest: review required')
    expected=json.loads((PREPARED/'manifest.json').read_text())
    prepared_hashes=expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation: review required')
    for name,checksum in prepared_hashes.items():
        if sha(PREPARED/name) != checksum:
            raise ValueError('Prepared evidence changed: '+name)
    out=ROOT/'tang/impl'/NAME
    out.mkdir(exist_ok=False)
    record_build(out,contract)
    shutil.copytree(PARENT/'source',out/'source')
    (out/'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    shutil.copy2(PARENT/'console_neo.vg',out/'console_neo.vg')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/name,target)
    updated={str(x.relative_to(out/'source')):sha(x) for x in (out/'source').rglob('*') if x.is_file()}
    old=record['source_manifest']
    if set(updated)!=set(old) or sorted(k for k in updated if updated[k]!=old[k])!=record['changed_source_files']:
        raise ValueError('Unexpected source mutation')
    dump(out/'sources.json',updated)
    observer=json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(out/'sources.json'),routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT/'observer_build.json'))
    dump(out/'observer_build.json',observer)
    dump(out/'route.json',dict(parent=str(PARENT),netlist_sha256=SHA_NET,
        observer_placement_manifest_sha256=a.build_reviewed))
    for name in ('manifest.json','placement_proof.json','constraints.diff'):
        shutil.copy2(PREPARED/name,out/('placement_'+name))
    shutil.copy2(PARENT/'local_controls_audit.json',out/'parent_local_controls_audit.json')
    settings=[line.replace(str(PARENT),str(out)) for line in (PARENT/'build.tcl').read_text().splitlines()
              if line.startswith(('set_device ','set_option '))]
    (out/'build.tcl').write_text('\n'.join(settings+[
        f'add_file {{{out/"console_neo.vg"}}}',f'add_file {{{out/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out/"source/tang/boards/neo/neo.sdc"}}}','run pnr','']))
    with (out/'build.log').open('w') as log:
        done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
                            stdout=log,stderr=subprocess.STDOUT)
    if done.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):
        raise SystemExit('Routing failed')
    print(out)


if __name__ == '__main__':
    main()
