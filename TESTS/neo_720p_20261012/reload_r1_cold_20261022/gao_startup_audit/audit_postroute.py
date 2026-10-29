#!/usr/bin/env python3
"""Audit completed R10 outputs without toolchain or hardware access.

The vendor VO/SDF exclude GAO internals. This audit records that limitation
instead of claiming all twenty physical capture bindings were inspected.
"""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from check_geometry_timing import inspect
from neo.timing import timing_checks
from prepare_metadata_proposal import BUILD, PARENT, complete, proposal, EXPECTED_AUDITS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    path = HERE / name
    with path.open('x') as out:
        if isinstance(data, str):
            out.write(data)
        else:
            json.dump(data, out, indent=2)
            out.write('\n')
    return sha(path)


def section(text, title):
    found = list(re.finditer(r'^\s*\d+\. ' + re.escape(title) + r'\s*$', text, re.M))
    assert len(found) == 1, title
    start = found[0].end()
    end = re.search(r'^\s*\d+\. ', text[start:], re.M)
    return text[start:start + end.start()] if end else text[start:]


def globals_table(text):
    return [dict(net=m[1].strip(), resource=m[2], location=m[3].strip()) for m in
        re.finditer(r'^\s*([^|\n]+?)\s*\|\s*(PRIMARY|LW|HCLK)\s*\|\s*([^\n]+)',
                    section(text, 'Global Clock Signals'), re.M)]


def detailed_paths(text):
    matches = list(re.finditer(r'Path Summary:\n', text))
    rows = []
    for i, match in enumerate(matches):
        body = text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)]
        def field(label):
            found = re.search(r'^' + re.escape(label) + r'\s*:\s*(.*?)\s*$', body, re.M)
            return found[1] if found else None
        src, dst = field('From'), field('To')
        if not any(n and n.startswith(('u_la0_top/', 'u_icon_top/')) for n in (src, dst)):
            continue
        # Compute line only for the small selected subset, not every path.
        rows.append(dict(source=src, destination=dst, slack_ns=float(field('Slack')),
            launch=field('Launch Clk'), latch=field('Latch Clk'),
            line=text.count('\n', 0, match.start())+1, text=body))
    return rows


def sdf_delta():
    a = PARENT / 'impl/pnr/console_neo.sdf'
    b = BUILD / 'impl/pnr/console_neo.sdf'
    pat = re.compile(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([\d.:]+)\)')
    differences = []
    for line, (before, after) in enumerate(itertools.zip_longest(a.open(), b.open()), 1):
        assert before is not None and after is not None, 'SDF line count changed'
        if before == after or before.startswith('//Created Time:'):
            continue
        old, new = pat.search(before), pat.search(after)
        assert old and new and old.groups()[:2] == new.groups()[:2], ('Non-route SDF delta', line)
        old_values, new_values = [list(map(float, m[3].split(':'))) for m in (old, new)]
        assert len(old_values) == len(new_values) == 3
        differences.append(dict(line=line, source=old[1].replace('\\', ''),
            destination=old[2].replace('\\', ''), before_ns=old_values, after_ns=new_values,
            delta_ns=[round(y-x, 3) for x, y in zip(old_values, new_values)]))
    groups = defaultdict(list)
    for row in differences:
        groups[row['source']].append(row)
    summary = {src: dict(changed_sinks=len(rows),
        min_delta_min_typ_max_ns=[min(r['delta_ns'][i] for r in rows) for i in range(3)],
        max_delta_min_typ_max_ns=[max(r['delta_ns'][i] for r in rows) for i in range(3)])
        for src, rows in groups.items()}
    return dict(changed_application_interconnects=len(differences), by_source=summary,
        cells_and_timingchecks_identical=True, application_net_endpoints_identical=True,
        gao_internals_present_in_SDF=False, differences=differences,
        scope='Reported interconnect delays; not path slack or proof of hardware startup')


