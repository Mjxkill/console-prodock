"""Prove the inherited -O gate bypass using file checks only; verify v3 refuses it."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    if sys.flags.optimize:
        raise SystemExit('assertions disabled: refusing to run')
    original = HERE.parent/'usb_video_trial_prepared_v2'
    before = hashlib.sha256((original/'probe_usb_video.py').read_bytes()).hexdigest()
    assert before == '4ea2b9f7d00fddba19fb00f1dd13816244c2b301c792464b6cf6291a3b86f9fe'
    bad = json.loads((original/'review_prepared.json').read_text())
    bad['hardware_ready'] = False
    bad['controller_sha256'] = '0'*64
    review = HERE/'invalid_review_for_offline_test.json'
    review.write_text(json.dumps(bad, indent=2)+'\n')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONOPTIMIZE', None)
    code = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
            'import probe_usb_video as c;c.local_checks(Path(sys.argv[2]),require_ready=True);'
            'print("BYPASS_CONFIRMED_FILE_CHECKS_ONLY")')
    normal = subprocess.run([sys.executable, '-c', code, str(original), str(review)],
                            env=env, capture_output=True, text=True, timeout=10)
    optimized = subprocess.run([sys.executable, '-O', '-c', code, str(original), str(review)],
                               env=env, capture_output=True, text=True, timeout=10)
    assert normal.returncode != 0 and 'Root review has not authorized hardware' in normal.stderr
    assert optimized.returncode == 0 and 'BYPASS_CONFIRMED_FILE_CHECKS_ONLY' in optimized.stdout
    cases = []
    scripts = ('probe_usb_video.py', 'test_controller.py', 'test_protocol.py', 'test_signals.py',
               'test_runtime_signals.py', 'test_review_guards.py', 'prepare_review.py')
    for script in scripts:
        for method in ('argument', 'environment'):
            options = ['-O'] if method == 'argument' else []
            variables = dict(env)
            if method == 'environment':
                variables['PYTHONOPTIMIZE'] = '1'
            args = ['--review', str(review), '--check-only'] if script == 'probe_usb_video.py' else []
            result = subprocess.run([sys.executable, *options, str(HERE/script), *args], env=variables,
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode != 0 and 'assertions disabled: refusing to run' in result.stderr, (script, result)
            cases.append(dict(script=script, method=method, passed=True, returncode=result.returncode))
    assert hashlib.sha256((original/'probe_usb_video.py').read_bytes()).hexdigest() == before
    previous = json.loads((original/'signal_tests_result.json').read_text())
    d1 = [dict(case=x['case'], signal=x['signal'], error=x['error']) for x in previous['cases']
          if x['error'] and 'KeyboardInterrupt' in x['error'] and 'error' not in x['report']]
    assert d1
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    result = dict(passed=True, hardware_access=False, controller_sha256=sha(HERE/'probe_usb_video.py'),
                  tool_sha256=sha(Path(__file__)), v2_sha256=before,
                  D1_existing_real_signal_cases_missing_error=d1,
                  D3_v2_optimized_preflight_accepted_invalid_review=True,
                  D3_normal_refused_not_ready=True, D3_v3_refused_optimized=cases,
                  scope='Only local_checks invoked on v2, never main or hardware execution. v3 optimized invocations refuse before argument processing.')
    (HERE/'review_guard_tests_result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, hardware_access=False, optimized_refusals=len(cases),
                         D1_counterexamples=len(d1))))


if __name__ == '__main__':
    main()
