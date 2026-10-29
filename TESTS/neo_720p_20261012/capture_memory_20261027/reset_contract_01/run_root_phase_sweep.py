#!/usr/bin/env python3
"""Exercise additional reset-clock phases; no FPGA or board access."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CANDIDATE = HERE / 'candidate_01'
OUT = HERE / 'root_phase_sweep_01'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    binary = CANDIDATE / 'obj_candidate_v2/Vtb'
    provenance = CANDIDATE / 'obj_candidate_v2/Vtb__verFiles.dat'
    compiled = provenance.read_text()
    sources = [CANDIDATE / n for n in ('invariants_tb.sv', 'exact_chain.sv',
                                      'neo_reset_trial.v', 'neo_reset_trial_rx.v')]
    # Verify that the reused binary's source timestamps and sizes match the
    # Verilator build record; retain both sources and binary digests as evidence.
    for p in sources:
        m = re.findall(r'^S\s+(\d+)\s+\d+\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+"' +
                       re.escape(str(p.relative_to(ROOT))) + r'"$', compiled, re.M)
        assert len(m) == 1, p
        size, seconds, nanos = map(int, m[0])
        assert (p.stat().st_size, p.stat().st_mtime_ns) == (size, seconds*10**9+nanos)
    inputs = {str(p): sha(p) for p in [binary, provenance, Path(__file__), *sources]}
    OUT.mkdir(exist_ok=False)
    for p in sources:
        (OUT / p.name).write_bytes(p.read_bytes())
    result = dict(passed=False, hardware_access=False,
                  scope='Additional ideal-clock RTL invariant tests, not physical qualification',
                  inputs=inputs, started_unix=time.time(), phases=[])

    def run(phase):
        directory = OUT / ('phase_' + str(phase))
        directory.mkdir()
        with (directory / 'simulation.log').open('x') as log:
            proc = subprocess.run([str(binary), '+PHASE_PS='+str(phase)],
                                  cwd=directory, stdout=log, stderr=log, timeout=180)
        output = (directory / 'simulation.log').read_text()
        events = directory / 'events.csv'
        passed = proc.returncode == 0 and f'INVARIANTS_PASS phase_ps={phase} quick=0 releases=15' in output
        record = dict(phase_ps=phase, passed=passed, returncode=proc.returncode,
                      log_sha256=sha(directory / 'simulation.log'),
                      events_sha256=sha(events) if events.exists() else None)
        print(json.dumps(record), flush=True)
        return record

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            result['phases'] = list(pool.map(run, (9000, 9500, 10000, 10001)))
        assert all(sha(Path(p)) == h for p, h in inputs.items())
        result['passed'] = all(p['passed'] for p in result['phases'])
    except Exception as exc:
        result['error'] = repr(exc)
        raise
    finally:
        result['finished_unix'] = time.time()
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['passed']:
        raise SystemExit('Phase sweep failed; all evidence retained')


if __name__ == '__main__':
    main()
