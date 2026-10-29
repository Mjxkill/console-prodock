#!/usr/bin/env python3
"""Discriminate optional coupling with an explicit asymmetric-capture fault model."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import subprocess
import time

HERE=Path(__file__).resolve().parent
OUT=HERE/'root_capture_asymmetry_01'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    sources=[HERE/'capture_asymmetry_tb.sv',Path(__file__)]
    for name in ('candidate_01','candidate_02'):
        sources.extend(HERE/name/n for n in ('exact_chain.sv','neo_reset_trial.v','neo_reset_trial_rx.v'))
    inputs={str(p):sha(p) for p in sources}
    result=dict(passed=False,hardware_access=False,inputs=inputs,started_unix=time.time(),
                boundary='Intentional force of first reset chain only; not a physical PLL pulse model or evidence of the observed board cause')
    def run(name):
        folder=OUT/name;folder.mkdir()
        files=[HERE/'capture_asymmetry_tb.sv']+[HERE/name/n for n in ('exact_chain.sv','neo_reset_trial.v','neo_reset_trial_rx.v')]
        with (folder/'compile.log').open('x') as log:
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(folder/'sim.vvp'),*map(str,files)],stdout=log,stderr=log,timeout=60)
        assert c.returncode==0
        with (folder/'simulation.log').open('x') as log:
            c=subprocess.run(['vvp',str(folder/'sim.vvp')],cwd=folder,stdout=log,stderr=log,timeout=180)
        text=(folder/'simulation.log').read_text()
        wanted='CAPTURE_ASYMMETRY_STALE_QUALIFICATION' if name=='candidate_01' else 'ASYMMETRY_PASS releases=2'
        passed=wanted in text and ((c.returncode!=0) if name=='candidate_01' else c.returncode==0)
        record=dict(name=name,expected_negative=name=='candidate_01',passed=passed,returncode=c.returncode,
                    log_sha256=sha(folder/'simulation.log'),compile_log_sha256=sha(folder/'compile.log'),
                    executable_sha256=sha(folder/'sim.vvp'))
        print(json.dumps(record),flush=True)
        return record
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            result['tests']=list(pool.map(run,('candidate_01','candidate_02')))
        assert all(sha(Path(p))==h for p,h in inputs.items())
        result['passed']=all(t['passed'] for t in result['tests'])
    finally:
        result['finished_unix']=time.time();(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if not result['passed']:raise SystemExit('Asymmetric capture comparison failed')


if __name__=='__main__':main()
