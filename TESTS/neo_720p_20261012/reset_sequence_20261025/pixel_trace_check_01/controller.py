#!/usr/bin/env python3
"""Check trace decoding against exact mapped simulation and injected trace faults."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
from pixel_trace import HERE, mapping, parse_csv, analyze, sha, audit_wrapper


def main():
    out = HERE / 'pixel_trace_check_01'
    out.mkdir(exist_ok=False)
    old = HERE / 'command_mapped_02'
    proof = json.loads((old/'result.json').read_text())
    assert proof['passed']
    for name in ('tb.sv', 'mapped.v', 'primitives.v'):
        assert sha(old/name) == proof['inputs'][str(old/name)]
    for name in ('mapped.v', 'primitives.v'):
        shutil.copy2(old/name, out/name)
    m = mapping()
    expr = {}
    for bit, name in m['geometry_header'].items(): expr[name] = f'geometry_header[{bit}]'
    for bit, name in m['pixel_Q'].items(): expr[name] = f'pixel_header[{bit}]'
    for name in m['actual_pixel_D'].values(): expr[name] = name.replace('u_accel/u_v1/', 'dut.')
    external = {'gpu_debug_state[46]':'resetn', 'gpu_debug_state[48]':'child_resetn',
                'vid_hrstn':"1'b1", 'ddr_init':"1'b1", 'trial_request':"1'b1"}
    for name in m['controls'].values():
        expr[name] = external.get(name, name.replace('u_accel/u_v1/', 'dut.').replace('/', '.'))
    assert set(expr) == set(m['unique_signals'])
    # Exercise the duplicate trigger column used by some GAO versions as well.
    names = [m['controls']['shader_start'], *m['unique_signals']]
    tb = (old/'tb.sv').read_text()
    header = 'Data:\\ntime unit: us, '+', '.join(names)+',\\n'
    monitor = '''integer trace, sample_index=0;
initial begin
    trace=$fopen("mapped_trace.csv", "w");
    if(!trace)$fatal(1,"Trace open failed");
    $fwrite(trace, "'''+header+'''");
end
always @(posedge clk) begin
    $fwrite(trace, "%0d, '''+', '.join('%b' for _ in names)+''',\\n", sample_index, '''+', '.join(expr[n] for n in names)+''');
    sample_index=sample_index+1;
end
'''
    tb = tb.replace('integer captures=0;', monitor+'integer captures=0;')
    (out/'tb.sv').write_text(tb)
    compiler=Path('/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog')
    result = dict(passed=False, hardware_access=False,
        scope='Exact mapped GPU functional simulation; not GAO hardware or encrypted pipeline simulation',
        synthetic_external_constants=['vid_hrstn', 'ddr_init', 'trial_request'])
    try:
        with (out/'compile.log').open('x') as log:
            subprocess.run([str(compiler), '-B', str(compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'),
                '-g2012', '-s', 'tb', '-o', 'sim.vvp', 'tb.sv', 'mapped.v', 'primitives.v'],
                cwd=out, stdout=log, stderr=log, check=True, timeout=90)
        with (out/'simulation.log').open('x') as log:
            subprocess.run([str(compiler.parent/'vvp'), 'sim.vvp'], cwd=out,
                stdout=log, stderr=log, check=True, timeout=120)
        rows = parse_csv((out/'mapped_trace.csv').read_text(), m)
        observed = analyze(rows, m)
        assert len(observed['sampled_capture_events']) == 16
        assert not observed['conditional_dffre_mismatches'], observed['conditional_dffre_mismatches']
        assert not observed['conditional_checks_skipped']
        assert not observed['ce_and_disagreements']
        assert not observed['reset_inverse_disagreements']
        tests = {}
        i = observed['sampled_capture_events'][0]['sample']
        # Simulate missing downstream capture, exact observed type of failure.
        missing = copy.deepcopy(rows)
        for name in m['pixel_Q'].values(): missing[i+1][name] = 0
        bad = analyze(missing, m)
        assert any(v['sample'] == i and v['rule'] == 'capture' for v in bad['conditional_dffre_mismatches'])
        tests['missed_capture'] = True
        ce = copy.deepcopy(rows)
        ce[i][m['controls']['pixel_capture_enable']] = 0
        assert i in analyze(ce, m)['ce_and_disagreements']
        tests['missing_ce'] = True
        reset = copy.deepcopy(rows)
        reset[i][m['controls']['pixel_reset_active_high']] = 1
        bad = analyze(reset, m)
        assert i in bad['reset_inverse_disagreements']
        assert any(v['sample'] == i and v['rule'] == 'reset' for v in bad['conditional_dffre_mismatches'])
        tests['unexpected_reset'] = True
        unknown = copy.deepcopy(rows)
        unknown[i][m['actual_pixel_D']['24']] = None
        assert i in analyze(unknown, m)['conditional_checks_skipped']
        tests['unknown_not_zero'] = True
        # Bits 29,30,31 share the true D signal: explicitly preserve that alias.
        alias = copy.deepcopy(rows[i])
        alias[m['actual_pixel_D']['31']] = 1
        from pixel_trace import word
        assert word(alias, m['actual_pixel_D']) & 0xe0000000 == 0xe0000000
        tests['shared_actual_D'] = True
        text = (out/'mapped_trace.csv').read_text()
        # Reject a disagreeing trigger duplicate rather than silently choosing one.
        lines = text.splitlines()
        fields = lines[2].split(','); fields[1] = ' 1' if fields[1].strip() == '0' else ' 0'
        lines[2] = ','.join(fields)
        try:
            parse_csv('\n'.join(lines), m)
        except AssertionError:
            tests['duplicate_disagreement_rejected'] = True
        else: raise AssertionError('Duplicate mismatch accepted')
        (out/'decoded.json').write_text(json.dumps(observed, indent=2)+'\n')
        result.update(passed=True, samples=len(rows), captures=16, checks=tests,
                      wrapper=audit_wrapper())
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        shutil.copy2(Path(__file__), out/'controller.py')
        shutil.copy2(HERE/'pixel_trace.py', out/'pixel_trace.py')
        result['files']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('passed', 'samples', 'captures', 'error') if k in result}))


if __name__ == '__main__': main()
