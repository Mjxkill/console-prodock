#!/usr/bin/env python3
"""Route only the reviewed coupled R21 reset candidate. No board access."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment

BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
PARENT=ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
NET='4eace9a4feabe65a1a47e726500b23dd256b4edc3ea4f037b36a9d4d14e08ae4'
ASSEMBLY='6a0015a5c155d98bea8b98142f0e6153850a5915b5db81551c16231a1b4c1333'
PARENT_NET='3f49d84ccb8b2001e5afa156b36849705652003fbf4e2a741847dc23f1713338'
PARENT_BIT='2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def save(path,data): path.write_text(json.dumps(data,indent=2)+'\n')
def manifest(path): return {str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def guard(review_path):
    contract=before_build('neo',candidate=True)
    assert sha(PARENT/'console_neo.vg')==PARENT_NET
    assert sha(PARENT/'impl/pnr/console_neo.fs')==PARENT_BIT
    assert manifest(PARENT/'source')==read(PARENT/'sources.json')
    assert sha(BUILD/'assembly.json')==ASSEMBLY
    assembly=read(BUILD/'assembly.json')
    assert assembly['passed'] and not assembly['release_qualified']
    for p,h in assembly['inputs'].items():assert sha(BUILD/p)==h,p
    for p,h in assembly['external_inputs'].items():assert sha(Path(p))==h,p
    assert manifest(BUILD/'source')==read(BUILD/'sources.json')
    assert sha(BUILD/'console_neo.vg')==NET
    review=read(review_path)
    assert review['route_authorized'] is True and review['hardware_authorized'] is False
    assert review['netlist_sha256']==NET and review['assembly_sha256']==ASSEMBLY
    assert review['scope']=='candidate_pnr_only'
    for p,h in review['proof_files'].items():assert sha(Path(p))==h,p
    mapped_path=HERE/'candidate_02/mapped_01/result.json'
    assert str(mapped_path) in review['proof_files']
    mapped=read(mapped_path)
    assert mapped['passed'] and mapped['returncode']==0 and mapped['netlist_sha256']==NET
    for p,h in mapped['inputs'].items():assert sha(Path(p))==h,p
    for p,h in mapped['outputs'].items():assert sha(mapped_path.parent/p)==h,p
    for name in ('root_structure_coupled.json','root_capture_asymmetry_02/result.json',
                 'candidate_02/boundary_proof.json'):
        path=HERE/name
        assert str(path) in review['proof_files'] and read(path)['passed']
    for name in ('fable','deepseek','beam'):
        folder=ROOT/'TESTS/assisted_reviews_20261026'/('neo_reset_patch_'+name+'_r2')
        assert str(folder/'status.json') in review['proof_files']
        assert str(folder/'answer.txt') in review['proof_files']
        status=read(folder/'status.json')
        assert status['status']=='COMPLETED_REVIEW_PENDING_VALIDATION'
        assert status['packet_sha256']==sha(HERE/'patch_review_packet_02/packet.txt')
    tool=ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/gw_sh'
    assert sha(tool)==sha(IDE/'bin/gw_sh')
    return contract,tool


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',type=Path,required=True)
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args();review_path=args.review.resolve()
    assert review_path.is_relative_to(HERE)
    contract,tool=guard(review_path)
    if args.check_only:
        print(json.dumps(dict(ready=True,hardware_access=False,netlist_sha256=NET)))
        return
    with (BUILD/'route.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert not (BUILD/'route_launch.json').exists()
        assert not (BUILD/'build.log').exists()
        assert not (BUILD/'impl/pnr/console_neo.fs').exists()
        record_build(BUILD,contract)
        started=time.time()
        with (BUILD/'build.log').open('x') as log:
            child=subprocess.Popen([str(tool),'build.tcl'],cwd=BUILD,env=environment(),stdout=log,stderr=log)
            save(BUILD/'route_launch.json',dict(candidate=True,hardware_access=False,loaded=False,
                 pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=sha(tool),
                 netlist_sha256=NET,assembly_sha256=ASSEMBLY,wrapper_sha256=sha(Path(__file__)),
                 root_review=str(review_path),root_review_sha256=sha(review_path),
                 local_regressions=contract['local_regressions']))
            print('R21R2_COUPLED_ROUTE_STARTED pid='+str(child.pid),flush=True)
            rc=child.wait()
        output=(BUILD/'build.log').read_text()
        ok=rc==0 and 'Bitstream generation completed' in output and not re.search(r'^ERROR',output,re.M)
        assert sha(BUILD/'console_neo.vg')==NET
        save(BUILD/'route_result.json',dict(returncode=rc,
             status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',
             started_unix=started,finished_unix=time.time(),hardware_access=False,loaded=False,
             log_sha256=sha(BUILD/'build.log'),netlist_sha256=NET))
        if not ok:raise SystemExit('Route failed; evidence preserved, no board touched')
        print('Routed; physical timing/reset audit and board trial remain pending',flush=True)


if __name__=='__main__':main()
