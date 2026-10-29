#!/usr/bin/env python3
"""Read only completed R14 outputs. Write evidence only beside this script."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
COLD = HERE.parent
ROOT = COLD.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r14_gao_tck_cst_seeded'
PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
sys.path.insert(0, str(ROOT / 'tools'))
from check_geometry_timing import inspect
from neo.timing import timing_checks
from neo.timing_closure import global_clock_routes, sections, audit as audit_closure
from check_gpu_copy_synthesis import audit as audit_copy
from check_gpu_scanout_synthesis import audit as audit_scanout
from check_neo_fifo_synthesis import audit as audit_fifo
from check_ddr_profile import audit as audit_ddr, SELECTION
from neo.gpu_replication import audit as audit_owner
from neo.gpu_reset import audit_reset_tree
from neo.pixel_mask import audit as audit_mask
from neo.pixel_selector import audit as audit_selector


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    with (HERE / name).open('x') as out:
        if isinstance(value, str):
            out.write(value)
        else:
            json.dump(value, out, indent=2)
            out.write('\n')


def section(text, title):
    hits = list(re.finditer(r'^\s*\d+\. ' + re.escape(title) + r'\s*$', text, re.M))
    assert len(hits) == 1, title
    start = hits[0].end()
    end = re.search(r'^\s*\d+\. ', text[start:], re.M)
    assert end, 'Truncated ' + title
    return text[start:start + end.start()]


def field(block, label):
    hit = re.search(r'^' + re.escape(label) + r'\s*:\s*(.*?)\s*$', block, re.M)
    assert hit, label
    return hit[1]


def paths(text):
    rows = []
    for kind, blocks in sections(text):
        for block in blocks:
            src, dst = field(block, 'From'), field(block, 'To')
            slack = float(field(block, 'Slack'))
            is_gao = src.startswith(('u_la0_top/', 'u_icon_top/', 'u_gw_jtag/')) or dst.startswith(('u_la0_top/', 'u_icon_top/'))
            if slack < 0 or is_gao:
                rows.append(dict(kind=kind, source=src, destination=dst, slack_ns=slack,
                    launch=field(block, 'Launch Clk'), latch=field(block, 'Latch Clk'),
                    gao=is_gao, text='Path Summary:' + block))
    return rows


def main():
    # Do not even parse in-progress reports. The wrapper writes this last,
    # after its owned gw_sh exits and prepared inputs are rechecked.
    result_path = BUILD / 'route_result.json'
    if not result_path.exists():
        print(json.dumps(dict(status='WAITING_FOR_ROUTE_RESULT', outputs_read=False)))
        return
    route_result = json.loads(result_path.read_text())
    log = (BUILD / 'build.log').read_text()
    errors = [dict(offset=m.start(), context=log[max(0,m.start()-80):m.start()+420])
              for m in re.finditer('ERROR', log)]
    complete = (route_result.get('returncode') == 0 and
        route_result.get('status') == 'ROUTED_NOT_QUALIFIED' and
        'Bitstream generation completed' in log and
        f'Generate file "{BUILD}/impl/pnr/console_neo.tr" completed' in log)
    preliminary = dict(route_result=route_result, ERROR_anywhere=errors,
        completion_markers_present=complete, log_sha256=sha(BUILD/'build.log'),
        route_result_sha256=sha(result_path), hardware_access=False)
    if not complete:
        write('incomplete_or_failed.json', preliminary)
        print(json.dumps(dict(status='BUILD_NOT_COMPLETE', **preliminary)))
        return
    builder_path = COLD / 'prepare_gao_backend_seeded.py'
    assert sha(builder_path) == '8ad0203355c5494a53035113564253d525eff612aadfddc87abb403f4d37a907'
    spec = importlib.util.spec_from_file_location('r14_frozen_builder', builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    prepared = builder.verify_prepared(*builder.parent_preflight())
    assert route_result['prepared_sha256'] == sha(BUILD/'backend_prepared.json')
    assert route_result['log_sha256'] == sha(BUILD/'build.log')
    native = BUILD / 'impl/pnr/ao_0.fs'
    output_names = ['console_neo.tr','console_neo.rpt.txt','console_neo.vo','console_neo.sdf',
                    'console_neo.p','console_neo.pr','console_neo.db','ao_0.fs','ao_0.bin','ao_0.binx']
    outputs = [BUILD/'impl/pnr'/name for name in output_names]
    assert all(p.is_file() and p.stat().st_size > 0 for p in outputs), 'Missing output'
    stable = outputs + [BUILD/name for name in ('build.log','route_result.json',
        'route.json','backend_prepared.json','backend_args_result.json','backend_args.log',
        'sources.json','console_neo.vg','impl/gao/gao.v','impl/pnr/cmd.do')]
    stable += [PARENT/'impl/pnr'/n for n in ('console_neo.tr','console_neo.rpt.txt','console_neo.vo')]
    stable += [COLD/'gao_startup_audit'/n for n in ('result.json','expected_probe_bindings.json')]
    stable += [builder_path, Path(__file__)]
    hashes = {str(p):sha(p) for p in stable}
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name and Path(name).is_file() and Path(name).resolve().is_relative_to(ROOT/'tools'):
            hashes[str(Path(name).resolve())]=sha(Path(name))
    header = native.read_text().splitlines()[:25]
    assert '//GAOCRC: 0101011010100000' in header
    assert '//Part Number: GW5AST-LV138PG484AC1/I0' in header
    tr_path = BUILD/'impl/pnr/console_neo.tr'
    tr, rpt = tr_path.read_text(), (BUILD/'impl/pnr/console_neo.rpt.txt').read_text()
    old_tr = (PARENT/'impl/pnr/console_neo.tr').read_text()
    old_rpt = (PARENT/'impl/pnr/console_neo.rpt.txt').read_text()
    assert '<Part Number>: GW5AST-LV138PG484AC1/I0' in tr
    constraints = re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$', tr, re.M)
    sdc = (BUILD/'source/tang/boards/neo/neo.sdc').read_text()
    normalize = lambda s:' '.join(s.split())
    expected = {normalize(s) for s in sdc.splitlines() if s.startswith(('create_', 'set_', 'report_timing '))}
    assert constraints and all(state == 'Actived' for state, _ in constraints)
    assert expected == {normalize(c) for _, c in constraints}, 'Incomplete frozen SDC'
    frequencies = dict(clk50=50,bus80_clk=80,core_clk=800,rtc_clk=10,
        ddr3_mem_clk=300,ddr3_sys_clk=75,vid_pclk=74.375,vid_clk5x=371.875,
        CLK_48M=48,PHY_CLKOUT=60,fclk_960M=960,sclk=120,tck_pad_i=20)
    actual_freq = {}
    for clock, wanted in frequencies.items():
        hit = re.search(r'^\s*\d+\s+'+re.escape(clock)+r'\s+(?:Base|Generated)\s+[\d.]+\s+([\d.]+)MHz',tr,re.M)
        assert hit and abs(float(hit[1])-wanted)<.051, 'Wrong/missing clock '+clock
        actual_freq[clock]=float(hit[1])
    # Command is compared in full to R10 plus exactly -gao_cst by the pinned
    # builder. This retains place/route/replication/cst_error and all options.
    assert (BUILD/'impl/pnr/cmd.do').read_text() == builder.expected_command()
    route = json.loads((BUILD/'route.json').read_text())
    vg, vo = BUILD/'console_neo.vg', BUILD/'impl/pnr/console_neo.vo'
    source = BUILD/'source'
    audit_jobs = {
        'copy':lambda:audit_copy(vg), 'scanout':lambda:audit_scanout(vg),
        'gpu_owner_replication':lambda:audit_owner(vo),
        'timing_closure':lambda:audit_closure(source,tr_path),
        'cpu_ddr_fifo_registers':lambda:audit_fifo(vg),
        'gpu_reset_tree':lambda:audit_reset_tree(vg,BUILD/'impl/pnr/console_neo.rpt.txt',
            control_local='gpu_debug_state[43]' in (source/'tang/boards/neo/neo.cst').read_text()),
        'gpu_pixel_mask':lambda:audit_mask(vg), 'gpu_pixel_mask_routed':lambda:audit_mask(vo,routed=True),
        'gpu_pixel_selector':lambda:audit_selector(vg), 'gpu_pixel_selector_routed':lambda:audit_selector(vo,routed=True)}
    assert set(audit_jobs) == set(route['required_qualification_audits'])
    assert route['optional_audit_selectors_present'] == [] and not route['wide_gpu_controls_catalog_present']
    audits = {}
    for name, fn in audit_jobs.items():
        try:
            audits[name] = fn()
        except Exception as exc:
            audits[name] = dict(passed=False,exception=repr(exc))
        print(name + ': ' + ('PASS' if audits[name]['passed'] else 'FAIL'), flush=True)
    select_path = source/SELECTION
    variant = json.loads(select_path.read_text())['variant'] if select_path.exists() else 'prodock'
    ddr = audit_ddr(source,variant,system_reset=(source/'tang/boards/neo/system_reset.json').exists(),
                    ddr_startup=(source/'tang/boards/neo/ddr_startup.json').exists())
    assert ddr['passed'], 'DDR profile differs'
    summary = inspect(BUILD,'console_neo')
    checks = timing_checks(tr)
    assert summary['minimum_pulse_slack_ns'] is not None
    routes = global_clock_routes(rpt)
    old_routes = global_clock_routes(old_rpt)
    closure = json.loads((source/'tang/boards/neo/timing_closure.json').read_text())
    required_primary = closure['required_primary_clocks']
    assert len(required_primary) == 8
    missing_primary = sorted(set(required_primary)-{net for net,kind,_ in routes if kind=='PRIMARY'})
    selected_paths = paths(tr)
    gao_paths = [p for p in selected_paths if p['gao']]
    negative = [p for p in selected_paths if p['slack_ns']<0]
    old_gao_hold = [p for p in paths(old_tr) if p['gao'] and p['kind']=='hold' and p['slack_ns']<0]
    assert len(old_gao_hold)==13, 'Parent comparison differs from audited R10'
    hold_comparison=[]
    for old in old_gao_hold:
        current=[p for p in gao_paths if all(p[k]==old[k] for k in
                 ('kind','source','destination','launch','latch'))]
        hold_comparison.append(dict(source=old['source'],destination=old['destination'],
            launch=old['launch'],latch=old['latch'],R10_slack_ns=old['slack_ns'],
            R14_reported_slack_ns=min(p['slack_ns'] for p in current) if current else None,
            note='Not present in finite report is not a per-path pass' if not current else None))
    tck_rows=sorted({line.strip() for p in gao_paths for line in p['text'].splitlines()
                    if 'u_gw_jtag/tck_o' in line or 'tck_pad_i' in line})
    write('tck_clock_path_rows.txt','\n'.join(tck_rows)+'\n')
    write('negative_paths.txt','\n'.join(p['text'] for p in negative))
    write('gao_paths.txt','\n'.join(p['text'] for p in gao_paths))
    expected_probes = json.loads((COLD/'gao_startup_audit/expected_probe_bindings.json').read_text())
    checked = []
    for probe in expected_probes['probes'][:20]:
        target = 'u_la0_top/u_ao_mem_ctrl/data_reg_dly_%d_s0' % probe['data_i_bit']
        witnesses = [p for p in gao_paths if p['destination']==target]
        for witness in witnesses:
            assert witness['source']==probe['application_driver']['instance']
            assert witness['latch']=='clk50:[R]' and 'clk_ibuf/O' in witness['text']
        checked.append(dict(net=probe['net'],data_bit=probe['data_i_bit'],physical_path_visible=bool(witnesses)))
    trigger = [p for p in gao_paths if p['destination']=='u_la0_top/u_ao_match_0/trig_dly_in_0_s0']
    for p in trigger:
        assert p['source']==expected_probes['probes'][9]['application_driver']['instance']
        assert p['latch']=='clk50:[R]' and 'clk_ibuf/O' in p['text']
    public_vo = vo.read_text()
    old_vo = (PARENT/'impl/pnr/console_neo.vo').read_text()
    vo_equal = public_vo[public_vo.index('`timescale'):]==old_vo[old_vo.index('`timescale'):]
    gao_hidden = 'u_la0_top/' not in public_vo and 'u_icon_top/' not in public_vo
    gao_resource = section(rpt,'GAO Resource Usage Summary')
    clock_resource = section(rpt,'Clock Resource Usage Summary')
    write('resource_tables.txt',gao_resource+'\n'+clock_resource+'\n'+section(rpt,'Global Clock Signals'))
    # All generated GAO sources are already in the prepared immutable manifest;
    # compare them to the previously audited R10, not just its top-level wrapper.
    inherited = json.loads((COLD/'gao_startup_audit/result.json').read_text())
    for name,digest in inherited['input_sha256'].items():
        p=Path(name)
        if p.is_relative_to(PARENT/'impl/gao'):
            assert sha(BUILD/p.relative_to(PARENT))==digest
    assert sha(source/'tang/boards/neo/startup.gao')==sha(PARENT/'source/tang/boards/neo/startup.gao')
    metadata = {k:v for k,v in inherited.items() if k in ('sample_clock','trigger','capture','generated_capture_input_connections')}
    assert all(sha(Path(p))==digest for p,digest in hashes.items()), 'Output/input changed during audit'
    builder.verify_prepared(*builder.parent_preflight())
    static_pass = (not errors and summary['status']=='PASS' and min(checks.values())>=0
        and not missing_primary and all(a['passed'] for a in audits.values()) and vo_equal)
    clean_rows = lambda rows:[{k:v for k,v in p.items() if k!='text'} for p in rows]
    result = dict(audit_completed=True,static_qualification_status='PASS' if static_pass else 'FAIL',
        hardware_access=False,startup_fix_proven=False,candidate_or_inputs_modified=False,
        experiment_purpose='GAO instrumentation TCK distribution and timing audit',
        GAO_hold_to_AE350_reset_causality_proven=False,
        successful_boot_after_reroute_would_establish_causality=False,
        input_sha256=hashes,bitstream_sha256=sha(native),native_bitstream=str(native),
        completion=preliminary,prepared_manifest_sha256=sha(BUILD/'backend_prepared.json'),
        timing_summary=summary,timing_checks_ns=checks,parent_timing_checks_ns=timing_checks(old_tr),
        clock_mhz=actual_freq,active_timing_constraints=len(constraints),ddr_profile=ddr,
        synthesis_audits=audits,required_primary_clocks=required_primary,missing_primary=missing_primary,
        global_routes=routes,parent_global_routes=old_routes,
        added_global_routes=[r for r in routes if r not in old_routes],
        removed_global_routes=[r for r in old_routes if r not in routes],
        GAO_resource_report=gao_resource,clock_resource_report=clock_resource,
        application_public_VO_body_unchanged=vo_equal,gao_hidden_in_public_VO=gao_hidden,
        generated_GAO_configuration=metadata,probe_bindings=checked,
        visible_probe_count=sum(p['physical_path_visible'] for p in checked),trigger_path_visible=bool(trigger),
        negative_paths=clean_rows(negative),gao_paths=clean_rows(gao_paths),
        parent_13_GAO_hold_comparison=hold_comparison,
        TCK_clock_path_rows=tck_rows,
        full_physical_GAO_binding_audit_proven=all(p['physical_path_visible'] for p in checked),
        limits=['No hardware test or proof of repaired startup.',
            'R14 targets GAO instrumentation; no causal link from its hold violations to AE350 reset is established.',
            'Even successful startup after rerouting would not by itself establish that causal link.',
            'CST acceptance is distinct from actual global routing and its measured timing.',
            'Public routed VO/SDF may omit protected GAO internals; unseen bindings remain unproven.',
            'Finite reported paths do not enumerate every routed GAO clock sink.',
            'This independent audit calls all ten inherited audit functions without writing qualification.json.',
            'No placeholder build.tcl or renamed bitstream was installed in the frozen backend candidate.'])
    write('result.json',result)
    print(json.dumps(dict(status=result['static_qualification_status'],timing=checks,
        result_sha256=sha(HERE/'result.json'),bitstream_sha256=sha(native))))


if __name__=='__main__':
    main()
