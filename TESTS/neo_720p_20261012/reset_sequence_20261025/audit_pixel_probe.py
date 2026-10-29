#!/usr/bin/env python3
"""Audit the single R16 observation build, retaining every failure separately."""
import json
from pathlib import Path
import re
from pixel_trace import HERE, BUILD, sha, audit_wrapper
import audit_routed as checks


def main():
    out = HERE / 'pixel_probe_postroute_01'
    assert not out.exists()
    parent = checks.BUILD
    route = json.loads((BUILD/'route_result.json').read_text())
    assert route['status'] == 'ROUTED_NOT_QUALIFIED' and route['returncode'] == 0
    result = dict(hardware_access=False, loaded=False, candidate=True,
                  qualification_status='PENDING', observation_input_audit_passed=False)
    out.mkdir()
    stable = [BUILD/n for n in ('console_neo.vg', 'sources.json', 'build.tcl',
        'observation_preparation.json', 'build.log', 'route_result.json',
        'impl/pnr/ao_0.fs', 'impl/pnr/console_neo.vo', 'impl/pnr/console_neo.tr',
        'impl/pnr/console_neo.sdf', 'impl/pnr/console_neo.rpt.txt', 'impl/pnr/cmd.do')]
    stable += [parent/'console_neo.vg', parent/'impl/pnr/console_neo.vo',
               Path(__file__), HERE/'pixel_trace.py', HERE/'audit_routed.py']
    try:
        result['input_sha256'] = {str(p):sha(p) for p in stable}
        result['wrapper'] = audit_wrapper()
        result['bitstream_sha256'] = sha(BUILD/'impl/pnr/ao_0.fs')
        result['identical_input_netlist'] = sha(BUILD/'console_neo.vg') == sha(parent/'console_neo.vg')
        result['identical_constraints'] = all(sha(BUILD/n) == sha(parent/n) for n in
            ('source/tang/boards/neo/neo.cst', 'source/tang/boards/neo/neo.sdc'))
        manifest = json.loads((BUILD/'sources.json').read_text())
        result['source_manifest_passed'] = manifest == {
            str(p.relative_to(BUILD/'source')):sha(p) for p in (BUILD/'source').rglob('*') if p.is_file()}
        header = (BUILD/'impl/pnr/ao_0.fs').read_text().splitlines()[:25]
        result['part_and_gao_id_passed'] = all(s in header for s in (
            '//Part Number: GW5AST-LV138PG484AC1/I0', '//GAOCRC: 0101011010110000'))
        old, op = checks.cells(parent/'impl/pnr/console_neo.vo')
        new, np = checks.cells(BUILD/'impl/pnr/console_neo.vo')
        result['application_cells'] = dict(parent=len(old), candidate=len(new),
            removed=sorted(old.keys()-new.keys()), added=sorted(new.keys()-old.keys()),
            changed={n:dict(before=old[n], after=new[n]) for n in old.keys() & new.keys() if old[n] != new[n]},
            parameters_changed={n:dict(before=op.get(n), after=np.get(n))
                                for n in op.keys() | np.keys() if op.get(n) != np.get(n)})
        app = result['application_cells']
        result['application_cells_identical'] = not any(app[k] for k in
            ('removed', 'added', 'changed', 'parameters_changed'))
        tr = (BUILD/'impl/pnr/console_neo.tr').read_text()
        result['timing'] = checks.timing_checks(tr)
        result['timing_summary'] = checks.inspect(BUILD, 'console_neo')
        constraints = re.findall(r'^\s*TC_\S+\s+(\S+)\s+(.+?)\s*$', tr, re.M)
        sdc = (BUILD/'source/tang/boards/neo/neo.sdc').read_text()
        expected = {' '.join(s.split()) for s in sdc.splitlines()
                    if s.startswith(('create_', 'set_', 'report_timing '))}
        result['active_constraints_passed'] = (bool(constraints) and
            all(state == 'Actived' for state, _ in constraints) and
            expected == {' '.join(c.split()) for _, c in constraints})
        routes = checks.global_clock_routes((BUILD/'impl/pnr/console_neo.rpt.txt').read_text())
        primary = json.loads((BUILD/'source/tang/boards/neo/timing_closure.json').read_text())['required_primary_clocks']
        result['global_routes'] = routes
        result['missing_primary'] = sorted(set(primary)-{n for n,k,_ in routes if k == 'PRIMARY'})
        result['reported_paths'] = checks.paths(tr)
        result['pixel_capture_paths'] = [r for r in result['reported_paths'] if
            any('/packet_' in r[k] or '/shader_command_' in r[k] for k in ('source', 'destination'))]
        vg, vo = BUILD/'console_neo.vg', BUILD/'impl/pnr/console_neo.vo'
        jobs = dict(copy=lambda:checks.audit_copy(vg), scanout=lambda:checks.audit_scanout(vg),
            owner=lambda:checks.audit_owner(vo), cpu_fifo=lambda:checks.audit_fifo(vg),
            closure=lambda:checks.audit_closure(BUILD/'source', BUILD/'impl/pnr/console_neo.tr'),
            resets=lambda:checks.audit_reset_tree(vg, BUILD/'impl/pnr/console_neo.rpt.txt', control_local=True),
            mask=lambda:checks.audit_mask(vg), mask_routed=lambda:checks.audit_mask(vo, routed=True),
            selector=lambda:checks.audit_selector(vg), selector_routed=lambda:checks.audit_selector(vo, routed=True),
            ddr_profile=lambda:checks.audit_ddr(BUILD/'source', 'neo-fifo-registers'))
        result['synthesis_audits'] = {}
        for name, job in jobs.items():
            try: result['synthesis_audits'][name] = job()
            except Exception as e: result['synthesis_audits'][name] = dict(passed=False, error=repr(e))
            print(name+': '+('PASS' if result['synthesis_audits'][name]['passed'] else 'FAIL'), flush=True)
        result['observation_input_audit_passed'] = all(result[k] for k in
            ('identical_input_netlist', 'identical_constraints', 'source_manifest_passed',
             'part_and_gao_id_passed', 'application_cells_identical', 'active_constraints_passed'))
        result['files_unchanged_during_audit'] = all(sha(Path(p)) == v for p,v in result['input_sha256'].items())
        result['observation_input_audit_passed'] &= result['files_unchanged_during_audit']
        timing_passed = all(v >= 0 for v in result['timing'].values())
        result['qualification_status'] = ('HARDWARE_PENDING' if timing_passed and
            result['observation_input_audit_passed'] and not result['missing_primary'] and
            all(a['passed'] for a in result['synthesis_audits'].values()) else 'FAIL')
    except BaseException as error:
        result.update(error=repr(error), qualification_status='FAIL')
        raise
    finally:
        result['limits'] = [
            'Instrument insertion changes physical placement, fanout and routes even with identical application cells.',
            'Public VO/SDF exclude encrypted GAO internals: uniform acquisition latency is not independently verified.',
            'Finite reported timing paths do not constitute full coverage of every D/CE/reset probe.',
            'A failed trace equation alone does not establish a physical cause; reproduce and corroborate the failure.',
            'The strict DDR source audit may reject the explicit R15 reset change; preserve this FAIL.']
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('observation_input_audit_passed', 'qualification_status',
            'timing', 'bitstream_sha256', 'error') if k in result}))


if __name__ == '__main__': main()
