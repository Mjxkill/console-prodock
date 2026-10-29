#!/usr/bin/env python3
"""Audit a completed R5: all scalar/vector control pins, primitive parameters and global routes."""
from collections import defaultdict, Counter
import json
from pathlib import Path
from audit_gpu_control_inventory import bit_expander, primitive_directions, global_nets, pin_base, CLOCK
from prove_geometry_controls import parameters
from build_geometry_controls import PARENT, ROOT, NAME, ADDITION, NETS, SHA_NET, sha, dump


def indexed_netlist(path):
    from build_local_controls import cells
    body=path.read_text()
    cc,expand,directions=cells(body),bit_expander(body),primitive_directions()
    drivers,loads=defaultdict(list),defaultdict(list)
    for name,cell in cc.items():
        for port,expression in cell['pins'].items():
            bits=expand(expression)
            vector=len(bits)>1 or expression.startswith('{')
            output=directions.get(cell['kind'],{}).get(port)=='output'
            for i,net in enumerate(bits):
                pin=f'{port}[{len(bits)-1-i}]' if vector else port
                (drivers if output else loads)[net].append((name,cell['kind'],pin))
    return cc,parameters(body),drivers,loads


def audit():
    build=ROOT/'tang/impl'/NAME
    errors=[]
    old=json.loads((PARENT/'sources.json').read_text())
    new=json.loads((build/'sources.json').read_text())
    actual={str(p.relative_to(build/'source')):sha(p) for p in (build/'source').rglob('*') if p.is_file()}
    if actual!=new or set(new)!=set(old) or sorted(k for k in new if new[k]!=old[k])!=['tang/boards/neo/neo.cst']:
        errors.append('Unexpected source mutation')
    if (build/'source/tang/boards/neo/neo.cst').read_text()!=(PARENT/'source/tang/boards/neo/neo.cst').read_text()+ADDITION:
        errors.append('Unexpected CST change')
    if sha(build/'console_neo.vg')!=SHA_NET:
        errors.append('Changed synthesis netlist')
    pc,pp,pd,pl=indexed_netlist(PARENT/'impl/pnr/console_neo.vo')
    cc,cp,cd,cl=indexed_netlist(build/'impl/pnr/console_neo.vo')
    old_global,new_global=global_nets(PARENT),global_nets(build)
    controls=[]
    expected={'u_accel/u_v1/n56220_6':312,'u_gpu_debug/n2835_5':283,
        'u_gpu_debug/mem_up[1]':2,'u_accel/u_v1/n56864_3':256,
        NETS[0]:204,NETS[1]:246,'gpu_debug_state[48]':9}
    for net,count in expected.items():
        issues=[]
        if pd[net]!=cd[net] or len(pd[net])!=1:
            issues.append('Driver resolution changed')
        if sorted(pl[net])!=sorted(cl[net]) or len(cl[net])!=count:
            issues.append('Complete scalar/vector load set changed')
        if any(CLOCK.fullmatch(pin_base(pin)) for _,_,pin in cl[net]):
            issues.append('Control feeds a clock pin')
        affected={n for n,_,_ in pd[net]+pl[net]}
        differences=[name for name in sorted(affected) if cc.get(name)!=pc[name] or cp.get(name)!=pp.get(name)]
        if differences:
            issues.append('Driver or load primitive/pins/parameters changed')
        if net in new_global:
            issues.append('Control still uses global routing: '+new_global[net])
        controls.append(dict(net=net,load_count=len(cl[net]),load_pin_counts=dict(Counter(p for _,_,p in cl[net])),
            drivers=pd[net],changed_cells=differences,errors=issues,
            full_primitive_pins_and_parameters_unchanged=not differences))
    newly=[]
    for net,resource in sorted(new_global.items()):
        if old_global.get(net)==resource:
            continue
        newly.append(dict(net=net,resource=resource,drivers=cd[net],
            load_pin_counts=dict(Counter(p for _,_,p in cl[net]))))
    paths=[build/'sources.json',build/'console_neo.vg',build/'source/tang/boards/neo/neo.cst',
        build/'source/tang/boards/neo/neo.sdc',build/'impl/pnr/console_neo.vo',build/'impl/pnr/console_neo.rpt.txt',
        PARENT/'impl/pnr/console_neo.vo',PARENT/'impl/pnr/console_neo.rpt.txt',Path(__file__)]
    return dict(passed=not errors and all(not c['errors'] for c in controls),errors=errors,controls=controls,
        new_global_nets=newly,removed_global_nets=sorted(set(old_global)-set(new_global)),
        all_global_nets=new_global,sha256={str(p):sha(p) for p in paths},hardware_access=False,
        limitations=['A passing structural audit does not replace setup/hold/recovery/removal qualification.',
                     'All direct scalar/vector ports covered; a control may have indirect combinational descendants.',
                     'Newly global controls must be reviewed independently even if the seven selected controls pass.'])


if __name__=='__main__':
    result=audit()
    dump(ROOT/'tang/impl'/NAME/'geometry_controls_audit.json',result)
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise SystemExit('R5 control routing audit failed')
