#!/usr/bin/env python3
"""Freeze local simulation and assembly evidence; never route or access hardware."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=Path('/home/michael/console');BASE=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
proofs=[BASE/'simulation_01/result.json',BASE/'candidate_01/rtl_result.json',BASE/'candidate_01/synthesis_02/result.json',HERE/'mapped_01/result.json',HERE/'boundary_proof.json',BASE/'root_structure_coupled.json',BASE/'root_capture_asymmetry_02/result.json']
records={str(p):json.loads(p.read_text()) for p in proofs}
assert records[str(HERE/'mapped_01/result.json')]['passed']
m=records[str(HERE/'mapped_01/result.json')]
assert m['netlist_sha256']==sha(BUILD/'console_neo.vg')
for name,h in m['inputs'].items():assert sha(Path(name))==h,name
for name,h in m['outputs'].items():assert sha(HERE/'mapped_01'/name)==h,name
for p in proofs[1:]:assert records[str(p)]['passed'],p
for p in [HERE/'boundary_proof.json',BASE/'root_structure_coupled.json']:
 assert records[str(p)]['netlist_sha256']==sha(BUILD/'console_neo.vg')
assert (HERE/'neo_reset_trial.v').read_bytes()==(BASE/'candidate_01/neo_reset_trial.v').read_bytes()
assert 'PASS,1000,0,15' in (HERE/'mapped_01/events.csv').read_text()
a=json.loads((BUILD/'assembly.json').read_text())
for n,h in a['inputs'].items():assert sha(BUILD/n)==h,n
for n,h in a['external_inputs'].items():assert sha(Path(n))==h,n
paths=[Path(__file__),HERE/'candidate_manifest.json',HERE/'candidate.diff',HERE/'check_mapped.py',HERE/'check_boundaries.py',HERE/'README.md',BUILD/'assembly.json',BUILD/'sources.json',BUILD/'console_neo.vg',*proofs]
r=dict(passed=True,status='CANDIDATE_SIMULATED_NOT_ROUTED',candidate=True,hardware_access=False,loaded=False,routing_started=False,build=str(BUILD),netlist_sha256=sha(BUILD/'console_neo.vg'),assembly_sha256=sha(BUILD/'assembly.json'),helper_rtl_sha256=sha(HERE/'neo_reset_trial.v'),mapped_full_suite=dict(simulator='Icarus4state',functional_primitives='official Gowin',real_50ms_intervals=True,phase_ps=1000,scenarios=16,por_releases=15,compared_with='coupled candidate02 RTL at every reference/AHB rising edge and asynchronous input loss'),original_control='Original exact RTL fails generic invariant; separate original reproduction shows stale authorization and12.5ns pulse',candidate01='7RTL phases and Icarus full suite prove uncoupled local correction; capture asymmetry intentionally fails',candidate02='Coupled reset chain passes intentional asymmetry plus full exact-mapped/RTL comparison',files={str(p):sha(p) for p in paths},limits=['No hardCPU or PLL behavioral model.','No metastability or asynchronous minimum pulse width qualification.','No global timing or hardware qualification; candidate remains non-promoted.','Original hardware R21 startup failure cause not established by these digital counterexamples.','The first-stage AE350 reset capture and qualifier are now coupled; physical reset timing and CDC must be examined after route.','External model reviews are bound separately by parent; not represented as tests in this result.'])
with (HERE/'result.json').open('x') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(dict(result=str(HERE/'result.json'),sha256=sha(HERE/'result.json'),netlist_sha256=r['netlist_sha256']),indent=2))