def main():
    complete()
    metadata = proposal()
    assert json.loads((BUILD/'route.json').read_text()) == metadata
    stable = [BUILD/name for name in ('build.log', 'route_result.json', 'route.json',
        'qualification.json', 'bitstream_output_identity.json', 'sources.json', 'build.tcl',
        'impl/pnr/console_neo.vo', 'impl/pnr/console_neo.sdf', 'impl/pnr/console_neo.tr',
        'impl/pnr/console_neo.rpt.txt', 'impl/pnr/ao_0.fs', 'impl/pnr/ao_0.bin',
        'impl/pnr/ao_0.binx', 'impl/pnr/console_neo.fs', 'impl/pnr/cmd.do',
        'impl/pnr/console_neo.p', 'impl/pnr/console_neo.pr', 'impl/pnr/console_neo.db',
        'impl/gao/gao.v', 'source/tang/boards/neo/startup.gao')]
    stable += [PARENT/name for name in ('impl/pnr/console_neo.vo', 'impl/pnr/console_neo.sdf',
        'impl/pnr/console_neo.rpt.txt', 'impl/pnr/console_neo.tr', 'build.log', 'qualification.json')]
    stable += [HERE/'result.json', HERE/'expected_probe_bindings.json',
        HERE.parent/'route9_startup_analysis/r9.json',
        HERE.parent/'gao_cli_research/gao_manual.txt', ROOT/'tools/neo/timing_closure.py',
        Path(__file__).resolve()]
    hashes = {str(p): sha(p) for p in stable}
    assert sha(BUILD/'impl/pnr/ao_0.fs') == sha(BUILD/'impl/pnr/console_neo.fs') == \
        '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'
    fs_header = (BUILD/'impl/pnr/ao_0.fs').read_text().splitlines()[:25]
    assert '//GAOCRC: 0101011010100000' in fs_header
    assert '//Part Number: GW5AST-LV138PG484AC1/I0' in fs_header
    old_vo, vo = [(b/'impl/pnr/console_neo.vo').read_text() for b in (PARENT, BUILD)]
    old_body, body = [v[v.index('`timescale'):] for v in (old_vo, vo)]
    assert old_body == body, 'Application VO changed beyond header'
    assert 'u_la0_top/' not in body and 'u_icon_top/' not in body
    assert all('`pragma protect begin_protected' in (BUILD/'impl/pnr'/n).read_text()
               for n in ('console_neo.p', 'console_neo.pr'))
    pnr_command = (BUILD/'impl/pnr/cmd.do').read_text()
    assert f'-gao {BUILD}/impl/gao/gao.v\n' in pnr_command
    assert '-gao_crc 0101011010100000\n' in pnr_command
    tr = (BUILD/'impl/pnr/console_neo.tr').read_text()
    rpt = (BUILD/'impl/pnr/console_neo.rpt.txt').read_text()
    parent_rpt = (PARENT/'impl/pnr/console_neo.rpt.txt').read_text()
    table = re.search(r'^3\.1\.2 Hold Paths Table\n(.*?)^3\.1\.3 Recovery Paths Table',
                      tr, re.M | re.S)[1]
    hold_rows = []
    for line in table.splitlines():
        words = line.split()
        if len(words) != 9 or not words[0].isdecimal():
            continue
        if float(words[1]) >= 0:
            continue
        hold_rows.append(dict(rank=int(words[0]), slack_ns=float(words[1]), source=words[2],
            destination=words[3], launch=words[4], latch=words[5],
            relation_ns=float(words[6]), skew_ns=float(words[7]), data_delay_ns=float(words[8])))
    assert len(hold_rows) == 13
    assert all(r['launch'].startswith('tck_pad_i:') and r['latch'] == r['launch'] for r in hold_rows)
    paths = detailed_paths(tr)
    critical = []
    for row in hold_rows:
        candidates = [p for p in paths if p['source'] == row['source'].rsplit('/', 1)[0]
            and p['destination'] == row['destination'].rsplit('/', 1)[0]
            and p['slack_ns'] == row['slack_ns']]
        assert candidates, row
        critical.append(dict(**row, detailed_report_line=candidates[0]['line']))
    path_text = '\n'.join(p['text'] for p in paths if p['slack_ns'] < 0)
    path_sha = write('gao_hold_paths.txt', path_text)
    hold_sha = write('gao_hold_paths.json', dict(rows=critical, count=13,
        source_report_sha256=sha(BUILD/'impl/pnr/console_neo.tr'),
        minimum_ns=min(r['slack_ns'] for r in hold_rows), TNS_ns=-2.020,
        same_edge_paths=True, slowing_TCK_is_not_a_hold_fix=True,
        readable_path_extract_sha256=path_sha))
    capture = [p for p in paths if p['destination'] and
        ('data_reg_dly_' in p['destination'] or '/u_ao_match_0/trig_dly_in_' in p['destination'])]
    expected = json.loads((HERE/'expected_probe_bindings.json').read_text())
    checked = []
    for row in expected['probes'][:20]:
        destination = 'u_la0_top/u_ao_mem_ctrl/data_reg_dly_%d_s0' % row['data_i_bit']
        actual = [p for p in capture if p['destination'] == destination]
        for path in actual:
            assert path['source'] == row['application_driver']['instance'], row['net']
            assert path['latch'] == 'clk50:[R]' and 'clk_ibuf/O' in path['text']
            assert path['destination']+'/D' in path['text'] and path['destination']+'/CLK' in path['text']
        checked.append(dict(net=row['net'], generated_data_bit=row['data_i_bit'],
            original_driver_retained_in_public_VO=True, generated_GAO_connection_verified=True,
            physical_capture_path_visible_in_TR=bool(actual),
            report_lines=[p['line'] for p in actual]))
    trigger = [p for p in capture if p['destination'] == 'u_la0_top/u_ao_match_0/trig_dly_in_0_s0']
    assert len(trigger) == 1 and trigger[0]['source'] == expected['probes'][9]['application_driver']['instance']
    assert trigger[0]['latch'] == 'clk50:[R]' and 'clk_ibuf/O' in trigger[0]['text']
    assert sum(r['physical_capture_path_visible_in_TR'] for r in checked) == 5
    capture_sha = write('capture_path_witnesses.txt', '\n'.join(p['text'] for p in capture))
    old_globals, new_globals = [globals_table(t) for t in (parent_rpt, rpt)]
    assert old_globals == new_globals
    closure = json.loads((BUILD/'source/tang/boards/neo/timing_closure.json').read_text())
    required_primary = closure['required_primary_clocks']
    actual_primary = {g['net'] for g in new_globals if g['resource'] == 'PRIMARY'}
    assert set(required_primary) <= actual_primary
    warnings = [sorted(set(re.findall(r'^WARN.*PR1014.*$', (b/'build.log').read_text(), re.M)))
                for b in (PARENT, BUILD)]
    assert warnings[0] == warnings[1]
    delta = sdf_delta()
    assert delta['changed_application_interconnects'] == 5467
    delta_sha = write('application_sdf_delta.json', delta)
    q = json.loads((BUILD/'qualification.json').read_text())
    pq = json.loads((PARENT/'qualification.json').read_text())
    assert set(q['synthesis_audits']) == set(EXPECTED_AUDITS)
    assert q['status'] == 'FAIL' and q['timing_checks_ns'] == timing_checks(tr)
    assert q['bitstream_sha256'] == sha(BUILD/'impl/pnr/ao_0.fs')
    assert q['synthesis_audits']['timing_closure']['errors'] == [
        'Required primary clock not retained: '+n for n in required_primary]
    manual = (HERE.parent/'gao_cli_research/gao_manual.txt').read_text()
    assert 'internal registers in GAO IP driven by the rising edge of the TCK clock to be' in manual
    assert 'driven by the falling edge, which is used to improve the timing of the TCK' in manual
    # Hash checks close the observation interval; no candidate file is written.
    assert all(sha(Path(path)) == wanted for path, wanted in hashes.items())
    result = dict(audit_completed=True, structural_application_comparison_passed=True,
        qualification_status='FAIL', instrumentation_full_physical_audit_passed=False,
        hardware_access=False, build_or_inputs_modified=False, input_sha256=hashes,
        native_bitstream='impl/pnr/ao_0.fs', bitstream_sha256=sha(BUILD/'impl/pnr/ao_0.fs'),
        compatibility_bitstream_copy_exact=True, gao_id='0101011010100000',
        application_VO_body_identical_to_R9=True,
        application_VO_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        gao_primitives_excluded_from_public_VO_and_SDF=True,
        source_and_generated_GAO_verified_probes=20, public_TR_proven_capture_bits=5,
        trigger_ddr_init_path_proven=True, trigger_report_line=trigger[0]['line'],
        probe_bindings=checked, capture_path_witnesses_sha256=capture_sha,
        sample_clock=dict(net='clk_d', physical_source='clk_ibuf/O', timing_clock='clk50',
            configured_period_ns=20, independence_from_CPU_DDR_proven_on_visible_capture_paths=True,
            all_internal_clock_sinks_independently_verified=False, frequency_measured=False),
        globals_unchanged_from_R9=True, global_routes=new_globals,
        generic_clock_warning_set_unchanged=warnings[0],
        primary_clock_format_false_negative=dict(old_section=6, new_section=7,
            required=required_primary, independently_present=True,
            checker='tools/neo/timing_closure.py:133', qualification_rewritten=False),
        parent_timing_ns=pq['timing_checks_ns'], candidate_timing_ns=q['timing_checks_ns'],
        synthesis_audits={k:v['passed'] for k,v in q['synthesis_audits'].items()},
        GAO_routed_resources=dict(logic=567,LUT=552,ALU=15,registers=354,BSRAM=6),
        application_resource_summary=inspect(BUILD,'console_neo')['resources'],
        new_GAO_hold=dict(count=13,minimum_ns=-0.384,TNS_ns=-2.020,
            analysis_clock='tck_pad_i',frequency_MHz=20,details_sha256=hold_sha),
        sdf_changes=dict(changed_application_arcs=5467, details_sha256=delta_sha,
                         by_source=delta['by_source']),
        falling_edge_option=dict(current_value=False, documented_TCK_register_effect=True,
            source='SUG114-3.4.4E p24; gao_manual.txt:1039', verified_remedy=False,
            limitation='Affected registers are not enumerated; worst failing pair is already falling-edge to falling-edge. A separate rebuilt/routed candidate and full audits are required.'),
        limits=[
            'Five of twenty capture-bit physical paths plus the DDR trigger are exposed in the finite timing report; remaining physical endpoints cannot be independently reconstructed from the public VO/SDF.',
            'Public application VO equality preserves primitive pins/parameters/INIT, not physical route delay equality.',
            'The protected P/PR files and binary DB are not decrypted or guessed.',
            'SDF delay deltas are neither complete path slack nor evidence of a startup cause.',
            'GAO readout/command hold violations limit trust in a future capture until resolved or independently validated.',
            'No hardware capture or functional qualification is established.'])
    digest = write('postroute_result.json', result)
    print(json.dumps(dict(audit_completed=True, qualification='FAIL', physical_capture_bits_proven=5,
        trigger_proven=True, full_physical_instrumentation_audit=False, result_sha256=digest)))


if __name__ == '__main__':
    main()
