#!/usr/bin/env python3
"""Recheck frozen startup comparison; no hardware, build or source mutation.

The JSON inputs preserve complete selected primitive pins/parameters and SDF
arcs. This script verifies their source hashes and independently reparses the
selected primitives. Its success is structural, never FPGA qualification.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from route_scan_timing_candidates import cells  # read-only parser
from prove_geometry_controls import parameters


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value):
    # Exact net aliases; the corresponding state FF and lock LUT pins/INIT
    # are separately compared, including the inverse lock driver below.
    if isinstance(value, str):
        return value.replace('state_145[', 'state_178[').replace(
            'soc_dbg_144[1]', 'soc_dbg_177[1]').replace('n3587_7', 'n4009_7')
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    return value


def main():
    result = dict(scope='Frozen startup structure and reported routes only',
                  hardware_access=False, hardware_cause_proven=False,
                  builds={}, input_sha256={})
    snapshots = {}
    ddr_selected = {}
    for label in ('n56r8', 'r2', 'r9'):
        snapshot_path = HERE / (label + '.json')
        data = json.loads(snapshot_path.read_text())
        build = Path(data['build'])
        for relative, wanted in data['identities'].items():
            path = build / relative
            assert sha(path) == wanted, path
            result['input_sha256'][str(path)] = wanted
        for relative in ('sources.json', 'build.log', 'impl/pnr/console_neo.tr',
                         'impl/pnr/console_neo.fs'):
            path = build / relative
            result['input_sha256'][str(path)] = sha(path)
        q = json.loads((build / 'qualification.json').read_text())
        assert q['status'] == 'FAIL'
        assert q['bitstream_sha256'] == sha(build / 'impl/pnr/console_neo.fs')
        assert q['timing_sha256'] == sha(build / 'impl/pnr/console_neo.tr')
        source_manifest = json.loads((build / 'sources.json').read_text())
        for relative, wanted in source_manifest.items():
            assert sha(build / 'source' / relative) == wanted, relative
        body = (build / 'impl/pnr/console_neo.vo').read_text()
        cc, pp = cells(body), parameters(body)
        for name, selected in data['selected'].items():
            assert cc[name] == selected['cell'], name
            assert pp.get(name, {}) == selected['parameters'], name
        lock_inverse = 'n3587_s2' if label == 'n56r8' else 'n4009_s2'
        inverse = dict(cell=cc[lock_inverse], parameters=pp[lock_inverse])
        assert normalize(inverse) == dict(cell=dict(kind='LUT4', pins=dict(
            I0='state_178[0]', I1='state_178[1]', I2='state_178[2]',
            I3='pll_lock', F='n4009_7')), parameters=dict(INIT="16'h7FFF"))
        assert cc['led_n_d_s0'] == dict(kind='LUT1', pins=dict(I0='ddr_init', F='led_n_d_4'))
        assert pp['led_n_d_s0'] == dict(INIT="2'h1")
        ddr_selected[label] = {n: dict(cell=c, parameters=pp.get(n, {})) for n, c in cc.items()
            if 'gw3_top/' in n and (any(t in n.rsplit('/', 1)[-1] for t in (
                'ddr_rsti_reg_', 'init_complete')) or c['kind'] in ('DDRDLL', 'CLKDIV'))}
        rpt = (build / 'impl/pnr/console_neo.rpt.txt').read_text()
        clock_resources = rpt.split('5. Clock Resource Usage Summary', 1)[1].split(
            '6. Global Clock Signals', 1)[0]
        resource_counts = dict(re.findall(r'^\s*(\w+)\s*\|\s*(\d+/\d+)\s*\|',
                                         clock_resources, re.M))
        globals_section = rpt.split('6. Global Clock Signals', 1)[1].split(
            '7. Pinout by Port Name', 1)[0]
        routes = {m[0]: dict(resource=m[1], location=m[2].strip()) for m in re.findall(
            r'^\s*(\S+)\s*\|\s*(PRIMARY|LW|HCLK)\s*\|\s*([^\n]+)',
            globals_section, re.M)}
        warnings = re.findall(r'^WARN\s+\(PR1014\).+$', (build / 'build.log').read_text(), re.M)
        wanted_sites = ('u_soc/init_sync_0_s0', 'u_soc/init_sync_1_s0',
            'ae350_rst_sync_1_s0', 'u_soc/vid_hrstn_r_s0', 'u_video_fast',
            'u_pll_ae350/u_pll/PLL_inst', 'u_soc/u_pll_ddr3/u_pll/PLL_inst')
        sites = {n: set() for n in wanted_sites}
        for location, node in re.findall(
                r'^\s*[-\d.]+\s+[-\d.]+\s+t\w+\s+\w+\s+\d+\s+(\S+)\s+(\S+)\s*$',
                (build / 'impl/pnr/console_neo.tr').read_text(), re.M):
            name = node.rsplit('/', 1)[0]
            if name in sites:
                sites[name].add(location)
        result['builds'][label] = dict(build=str(build), bitstream_sha256=q['bitstream_sha256'],
            qualification_status=q['status'], timing_ns=q['timing_checks_ns'],
            selected_primitives=len(data['selected']), clock_resources=resource_counts,
            global_routes=routes, generic_clock_warnings=warnings,
            reported_cell_sites={n: sorted(s) for n, s in sites.items()},
            inverse_lock=inverse, source_manifest=source_manifest)
        result['input_sha256'][str(snapshot_path)] = sha(snapshot_path)
        snapshots[label] = data
    assert snapshots['r2']['selected'] == snapshots['r9']['selected']
    assert normalize(snapshots['n56r8']['selected']) == snapshots['r9']['selected']
    assert ddr_selected['r2'] == ddr_selected['r9']
    assert ddr_selected['n56r8'] == ddr_selected['r9']
    result['ddr_reset_completion_primitives'] = ddr_selected
    result['ddr_reset_completion_primitives_exactly_identical'] = True
    result['selected_r2_r9_identical'] = True
    result['selected_n56r8_r9_identical_after_verified_aliases'] = True
    for label in ('n56r8', 'r2'):
        a = result['builds'][label]['source_manifest']
        b = result['builds']['r9']['source_manifest']
        result['builds'][label]['source_differences_to_r9'] = sorted(
            p for p in a.keys() | b.keys() if a.get(p) != b.get(p))
    assert result['builds']['r2']['source_differences_to_r9'] == [
        'tang/boards/neo/neo.cst', 'tang/boards/neo/timing_closure.json']
    for label in ('n56r8', 'r2'):
        assert result['builds'][label]['generic_clock_warnings'] == result['builds']['r9']['generic_clock_warnings']
    # Independent SDF extraction verifies every previously saved arc.
    sdf_path = HERE / 'startup_sdf.json'
    stored_sdf = json.loads(sdf_path.read_text())
    for label, rows in stored_sdf.items():
        build = Path(result['builds'][label]['build'])
        sdf = (build / 'impl/pnr/console_neo.sdf').read_text()
        arcs = {(s.replace('\\/', '/'), d.replace('\\/', '/')):
                tuple(map(float, v.split(':'))) for s, d, v in re.findall(
            r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([\d.:]+)\)', sdf)}
        for row in rows:
            assert arcs[(row['source'], row['destination'])] == (
                row['min_ns'], row['typ_ns'], row['max_ns']), row
        result['builds'][label]['ddr_internal_sdf_arcs'] = [dict(
            source=s, destination=d, min_ns=v[0], typ_ns=v[1], max_ns=v[2])
            for (s, d), v in arcs.items()
            if d.replace('\\.', '.').rsplit('/', 1)[0] in ddr_selected[label]]
    result['input_sha256'][str(sdf_path)] = sha(sdf_path)
    evidence = ['r9_route9_rgb_trial/result.json', 'r9_route9_rgb_trial/reset.log',
        'r9_route9_rgb_trial_100k/result.json', 'r9_route9_rgb_trial_100k/reset.log',
        'r9_route9_rgb_trial_100k/restored.log', 'r9_route2_reset_reloads/result.json']
    for relative in evidence:
        path = HERE.parent / relative
        result['input_sha256'][str(path)] = sha(path)
    for relative in ('TESTS/rtl/neo_reset_jtag.v', 'tools/neo/run_reset_probe.py'):
        path = ROOT / relative
        result['input_sha256'][str(path)] = sha(path)
    for path in (Path('/home/michael/Litex/openFPGALoader/src/gowin.cpp'),
                 Path('/home/michael/gowin/IDE/doc/EN/SUG283-3.6E_Gowin Primitives User Guide.pdf'),
                 Path('/home/michael/gowin/Gowin_V1.9.12_linux/Programmer/doc/ENG/UG704-1.0.4E_Arora Ⅴ 138K FPGA Product Programming and Configuration Guide.pdf')):
        result['input_sha256'][str(path)] = sha(path)
    result['input_sha256'][str(Path(__file__).resolve())] = sha(Path(__file__))
    result['verified'] = True
    result['limits'] = [
        'No measured PLL lock, DDR initialization, CPU reset or TMDS waveform under R9.',
        'Post-route equality and SDF delay comparisons do not prove reliable startup.',
        'All three qualification results remain FAIL.',
        'No boundary-scan opcode, pin-chain mapping or undocumented instruction is guessed.',
        'No synthesis, routing, hardware access or protected-file edit performed.']
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(verified=True, selected_primitives=263, hardware_cause_proven=False)))


if __name__ == '__main__':
    main()
