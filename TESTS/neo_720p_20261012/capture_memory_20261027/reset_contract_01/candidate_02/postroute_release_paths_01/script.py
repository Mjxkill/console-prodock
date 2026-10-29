#!/usr/bin/env python3
"""Record exact routed reset paths and legal release sensitization, without STA exceptions."""
from pathlib import Path
import functools,hashlib,itertools,json,re,runpy
HERE=Path(__file__).resolve().parent;A=runpy.run_path(str(HERE/'audit_routed.py'))
B=A['BUILD'];P=A['PARENT'];OUT=HERE/'postroute_release_paths_01'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    v,p=A['routed_cells'](B/'impl/pnr/console_neo.vo');old,op=A['routed_cells'](P/'impl/pnr/console_neo.vo');drivers=A['drivers'](v)
    def paths(net,source,seen=()):
        for name,pin in drivers.get(net,[]):
            if name==source:yield [(name,pin)];continue
            if name in seen or name not in v:continue
            kind,ports=v[name]
            if kind!='INV' and not kind.startswith(('LUT','MUX')):continue
            for inp,n in ports.items():
                if inp in A['OUTPUTS'][kind]:continue
                for path in paths(n,source,seen+(name,)):yield path+[(name,inp+'->'+pin)]
    targets=['u_soc/init_sync_0_s0','u_soc/init_sync_1_s0']
    source='u_pll_ae350/u_pll_init/state_1_s0'
    exact={n:list(paths(v[n][1]['CLEAR'],source)) for n in targets}
    names=set(n for ps in exact.values() for path in ps for n,_ in path)
    nodes={n:dict(kind=v[n][0],pins=v[n][1],params={k:x for k,x in p.items() if k.startswith(n+'.')}) for n in sorted(names)}
    assert all(len(x)==1 for x in exact.values())
    assert not any('PLL_inst' in n for n in names)
    # Evaluate the exact six LUT equations for all binary combinations.
    def lut(name,ins):
        k,pins=v[name];width=int(k[3:]);assert len(ins)==width
        raw=p[name+'.INIT'];init=int(raw.split("'h")[1],16)
        return (init>>sum(x<<i for i,x in enumerate(ins)))&1
    truth=[]
    for state,lock,first,ddr,ready,holding,done in itertools.product(range(8),range(2),range(2),range(2),range(2),range(2),range(2)):
        masked=lut('u_pll_ae350/u_pll_init/pll_ae350_lock_s',[(state>>i)&1 for i in range(3)]+[lock])
        qualified=lut('neo_qualified_pll_lut',[masked,first])
        unavailable=lut('u_reset_trial/n261_s1',[ddr,qualified])
        request=lut('u_reset_trial/release_request_d_s',[holding,unavailable,ready,done])
        clear=lut('u_soc/neo_qualified_clear_lut',[first,request])
        assert request==int(bool(masked and not first and ddr and ready and not holding and done))
        assert clear==int(bool(first or not request))
        if not done:assert clear==1
        truth.append([state,lock,first,ddr,ready,holding,done,request,clear])
    (OUT/'truth_table.json').write_text(json.dumps(truth)+'\n')
    incoming,cq,clocks,setup,counts=A['parse_sdf']((B/'impl/pnr/console_neo.sdf').read_text())
    @functools.lru_cache(None)
    def origins(pin):
        name,port=pin.rsplit('/',1)
        if name in cq and port=='Q':return {name:cq[name]}
        if pin not in incoming:return {}
        found={}
        for start,delay in incoming[pin]:
            for origin,previous in origins(start).items():
                val=tuple(x+y for x,y in zip(previous,delay))
                found[origin]=tuple(max(x,y) for x,y in zip(found[origin],val)) if origin in found else val
        return found
    reset_audit=json.loads((HERE/'postroute_01/reset.json').read_text())['reset_timing']
    sdc=(B/'source/tang/boards/neo/neo.sdc').read_text()
    assert 'set_max_delay 8.000 -from [get_clocks {clk50}] -to [get_clocks {bus80_clk}]' in sdc
    timing=[]
    for target in targets:
        for name,delay in origins(target+'/CLEAR').items():
            if name not in ['u_reset_trial/delay_done_s2',source]:continue
            sc,sd=clocks[name];tc,td=clocks[target]
            # Same inherited set_max_delay8 used by these clocks. This mixes
            # adverse corners deliberately; it is a conservative bound, not STA.
            triplets=reset_audit['reset_requirements'][target+'/CLEAR']['recovery_requirement_triplets']
            assert len(triplets)==1
            requirement=max(float(x) for x in triplets[0].split(':'))
            bound=8+min(td)-max(sd)-max(delay)-requirement
            timing.append(dict(source=name,destination=target+'/CLEAR',source_clock=sc,destination_clock=tc,data_delay_by_corner_ns=delay,source_clock_by_corner_ns=sd,destination_clock_by_corner_ns=td,recovery_requirement_ns=requirement,max_delay_bound_ns=8,conservative_constraint_bound_ns=bound,claim='Constraint-based bound only; not an asynchronous phase or metastability proof'))
    assert len(timing)==4
    rows=A['table_paths']((B/'impl/pnr/console_neo.tr').read_text());oldrows=A['table_paths']((P/'impl/pnr/console_neo.tr').read_text())
    relevant=lambda rows:[r for r in rows if any(r['destination'].startswith(n+'/') for n in targets)]
    olddrivers=A['drivers'](old)
    parent_clear={n:dict(pin=old[n][1]['CLEAR'],drivers=sorted(olddrivers.get(old[n][1]['CLEAR'],set()))) for n in targets}
    inputs=[Path(__file__),B/'impl/pnr/console_neo.vo',B/'impl/pnr/console_neo.sdf',B/'impl/pnr/console_neo.tr',P/'impl/pnr/console_neo.vo',P/'impl/pnr/console_neo.tr',HERE/'neo_reset_trial.v',HERE/'mapped_01/result.json',HERE/'postroute_01/reset.json',OUT/'truth_table.json']
    r=dict(analysis_complete=True,hardware_access=False,timing_qualification='FAIL retained',paths=exact,nodes=nodes,parent_clear=parent_clear,reported_paths=relevant(rows),parent_reported_paths=relevant(oldrows),conservative_bounds=timing,truth_table_cases=len(truth),legal_startup_reasoning=['delay_done has INIT0 and remains0 until the full count expires after ready_meta[1] is high.','While delay_done=0, exact routed release_request LUT output is0 and both final CLEAR inputs are1 for every state/LOCK value. This proves combinational masking, not analog pulse capture.','The legal first release is caused by delay_done after qualification, with masked LOCK and ready_meta already stable.','On LOCK loss, asynchronous invalidation and first-chain coupling were tested in the exact mapped candidate. This does not prove a minimum silicon pulse width or discard the STA path.'],limits=['Reported setup/recovery violations remain FAIL; no false_path or SDC change introduced.','CLK50 and bus80 are asynchronous in constraints; positive constraint-based bound does not establish phase relationship.','Initial-chain PRESET false paths, raw PLL LOCK analog behavior, hardCPU reset contract and metastability remain separate coverage limits.'],inputs={str(x):sha(x) for x in inputs})
    (OUT/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(result=str(OUT/'result.json'),sha256=sha(OUT/'result.json'),bounds=timing),indent=2))
if __name__=='__main__':main()
