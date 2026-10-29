#!/usr/bin/env python3
"""Read completed R15 outputs. No hardware, toolchain, or candidate mutation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r15_reset50ms'
PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
OUT = HERE / 'postroute'
sys.path.insert(0, str(ROOT / 'tools'))
from check_geometry_timing import inspect
from neo.timing import timing_checks
from neo.timing_closure import global_clock_routes, audit as audit_closure
from check_gpu_copy_synthesis import audit as audit_copy
from check_gpu_scanout_synthesis import audit as audit_scanout
from check_neo_fifo_synthesis import audit as audit_fifo
from check_ddr_profile import audit as audit_ddr
from neo.gpu_replication import audit as audit_owner
from neo.gpu_reset import audit_reset_tree
from neo.pixel_mask import audit as audit_mask
from neo.pixel_selector import audit as audit_selector


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s):
    return re.sub(r'\s+', '', s).replace('\\', '')


def cells(p):
    s = p.read_text()
    found = {norm(n): [k, {pin: norm(v) for pin, v in
        re.findall(r'\.(\w+)\(([^()]*)\)', ports)}]
        for k, n, ports in re.findall(r'^(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);', s, re.M | re.S)
        if k != 'module'}
    params = {norm(n): norm(v) for n, v in
        re.findall(r'^defparam\s+(.+?)\s*=\s*([^;]+);', s, re.M)}
    return found, params


def paths(text):
    rows = []
    for m in re.finditer(r'Path Summary:\n(.*?)(?=Path Summary:|\Z)', text, re.S):
        block = m[1]
        def field(n):
            match = re.search(r'^' + re.escape(n) + r'\s*:\s*(.*?)\s*$', block, re.M)
            assert match, n
            return match[1]
        src, dst, slack = field('From'), field('To'), float(field('Slack'))
        helper = any(n.startswith('u_reset_trial/') for n in (src, dst))
        gao = any(n.startswith(('u_la0_top/', 'u_icon_top/', 'u_gw_jtag/')) for n in (src, dst))
        reset = any('init_sync' in n or 'vid_hrstn' in n for n in (src, dst))
        if helper or gao or reset or slack < 0:
            rows.append(dict(source=src, destination=dst, slack_ns=slack,
                launch=field('Launch Clk'), latch=field('Latch Clk'),
                helper=helper, gao=gao, reset=reset,
                line=text.count('\n', 0, m.start()) + 1))
    return rows


def main():
    route = json.loads((BUILD / 'route_result.json').read_text())
    assert route['status'] == 'ROUTED_NOT_QUALIFIED' and route['returncode'] == 0
    log = (BUILD / 'build.log').read_text()
    assert not re.search(r'^ERROR', log, re.M) and 'Bitstream generation completed' in log
    assembly = json.loads((BUILD / 'reset_assembly.json').read_text())
    for name, digest in assembly['inputs'].items():
        assert sha(BUILD / name) == digest, name
    manifest = json.loads((BUILD / 'sources.json').read_text())
    assert manifest == {str(p.relative_to(BUILD / 'source')): sha(p)
                        for p in (BUILD / 'source').rglob('*') if p.is_file()}
    stable = [BUILD / n for n in ['build.log', 'route_result.json', 'reset_assembly.json',
        'sources.json', 'console_neo.vg', 'impl/pnr/ao_0.fs', 'impl/pnr/console_neo.vo',
        'impl/pnr/console_neo.tr', 'impl/pnr/console_neo.sdf', 'impl/pnr/console_neo.rpt.txt',
        'impl/pnr/cmd.do', 'impl/gao/gw_gao_top.v', 'impl/gao/gao.v']]
    stable += [PARENT / 'impl/pnr/console_neo.vo', PARENT / 'impl/pnr/console_neo.tr', Path(__file__)]
    hashes = {str(p): sha(p) for p in stable}
    tr = (BUILD / 'impl/pnr/console_neo.tr').read_text()
    rpt = (BUILD / 'impl/pnr/console_neo.rpt.txt').read_text()
    header = (BUILD / 'impl/pnr/ao_0.fs').read_text().splitlines()[:25]
    assert '//Part Number: GW5AST-LV138PG484AC1/I0' in header
    assert '//GAOCRC: 0101011010101111' in header
    constraints = re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$', tr, re.M)
    sdc = (BUILD / 'source/tang/boards/neo/neo.sdc').read_text()
    expected = {' '.join(s.split()) for s in sdc.splitlines()
                if s.startswith(('create_', 'set_', 'report_timing '))}
    assert constraints and all(state == 'Actived' for state, _ in constraints)
    assert expected == {' '.join(c.split()) for _, c in constraints}

    old, old_params = cells(PARENT / 'impl/pnr/console_neo.vo')
    new, new_params = cells(BUILD / 'impl/pnr/console_neo.vo')
    assert not old.keys() - new.keys()
    changes = {n: dict(before=old[n], after=new[n]) for n in old if old[n] != new[n]}
    assert set(changes) == {'u_soc/init_sync_0_s0'}
    before, after = changes['u_soc/init_sync_0_s0'].values()
    assert before[0] == after[0] == 'DFFCE'
    assert before[1]['D'] == 'ddr_init' and after[1]['D'] == 'trial_request'
    assert {k:v for k,v in before[1].items() if k != 'D'} == {k:v for k,v in after[1].items() if k != 'D'}
    assert all(new_params.get(k) == v for k, v in old_params.items())
    additions = sorted(new.keys() - old.keys())
    assert additions and all(n.startswith('u_reset_trial/') for n in additions)
    witness = {n: v for n, v in new.items() if n.startswith('u_reset_trial/') and
               v[0].startswith('DFF') and v[1].get('Q') in ('trial_ahb_tick', 'trial_rtc_tick')}
    assert {v[1]['CLK'] for v in witness.values()} == {'vid_hclk', 'rtc_clk'}
    assert all(v[1].get('RESET') == 'GND' for v in witness.values())

    config = ET.parse(BUILD / 'source/tang/boards/neo/reset_trial.gao').getroot()
    core = config.find('AoCore')
    probes = [n.text for n in core.findall('SignalList/Signal')]
    assert probes == assembly['probes'] and len(probes) == 22
    assert core.get('sample_clock') == 'clk_d' and core.get('storage_depth') == '4096'
    wrapper = (BUILD / 'impl/gao/gw_gao_top.v').read_text()
    data = re.search(r'\.data_i\(\{([^}]+)\}\)', wrapper)[1]
    assert [norm(n) for n in data.split(',')] == probes
    assert '.trig0_i(trial_request)' in wrapper and '.clk_i(clk_d)' in wrapper
    rows = paths(tr)
    links = [p for p in rows if p['source'] == 'u_reset_trial/delay_done_s2'
             and p['destination'] == 'u_soc/init_sync_0_s0']
    assert links and all(p['slack_ns'] > 0 for p in links)
    bindings = [dict(net=n, bit=21-i,
        physical_report_witnesses=[r for r in rows if r['destination'] ==
            'u_la0_top/u_ao_mem_ctrl/data_reg_dly_%d_s0' % (21-i)]) for i,n in enumerate(probes)]
    routes = global_clock_routes(rpt)
    primary = json.loads((BUILD / 'source/tang/boards/neo/timing_closure.json').read_text())['required_primary_clocks']
    missing_primary = sorted(set(primary) - {n for n,k,_ in routes if k == 'PRIMARY'})
    vg, vo = BUILD / 'console_neo.vg', BUILD / 'impl/pnr/console_neo.vo'
    jobs = dict(copy=lambda:audit_copy(vg), scanout=lambda:audit_scanout(vg),
        gpu_owner_replication=lambda:audit_owner(vo), timing_closure=lambda:audit_closure(BUILD/'source',BUILD/'impl/pnr/console_neo.tr'),
        cpu_ddr_fifo_registers=lambda:audit_fifo(vg),
        gpu_reset_tree=lambda:audit_reset_tree(vg,BUILD/'impl/pnr/console_neo.rpt.txt',control_local=True),
        gpu_pixel_mask=lambda:audit_mask(vg), gpu_pixel_mask_routed=lambda:audit_mask(vo,routed=True),
        gpu_pixel_selector=lambda:audit_selector(vg), gpu_pixel_selector_routed=lambda:audit_selector(vo,routed=True),
        ddr_profile=lambda:audit_ddr(BUILD/'source','neo-fifo-registers'))
    audits = {}
    for name, job in jobs.items():
        try: audits[name] = job()
        except Exception as exc: audits[name] = dict(passed=False, exception=repr(exc))
        print(name + ': ' + ('PASS' if audits[name]['passed'] else 'FAIL'), flush=True)
    summary = inspect(BUILD, 'console_neo')
    timing = timing_checks(tr)
    assert all(sha(Path(p)) == digest for p,digest in hashes.items())
    result = dict(audit_completed=True, hardware_access=False, loaded=False,
        qualification_status='FAIL', startup_cause_demonstrated=False,
        bitstream_sha256=sha(BUILD/'impl/pnr/ao_0.fs'), input_sha256=hashes,
        timing=timing, timing_summary=summary, active_constraints=len(constraints),
        old_application_cells=len(old), added_cells=len(additions),
        all_original_application_cell_parameters_preserved=True,
        only_original_application_cell_change=changes, activity_witnesses=witness,
        required_primary=primary, missing_primary=missing_primary, global_routes=routes,
        delay_to_ahb_path=links, generated_gao_bindings=bindings,
        source_GAO_capture_bits=22, capture_depth=4096, sample_period_ns=20,
        report_paths=rows, synthesis_audits=audits,
        limits=['No hardware startup or repaired-reset proof.',
            'Public VO/SDF exclude protected GAO internals; finite timing witnesses do not cover all capture bindings.',
            'GAO TCK hold failures remain. Constant levels and chronology need independent interpretation.',
            'The original application logic is preserved except the first reset-flop D; physical delays changed.',
            'Structural DDR source audit can reject the explicit reset-input ECO; its result is preserved.',
            'Positive delay-to-AHB path is one reported CDC path, not full-design timing closure.',
            'Warm short/long comparisons differ from cold configuration; do not conflate them.'])
    OUT.mkdir(exist_ok=False)
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(qualification='FAIL', timing=timing, bitstream_sha256=result['bitstream_sha256'],
        routed_original_cell_changes=len(changes), added_cells=len(additions), missing_primary=missing_primary,
        delay_to_ahb_slack_ns=[p['slack_ns'] for p in links], result_sha256=sha(OUT/'result.json'))))


if __name__ == '__main__':
    main()
