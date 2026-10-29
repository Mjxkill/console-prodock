from pathlib import Path
import csv,hashlib,json
O=Path(__file__).resolve().parent
runs=[]
for n,engine,phase,quick in [('v2_phase1000','Verilator',1000,0),('v2_phase3125','Verilator',3125,0),('v2_phase11000','Verilator',11000,0),('icarus_v2_phase1000','Icarus4state',1000,0),('icarus_v2_phase11000','Icarus4state',11000,1)]:
 p=O/n;rows=list(csv.reader((p/'events.csv').read_text().splitlines()));s=next(x for x in rows if x[0]=='SUMMARY');assert list(map(int,s[1:3]))==[phase,quick];assert 'REPRODUCTION_PASS' in (p/'simulation.log').read_text()
 releases=[dict(case=int(r[1]),time_ns=float(r[2]),since_lock_rise_ns=float(r[3]),since_available_ns=float(r[4]),done=int(r[5]))for r in rows if r[0]=='RELEASE']
 unqualified=[r for r in releases if r['done']==0]
 failures2=sum(r['since_lock_rise_ns']<2e6 for r in releases);failures50=sum(r['since_available_ns']<50e6 for r in releases)
 assert [len(releases),failures2,failures50]==list(map(int,s[3:]));assert len(unqualified)==(0 if phase==11000 else 1)
 runs.append(dict(name=n,engine=engine,phase_ps=phase,quick=bool(quick),test_exit_code=0,reproduction_passed=True,dut_2ms_property_passed=False,dut_50ms_property_passed=False,releases=releases,unqualified_releases=unqualified,summary_counts=list(map(int,s[3:])),files={f:hashlib.sha256((p/f).read_bytes()).hexdigest()for f in ['events.csv','trace.csv','simulation.log']}))
a=(O/'v2_phase1000/events.csv').read_bytes();b=(O/'icarus_v2_phase1000/events.csv').read_bytes();assert a==b
rows_a=[x for x in (O/'v2_phase11000/events.csv').read_text().splitlines()if x.startswith(('RELEASE,0,','RELEASE,1,','RELEASE,2,','FALL,1,','FALL,2,','BASELINE,','CASE,1,','CASE,2,'))]
rows_b=[x for x in (O/'icarus_v2_phase11000/events.csv').read_text().splitlines()if x.startswith(('RELEASE,0,','RELEASE,1,','RELEASE,2,','FALL,1,','FALL,2,','BASELINE,','CASE,1,','CASE,2,'))];assert rows_a==rows_b
files=['prepare.py','source_manifest.json','tb.sv','tb_initial.sv','exact_chain.sv','neo_reset_trial.v','neo_reset_trial_rx.v','compile.log','compile_v2.log','icarus/compile.log','icarus/simulation.log','icarus/events.csv','icarus/trace.csv']
r=dict(hardware_access=False,production_sources_modified=False,candidate_fix_present=False,r19_r21_reset_sources_equal=True,reproduction_passed=True,cause_of_r21_board_failure_established=False,dut_continuous_lock_2ms_property_passed=False,dut_long_mode_50ms_property_passed=False,dut_no_unqualified_por_pulse_property_passed=False,simulator_event_equality_phase1000=True,simulator_event_equality_phase11000_common_cases=True,runs=runs,files={f:hashlib.sha256((O/f).read_bytes()).hexdigest()for f in files},initial_bench_failure='Initial expectation omitted a second premature POR pulse for sampled8ns loss; original Icarus evidence retained; DUT unchanged between benchversions.',limits=['Behavioral digital simulation, no SDF or metastability model','LOCK and DDRready are external digital stimuli, not a PLL/DDR physical model','No hardCPU behavioral substitute; POR/HW input signals only','Pulses below actual asynchronous-control minimum width require separate physical qualification','Shared reset weakness is not a proven explanation of R19/R21 board difference'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(hashlib.sha256((O/'result.json').read_bytes()).hexdigest())
