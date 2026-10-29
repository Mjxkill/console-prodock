#!/usr/bin/env python3
"""Check passive-observer registers and control routing before a board trial."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
from prepare_scan_observer import ROOT,HERE,sha
from route_scan_observer import OUT,NETSHA

sys.path.insert(0,str(HERE.parent/'n55_gpu_diagnosis_20261021'))
from build_local_controls import cells,norm
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets,CLOCK,CE,pin_base

def bits(expression):
    expression=norm(expression)
    if expression.startswith('{'):
        assert expression.endswith('}') and '{' not in expression[1:]
        return [b for atom in expression[1:-1].split(',') for b in bits(atom)]
    m=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',expression)
    if m:return [f'{m[1]}[{n}]' for n in range(int(m[2]),int(m[3])-1,-1)]
    return [expression]

def flattened_observer(module,instance,ports):
    widths={name:(int(hi),int(lo)) if hi else None for hi,lo,name in re.findall(
        r'^(?:input|output|inout) (?:\[(\d+):(\d+)\]\s+)?(\w+)\s*;',module,re.M)}
    aliases={}
    for port,target in ports.items():
        assert port in widths
        width=widths[port]
        local=[port] if width is None else [f'{port}[{n}]' for n in range(width[0],width[1]-1,-1)]
        global_bits=bits(target)
        assert len(local)==len(global_bits),(port,target)
        aliases.update(zip(local,global_bits))
    def resolve(net):
        return net if net in ('VCC','GND') else aliases.get(net,instance+'/'+net)
    output={}
    for name,cell in cells(module).items():
        if not cell['kind'].startswith('DFF'):continue
        output[instance+'/'+name]=dict(kind=cell['kind'],pins={pin:resolve(net) for pin,net in cell['pins'].items()})
    inits={instance+'/'+norm(n):v.lower() for n,v in re.findall(
        r'^\s*defparam\s+(\\\S+|\w+)\s*\.INIT\s*=\s*([^;]+);',module,re.M)}
    return output,inits

def audit():
    build=OUT
    assert sha(build/'console_neo.vg')==NETSHA
    text=(build/'console_neo.vg').read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    top=cells(modules['console_neo'])
    routed,params,drivers,loads=indexed_netlist(build/'impl/pnr/console_neo.vo')
    global_routes=global_nets(build)
    errors=[];changes=[];registers={};control_nets=set()
    counts={}
    for instance in ('u_scan_observe','u_scan_debug'):
        source,init=flattened_observer(modules[top[instance]['kind']],instance,top[instance]['pins'])
        counts[instance]=len(source)
        for name,expected in source.items():
            actual=routed.get(name)
            expected_init={k.lower():v.lower() for k,v in params.get(name,{}).items()}.get('init')
            if expected!=actual or expected_init!=init[name]:
                changes.append(dict(instance=name,before=expected,after=actual,
                    before_init=init[name],after_init=expected_init))
            registers[name]=expected
            if expected['pins']['CLK'] not in ('gpu_clk','vid_hclk'):
                errors.append('Unexpected observer clock '+name)
            for pin in ('CE','RESET','CLEAR'):
                net=expected['pins'].get(pin)
                if net and net not in ('VCC','GND'):control_nets.add(net)
    if changes:errors.append('Observer register function/clock/reset/init changed after synthesis')
    for prefix in ('accepted_by_queue','accepted_by_arbiter','returned'):
        found=[name for name in registers if re.fullmatch(r'u_scan_observe/'+prefix+r'_\d+_s\d+',name)]
        if len(found)!=32:errors.append('Missing 32-bit observer counter '+prefix)
    # Global promotion of the original controls already caused failures on
    # this board. Check the new observer controls as well as the retained set.
    required=['u_accel/u_v1/n56220_6','u_gpu_debug/n2835_5','scan_debug_live[224]']
    control_nets.update(required)
    controls=[]
    for net in sorted(control_nets):
        issue=[]
        if net in global_routes:issue.append('Control on '+global_routes[net])
        if len(drivers[net])!=1:issue.append('Control does not have one driver')
        if any(CLOCK.fullmatch(pin_base(pin)) for _,_,pin in loads[net]):issue.append('Control feeds a clock pin')
        controls.append(dict(net=net,drivers=drivers[net],load_pin_counts=dict(Counter(pin_base(p) for _,_,p in loads[net])),errors=issue))
    if any(c['errors'] for c in controls):errors.append('Observer/control routing requires review')
    # High fanout CE nets from the scanout must not silently migrate onto LW.
    gpu_global_ce=[]
    for net,resource in global_routes.items():
        affected=[x for x in loads[net] if x[0].startswith(('u_gpu/','u_scan_queue/','u_scan_observe/','u_scan_debug/')) and CE.fullmatch(pin_base(x[2]))]
        if affected:gpu_global_ce.append(dict(net=net,resource=resource,loads=affected))
    if gpu_global_ce:errors.append('Global CE route feeding scanout or observer')
    q=json.loads((build/'qualification.json').read_text())
    required_audit=q['synthesis_audits']['timing_closure']
    if not required_audit['passed']:errors.append('Clock allocation/HDMI/reset audit failed')
    paths=[Path(__file__),build/'console_neo.vg',build/'impl/pnr/console_neo.vo',
        build/'impl/pnr/console_neo.rpt.txt',build/'qualification.json',build/'sources.json',
        build/'source/tang/boards/neo/neo.cst',build/'source/tang/boards/neo/neo.sdc',
        HERE.parent/'n55_gpu_diagnosis_20261021/audit_geometry_controls.py',
        HERE.parent/'n55_gpu_diagnosis_20261021/audit_gpu_control_inventory.py',
        HERE.parent/'n55_gpu_diagnosis_20261021/build_local_controls.py']
    return dict(passed=not errors,errors=errors,register_counts=counts,register_changes=changes,
        controls=controls,global_scanout_ce=gpu_global_ce,
        sha256={str(p):sha(p) for p in paths},hardware_access=False,
        limits=['Targeted register/control audit, not full-design equivalence or timing qualification.',
            'RTL tests do not reproduce analog DDR behavior or metastability.'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wait',action='store_true',help='Wait for this exact route automatic checks, never program a board')
    args=p.parse_args()
    if args.wait:
        end=time.monotonic()+7200
        while not (OUT/'automatic_checks.json').exists():
            if (OUT/'route_result.json').exists() and json.loads((OUT/'route_result.json').read_text())['status']=='ROUTING_FAILED':
                raise SystemExit('Route failed; no audit possible')
            if time.monotonic()>end:raise SystemExit('Automatic qualification still incomplete')
            time.sleep(15)
    result=audit()
    with (OUT/'scan_observer_audit.json').open('x') as handle:json.dump(result,handle,indent=2)
    print(json.dumps({k:result[k] for k in ('passed','errors','register_counts','hardware_access')},indent=2),flush=True)
    if not result['passed']:raise SystemExit('Observer audit failed')

if __name__=='__main__':main()
