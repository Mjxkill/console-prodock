#!/usr/bin/env python3
"""Qualify observation paths separately from application/global timing."""
import json
import re
from pathlib import Path
from audit_route_r20r1 import HERE, BUILD, PARENT, sha, cells, clean, vec

def main():
    audit=HERE/'r20r1_postroute_01/result.json';r=json.loads(audit.read_text())
    for name,digest in r['input_sha256'].items():assert sha(Path(name))==digest,name
    old,_=cells(PARENT/'impl/pnr/console_neo.vo');new,_=cells(BUILD/'impl/pnr/console_neo.vo')
    def drivers(cs):
        result={}
        for name,(kind,ports) in cs.items():
            outputs=['Q'] if kind.startswith('DFF') else ['F'] if kind.startswith(('LUT','MUX')) else ['O'] if kind in ('INV','BUF','OBUF','IBUF') else []
            for port in outputs:
                n=ports.get(port)
                if n and re.fullmatch(r'[^{}:,]+',n):result.setdefault(n,set()).add((name,port))
        return result
    od,nd=drivers(old),drivers(new);aliases=[];unexplained={}
    for name,change in r['changed_parent_cells'].items():
        if name.startswith('u_gpu_debug/'):continue
        a,b=change['before'],change['after']
        if a[0]!=b[0] or set(a[1])!=set(b[1]):unexplained[name]=change;continue
        for port,x in a[1].items():
            y=b[1][port]
            if x==y:continue
            if od.get(x) and od.get(x)==nd.get(y):aliases.append(dict(cell=name,port=port,before=x,after=y,drivers=sorted(od[x])))
            else:unexplained.setdefault(name,{})[port]=dict(before=x,after=y,old_drivers=sorted(od.get(x,())),new_drivers=sorted(nd.get(y,())))
    missing=[n for n in r['missing_parent_cells'] if not n.startswith('u_gpu_debug/')]
    added=[n for n in r['added_cells'] if not n.startswith('u_gpu_debug/')]
    params={n:v for n,v in r['changed_parent_parameters'].items() if not n.startswith('u_gpu_debug/')}
    sdf=(BUILD/'impl/pnr/console_neo.sdf').read_text();clocks={};setups={}
    for src,dst,delay in re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([^)]+)\)\)',sdf):
        if dst.endswith('/CLK'):clocks[clean(dst).removesuffix('/CLK')]=(clean(src),vec(delay))
    for part in sdf.split('\n  (CELL\n')[1:]:
        m=re.search(r'\(INSTANCE ([^\s)]+)\)',part)
        if not m:continue
        name=clean(m[1])
        for port,setup in re.findall(r'\(SETUPHOLD \((?:pos|neg)edge (\w+)\) \(posedge CLK\) \(([^)]+)\)',part):
            key=name+'/'+port;setups[key]=max(setups.get(key,0),max(vec(setup)))
    bounds=[];invalid=[]
    for path in r['snapshot_cone_paths']+r['sample_cone_paths']:
        src=path['source'];dst=path['destination'];cell=dst.rsplit('/',1)[0]
        sc,sd=clocks[src];dc,dd=clocks[cell]
        if sc!=dc or path['source_clock']!='gpu_clk' or dst not in setups:
            invalid.append(dict(path=path,source_clock=sc,destination_clock=dc));continue
        slack=[13.333+b-a-d-setups[dst] for a,b,d in zip(sd,dd,path['max_by_corner_ns'])]
        bounds.append(dict(source=src,destination=dst,conservative_setup_ns=slack))
    transport=max(max(p['max_by_corner_ns']) for p in r['snapshot_transport_paths'])
    min_setup=min(min(p['conservative_setup_ns']) for p in bounds)
    app_ok=not any((unexplained,missing,added,params))
    path_ok=bool(bounds) and not invalid and min_setup>0 and transport<20 and r['held_shadow_max_ns']<20
    result=dict(candidate=str(BUILD),candidate_only=True,qualification=r['qualification_status'],
        bitstream_sha256=r['bitstream_sha256'],timing=r['timing'],application_logic_preserved=app_ok,
        observation_paths_passed=path_ok,observation_setup_bound_ns=min_setup,
        snapshot_transport_max_ns=transport,aliases=aliases,unexplained_cells=unexplained,
        missing_application_cells=missing,added_application_cells=added,changed_application_parameters=params,
        invalid_path_origins=invalid,path_bounds=bounds,
        inputs={**r['input_sha256'],str(audit):sha(audit),str(Path(__file__)):sha(Path(__file__))},
        limits=['Not a complete timing qualification; global violations remain explicit.',
                'Snapshot timing bounds do not explain the failing GPU; hardware reproduction still required.',
                'Recovery timing uses the existing delayed-ready protocol after startup.'])
    out=HERE/'r20r1_routed_review.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('application_logic_preserved','observation_paths_passed','observation_setup_bound_ns','snapshot_transport_max_ns','timing')}))
    if not app_ok or not path_ok:raise SystemExit('R20r1 review incomplete or failed; no hardware load authorized by this report')

if __name__=='__main__':main()
