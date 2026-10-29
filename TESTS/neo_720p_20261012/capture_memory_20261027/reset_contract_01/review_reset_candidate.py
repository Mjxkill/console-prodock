#!/usr/bin/env python3
"""Independent structural review of a reset-only R21r1 netlist candidate.

Read-only apart from the explicitly named review output. No routing or board IO.
The helper's behavioral proof and physical qualification remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = ROOT / 'tang/impl/console_neo_n56r21r1_capture_memory'
PARENT_NET = '3f49d84ccb8b2001e5afa156b36849705652003fbf4e2a741847dc23f1713338'
sys.path.insert(0, str(HERE.parent))
import build_memory_capture as parse


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--coupled', action='store_true')
    args = ap.parse_args()
    build = args.build.resolve()
    assert build.is_relative_to(ROOT / 'tang/impl') and build != PARENT
    assert not args.out.exists()
    assert sha(PARENT / 'console_neo.vg') == PARENT_NET
    before = (PARENT / 'console_neo.vg').read_text()
    after = (build / 'console_neo.vg').read_text()
    module_names = lambda text: re.findall(r'^module (\w+)\b', text, re.M)
    old_names, new_names = module_names(before), module_names(after)
    assert len(old_names) == len(set(old_names))
    assert len(new_names) == len(set(new_names))
    assert set(old_names) == set(new_names)
    changed = [n for n in old_names if parse.block(before, n) != parse.block(after, n)]
    expected_modules = {'ae350_soc', 'neo_reset_trial'}
    if args.coupled:
        expected_modules.add('console_neo')
    assert set(changed) == expected_modules, changed
    old = parse.block(before, 'ae350_soc')
    new = parse.block(after, 'ae350_soc')
    oc, nc = parse.cells(old), parse.cells(new)
    assert not set(oc) - set(nc)
    addition = set(nc) - set(oc)
    assert len(addition) == 1, addition
    reset_gate = next(iter(addition))
    gate_type, gate_pins = nc[reset_gate]
    assert gate_type == 'LUT2' and set(gate_pins) == {'F', 'I0', 'I1'}
    assert set(gate_pins[p] for p in ('I0', 'I1')) == {'ae350_rst_sync[1]', 'trial_release'}
    clear_net = gate_pins['F']
    first, second = 'init_sync_0_s0', 'init_sync_1_s0'
    deltas = {name for name in oc if oc[name] != nc[name]}
    assert deltas == {first, second}, deltas
    for name in (first, second):
        kind, pins = oc[name]
        assert kind == 'DFFCE'
        assert pins['CLEAR'] == 'ae350_rst_sync[1]'
        assert pins['CLK'] == 'vid_hclk' and pins['CE'] == 'VCC'
        assert nc[name] == (kind, dict(pins, CLEAR=clear_net))
    assert oc[first][1]['D'] == 'trial_release'
    assert oc[second][1]['D'] == oc[first][1]['Q'] == 'init_sync[0]'
    assert oc[second][1]['Q'] == 'soc_dbg[0]'
    op, np = parse.params(old), parse.params(new)
    assert all(np.get(key) == value for key, value in op.items())
    assert op[first + '.INIT'] == op[second + '.INIT'] == "1'b0"
    assert set(np) - set(op) == {reset_gate + '.INIT'}
    init = re.fullmatch(r"4'h([0-9a-fA-F])", np[reset_gate + '.INIT'])
    assert init
    table = int(init[1], 16)
    truth = []
    for old_reset in (0, 1):
        for permission in (0, 1):
            inputs = {'ae350_rst_sync[1]': old_reset, 'trial_release': permission}
            index = inputs[gate_pins['I0']] + 2 * inputs[gate_pins['I1']]
            output = (table >> index) & 1
            assert output == (old_reset or not permission)
            truth.append([old_reset, permission, output])
    # Only the two reset pins may consume the new net. No hidden application tap.
    consumers = [(name, pin) for name, (_, pins) in nc.items()
                 for pin, net in pins.items() if net == clear_net and (name, pin) != (reset_gate, 'F')]
    assert sorted(consumers) == sorted([(first, 'CLEAR'), (second, 'CLEAR')])
    # Restrict the textual delta too: no changed assign statement or module port.
    restored = new
    cell_pattern = lambda name: r'^\s*\w+\s+' + re.escape(name) + r'\s*\([^;]*?\);'
    for name in (first, second):
        a = re.findall(cell_pattern(name), old, re.M | re.S)
        z = re.findall(cell_pattern(name), restored, re.M | re.S)
        assert len(a) == len(z) == 1
        restored = restored.replace(z[0], a[0], 1)
    restored, count = re.subn(cell_pattern(reset_gate), '', restored, flags=re.M | re.S)
    assert count == 1
    restored, count = re.subn(r'^\s*defparam\s+' + re.escape(reset_gate) + r'\.INIT\s*=\s*[^;]+;', '', restored, flags=re.M)
    assert count == 1
    restored, count = re.subn(r'^\s*wire\s+' + re.escape(clear_net) + r'\s*;', '', restored, flags=re.M)
    assert count == 1
    strip = lambda text: re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', text))
    assert strip(restored) == strip(old), 'Additional SoC text change outside reviewed reset cone'
    coupling = None
    if args.coupled:
        top_old, top_new = parse.block(before, 'console_neo'), parse.block(after, 'console_neo')
        tc, uc = parse.cells(top_old), parse.cells(top_new)
        assert not set(tc)-set(uc)
        extra = set(uc)-set(tc)
        assert len(extra) == 1
        gate = next(iter(extra))
        kind, pins = uc[gate]
        assert kind == 'LUT2' and set(pins) == {'F', 'I0', 'I1'}
        assert set(pins[p] for p in ('I0', 'I1')) == {'pll_ae350_lock', 'ae350_rst_sync[1]'}
        output_net = pins['F']
        assert {n for n in tc if tc[n] != uc[n]} == {'u_reset_trial'}
        assert tc['u_reset_trial'][1]['pll_ready'] == 'pll_ae350_lock'
        assert uc['u_reset_trial'] == (tc['u_reset_trial'][0], dict(tc['u_reset_trial'][1], pll_ready=output_net))
        tp, up = parse.params(top_old), parse.params(top_new)
        assert all(up.get(k) == v for k,v in tp.items())
        assert set(up)-set(tp) == {gate+'.INIT'}
        value = re.fullmatch(r"4'h([0-9a-fA-F])", up[gate+'.INIT'])
        assert value
        table = int(value[1],16)
        truth = []
        for locked in (0,1):
            for asserted in (0,1):
                ins = {'pll_ae350_lock':locked, 'ae350_rst_sync[1]':asserted}
                v = (table >> (ins[pins['I0']] + 2*ins[pins['I1']])) & 1
                assert v == (locked and not asserted)
                truth.append([locked,asserted,v])
        consumers = [(n,p) for n,(_,ps) in uc.items() for p,v in ps.items()
                     if v == output_net and (n,p) != (gate,'F')]
        assert consumers == [('u_reset_trial','pll_ready')]
        restored_top = top_new
        a = re.findall(cell_pattern('u_reset_trial'), top_old, re.M|re.S)
        z = re.findall(cell_pattern('u_reset_trial'), restored_top, re.M|re.S)
        assert len(a) == len(z) == 1
        restored_top = restored_top.replace(z[0],a[0],1)
        for pattern in (cell_pattern(gate),
                        r'^\s*defparam\s+'+re.escape(gate)+r'\.INIT\s*=\s*[^;]+;',
                        r'^\s*wire\s+'+re.escape(output_net)+r'\s*;'):
            restored_top,count = re.subn(pattern,'',restored_top,flags=re.M|re.S)
            assert count == 1
        assert strip(restored_top) == strip(top_old), 'Additional top change outside coupling cone'
        coupling = dict(gate=gate,truth_table_lock_reset_ready=truth,consumers=consumers,
                        unchanged_existing_top_cells=len(tc)-1,unchanged_top_parameters=len(tp))
    constraint_hashes = {}
    for filename in ('neo.cst', 'neo.sdc'):
        rel = Path('source/tang/boards/neo') / filename
        assert (build / rel).read_bytes() == (PARENT / rel).read_bytes()
        constraint_hashes[str(rel)] = sha(build / rel)
    assert (build / 'build.tcl').read_text().replace(str(build), str(PARENT)) == (PARENT / 'build.tcl').read_text()
    source_manifest = json.loads((build / 'sources.json').read_text())
    assert source_manifest == parse.manifest(build / 'source')
    parent_sources = json.loads((PARENT / 'sources.json').read_text())
    assert parent_sources == parse.manifest(PARENT / 'source')
    assert set(source_manifest) == set(parent_sources)
    source_changes = sorted(k for k in source_manifest if source_manifest[k] != parent_sources[k])
    assert source_changes == ['tang/boards/neo/console_neo.v', 'tang/boards/neo/neo_reset_trial.v']
    result = dict(passed=True, hardware_access=False, routing_authorized=False,
                  parent=str(PARENT), build=str(build), parent_netlist_sha256=PARENT_NET,
                  netlist_sha256=sha(build / 'console_neo.vg'),
                  source_manifest_sha256=sha(build / 'sources.json'),
                  changed_modules=changed, unchanged_module_count=len(old_names)-len(changed),
                  source_changes=source_changes, reset_gate=reset_gate,
                  truth_table_old_reset_permission_clear=[[0,0,1],[0,1,0],[1,0,1],[1,1,1]],
                  first_reset_coupling=coupling,
                  unchanged_existing_soc_cells=len(oc)-2,
                  unchanged_existing_soc_parameters=len(op),
                  constraints_identical=constraint_hashes, pnr_options_identical=True,
                  script_sha256=sha(Path(__file__)),
                  limits=['Structural reset-cone review only.',
                          'Helper simulation, CDC/reset timing, pulse width and hardware remain separate.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
