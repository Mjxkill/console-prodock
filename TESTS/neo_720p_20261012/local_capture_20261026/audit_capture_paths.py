#!/usr/bin/env python3
"""Check exact post-route ECO and local sample setup bounds, without hardware."""
import json
from pathlib import Path
import re
from audit_route import HERE, BUILD, sha, clean, vec

def main():
    source=HERE/'postroute_01/result.json'
    r=json.loads(source.read_text())
    for p,h in r['input_sha256'].items(): assert sha(Path(p))==h,p
    assert not r['missing_parent_cells'] and not r['changed_parent_parameters']
    expected={f'u_gpu_debug/hrdata_{i}_s0' for i in range(32)}
    assert set(r['changed_parent_cells'])==expected
    for name,item in r['changed_parent_cells'].items():
        old,new=item['before'],item['after'];bit=int(re.search(r'hrdata_(\d+)_',name)[1])
        assert old[0]==new[0]
        assert old[1]['Q']==f'debug_hrdata[{bit}]'
        assert new[1]['Q']==f'u_gpu_debug/trace_legacy_data[{bit}]'
        assert {k:v for k,v in old[1].items() if k!='Q'}=={k:v for k,v in new[1].items() if k!='Q'}
    prefixes=('u_accel/u_v1/u_pixels/u_capture/','u_gpu_debug/u_capture_bus/')
    assert all(n.startswith(prefixes) for n in r['added_cells'])
    sdf=(BUILD/'impl/pnr/console_neo.sdf').read_text()
    clocks={}
    for src,dst,delay in re.findall(r'\(INTERCONNECT (\S+) (\S+) \(([^)]+)\)\)',sdf):
        if dst.endswith('/CLK'):
            dst=clean(dst).removesuffix('/CLK');assert dst not in clocks
            clocks[dst]=(clean(src),vec(delay))
    checks={}
    for block in sdf.split('\n  (CELL\n')[1:]:
        m=re.search(r'\(INSTANCE ([^\s)]+)\)',block)
        if not m:continue
        name=clean(m[1])
        if not name.startswith(prefixes):continue
        for port,setup in re.findall(r'\(SETUPHOLD \((?:pos|neg)edge (\w+)\) \(posedge CLK\) \(([^)]+)\)',block):
            key=name+'/'+port
            checks[key]=max(checks.get(key,0),max(vec(setup)))
    bounds=[]
    for path in r['sample_cone_paths']:
        src=path['source'];dst=path['destination'];cell=dst.rsplit('/',1)[0]
        sc,sd=clocks[src];dc,dd=clocks[cell]
        assert sc==dc and path['source_clock']=='gpu_clk'
        setup=checks[dst]
        slack=[13.333+b-a-d-setup for a,b,d in zip(sd,dd,path['max_by_corner_ns'])]
        assert min(slack)>0,(src,dst,slack)
        bounds.append(dict(source=src,destination=dst,conservative_setup_ns=slack))
    assert bounds and r['timing_summary']['violated_endpoints']['hold']==0
    # Signature constant-zero shadow bits do not have a registered held origin.
    covered={int(re.search(r'shadow_(\d+)_',p['destination'])[1]) for p in r['held_shadow_paths']}
    assert covered==set(range(55))|{56,62,63},sorted(covered)
    result=dict(passed=True,hardware_access=False,qualification='FAIL',timing=r['timing'],
        bitstream_sha256=r['bitstream_sha256'],route_audit_sha256=sha(source),script_sha256=sha(Path(__file__)),
        only_existing_output_change='32 legacy HRDATA Q nets renamed before address mux',
        all_other_application_cells_and_parameters_preserved=True,
        held_shadow_covered_bits=sorted(covered),held_shadow_constant_zero_bits=sorted(set(range(64))-covered),
        held_shadow_max_ns=r['held_shadow_max_ns'],sample_setup_lower_bound_ns=min(min(p['conservative_setup_ns']) for p in bounds),
        sample_setup_bounds=bounds,
        limits=['Conservative local SDF calculation, not independent full-design STA.',
                'Global setup/recovery failures remain; data interpretation requires explicit arm/readiness handshake long after boot.',
                'No hardware or complete GPU qualification.'])
    out=HERE/'capture_paths_01.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sample_setup_bounds','held_shadow_covered_bits')}))

if __name__=='__main__':main()
