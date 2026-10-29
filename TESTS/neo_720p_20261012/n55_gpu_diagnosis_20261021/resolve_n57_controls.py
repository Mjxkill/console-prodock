#!/usr/bin/env python3
"""Resolve GPU controls from semantic register anchors after isolated USB synthesis.

No place/route, source mutation or hardware. Compare complete selected modules,
then structurally fingerprint control cones down to named sequential/input
boundaries. All scalar/vector CE and clock loads are included.
"""
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path
import re
from audit_gpu_control_inventory import bit_expander, primitive_directions, pin_base, CLOCK
from prove_geometry_controls import parameters
from build_timing_placement import HERE, ROOT, SHA_NET, sha

PARENT=ROOT/'tang/impl/console_neo_n56r3'
CANDIDATE=ROOT/'tang/impl/console_neo_n57_usb35_syn'
OUT=HERE/'n57_controls'


def cells(text):
    """Preserve escaped instance AND port names, including embedded dots."""
    norm=lambda value:re.sub(r'\s+','',value).removeprefix('\\')
    return {norm(name):dict(kind=kind,pins={norm(pin):norm(net) for pin,net in
        re.findall(r'\.(\\\S+|\w+)\s*\(([^()]*)\)',body)})
        for kind,name,body in re.findall(r'^\s*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S)
        if kind!='module'}
# Anchor names are semantic register names, never anonymous nNN driver names.
TARGETS=(
    ('captured_command','geometry','captured_command_0_s0','CE',312,True),
    ('held_snapshot','debug','held_0_s0','CE',283,True),
    ('memory_alive','debug','mem_up_1_s0','Q',2,True),
    ('material','geometry','material_0_s0','CE',256,True),
    ('camera','geometry','near_z_0_s0','CE',204,True),
    ('face','geometry','face_0_s0','CE',246,True),
    ('snapshot_bus','debug','snapshot_0_s0','CE',315,False),
    ('pending','accel','v1_pending_s2','Q',4,False),
    ('pending_inverse','accel','v1_tx_data_0_s0','CE',317,False),
)


def global_connections(path,targets):
    raw=path.read_text()
    bodies={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',raw,re.M|re.S)}
    models={}
    directions=primitive_directions()
    result={net:dict(drivers=[],loads=[]) for net in targets}

    def model(kind):
        if kind not in models:
            body=bodies[kind]
            ports={}
            for hi,lo,name in re.findall(r'^(?:input|output|inout)\s+(?:\[(\d+):(\d+)\]\s*)?(\\\S+|\w+)\s*;',body,re.M):
                name=name.removeprefix('\\')
                ports[name]=[name] if not hi else [f'{name}[{i}]' for i in range(int(hi),int(lo)-1,-1)]
                body+='\nwire '+(f'[{hi}:{lo}] ' if hi else '')+('\\'+name+' ' if '/' in name else name)+';\n'
            models[kind]=(cells(bodies[kind]),ports,bit_expander(body))
        return models[kind]

    def walk(kind,hierarchy,portmap):
        cc,_,expand=model(kind)
        def absolute(bit):
            if bit in ('VCC','GND'):
                return bit
            return portmap.get(bit,hierarchy+'/'+bit if hierarchy else bit)
        for name,cell in cc.items():
            instance=hierarchy+'/'+name if hierarchy else name
            connections={port:[absolute(bit) for bit in expand(expression)] for port,expression in cell['pins'].items()}
            if cell['kind'] in bodies:
                if not any(t.startswith(instance+'/') for t in targets) and not any(t in targets for bits in connections.values() for t in bits):
                    continue
                _,ports,_=model(cell['kind'])
                child={}
                for port,bits in connections.items():
                    if not bits:
                        continue
                    if port not in ports or len(ports[port])!=len(bits):
                        raise ValueError('Hierarchical port width mismatch: '+instance+'.'+port)
                    child.update(zip(ports[port],bits))
                walk(cell['kind'],instance,child)
                continue
            for port,bits in connections.items():
                for i,net in enumerate(bits):
                    if net not in targets:
                        continue
                    direction=directions.get(cell['kind'],{}).get(port)
                    if direction not in ('input','output'):
                        raise ValueError('Unresolved primitive on control net: '+instance+'.'+port)
                    vector=len(bits)>1 or cell['pins'][port].startswith('{')
                    pin=f'{port}[{len(bits)-1-i}]' if vector else port
                    result[net]['drivers' if direction=='output' else 'loads'].append((instance,cell['kind'],pin))
    walk('console_neo','',{})
    return result


class IndexedModule:
    def __init__(self,body):
        self.body=body
        self.cells=cells(body)
        self.params=parameters(body)
        expand=bit_expander(body)
        directions=primitive_directions()
        self.loads,self.drivers=defaultdict(list),defaultdict(list)
        self.bits={}
        self.input_bits=set()
        for expression in re.findall(r'^input\s+([^;]+);',body,re.M):
            declaration=re.sub(r'^\[[^]]+\]\s*','',expression).strip()
            # The netlist uses one name per input declaration.
            self.input_bits.update(expand(declaration))
        for name,cell in self.cells.items():
            if cell['kind'] not in directions:
                # A containing module can instantiate other modules. Its
                # primitive anchors still have complete primitive metadata.
                continue
            for port,expression in cell['pins'].items():
                bits=expand(expression)
                vector=len(bits)>1 or expression.startswith('{')
                self.bits[name,port]=bits
                direction=directions[cell['kind']].get(port)
                if direction not in ('input','output','inout'):
                    raise ValueError('Unknown primitive pin '+cell['kind']+'.'+port)
                for i,net in enumerate(bits):
                    pin=f'{port}[{len(bits)-1-i}]' if vector else port
                    (self.drivers if direction=='output' else self.loads)[net].append((name,cell['kind'],pin))
        self.directions=directions

    def cone(self,net,seen=None):
        if net in ('VCC','GND'):
            return ('constant',net)
        found=self.drivers[net]
        if not found:
            if net not in self.input_bits:
                raise ValueError('Undriven cone boundary '+net)
            return ('input',net)
        if len(found)!=1:
            raise ValueError('Ambiguous driver '+net)
        name,kind,outpin=found[0]
        if not kind.startswith(('LUT','MUX')) and kind not in ('INV','ALU'):
            return ('sequential_or_hard_boundary',name,kind,outpin)
        seen=set() if seen is None else seen
        if net in seen:
            raise ValueError('Combinational loop in control cone')
        inputs=[]
        for port in sorted(self.cells[name]['pins']):
            if self.directions[kind][port]=='input':
                inputs.append((port,[self.cone(bit,seen|{net}) for bit in self.bits[name,port]]))
        return ('combinational',kind,outpin,self.params.get(name,{}),inputs)


def modules_for(path):
    raw=path.read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',raw,re.M|re.S)}
    top=cells(modules['console_neo'])
    accel_name=top['u_accel']['kind']
    debug_name=top['u_gpu_debug']['kind']
    accel=cells(modules[accel_name])
    geometry_name=accel['u_v1']['kind']
    named={'accel':accel_name,'geometry':geometry_name,'debug':debug_name}
    return named,{label:modules[name] for label,name in named.items()},top,accel


def main():
    if OUT.exists():
        raise ValueError('Existing evidence must not be overwritten')
    completed=json.loads((CANDIDATE/'usb_synthesis_result.json').read_text())
    new_path=CANDIDATE/'impl/gwsynthesis/console_neo.vg'
    if completed['status']!='SYNTHESIZED_NOT_ROUTED' or sha(new_path)!=completed['netlist_sha256']:
        raise ValueError('Complete isolated USB synthesis required')
    if sha(PARENT/'console_neo.vg')!=SHA_NET:
        raise ValueError('Changed reference netlist')
    old_names,old_bodies,old_top,old_accel=modules_for(PARENT/'console_neo.vg')
    new_names,new_bodies,new_top,new_accel=modules_for(new_path)
    old={k:IndexedModule(v) for k,v in old_bodies.items()}
    new={k:IndexedModule(v) for k,v in new_bodies.items()}
    module_comparison={label:dict(old_module=old_names[label],new_module=new_names[label],
        byte_identical=old_bodies[label]==new_bodies[label],
        old_sha256=hashlib.sha256(old_bodies[label].encode()).hexdigest(),
        new_sha256=hashlib.sha256(new_bodies[label].encode()).hexdigest()) for label in old}
    entries=[]
    for label,module,anchor,pin,count,required in TARGETS:
        stages={}
        for stage,models,top,accel in [('parent',old,old_top,old_accel),('candidate',new,new_top,new_accel)]:
            indexed=models[module]
            if anchor not in indexed.cells:
                raise ValueError('Semantic anchor absent: '+anchor)
            net=indexed.cells[anchor]['pins'][pin]
            if net not in indexed.drivers or len(indexed.drivers[net])!=1:
                raise ValueError('Control driver absent/ambiguous: '+label)
            loads=sorted(indexed.loads[net])
            if len(loads)!=count or any(CLOCK.fullmatch(pin_base(p)) for _,_,p in loads):
                raise ValueError('Control loads/clock usage differ: '+label+' '+str(len(loads)))
            driver=indexed.drivers[net][0][0]
            hierarchy={'geometry':'u_accel/u_v1','debug':'u_gpu_debug','accel':'u_accel'}[module]
            routed_name=hierarchy+'/'+net
            # A module output is flattened to its connection in the parent.
            if module=='accel' and net in top['u_accel']['pins']:
                routed_name=top['u_accel']['pins'][net]
            cone=indexed.cone(net)
            stages[stage]=dict(net=net,proposed_routed_name=routed_name,driver=driver,
                driver_cell=indexed.cells[driver],driver_parameters=indexed.params.get(driver,{}),
                loads=loads,load_pin_counts=dict(Counter(p for _,_,p in loads)),clock_pin_count=0,
                cone=cone,cone_sha256=hashlib.sha256(json.dumps(cone,sort_keys=True).encode()).hexdigest())
        same_loads=stages['parent']['loads']==stages['candidate']['loads']
        same_cone=stages['parent']['cone']==stages['candidate']['cone']
        entries.append(dict(label=label,required_control=required,anchor=anchor,anchor_pin=pin,
            module=module,same_load_set=same_loads,same_combinational_cone=same_cone,stages=stages))
    # Resolve the exported reset through actual module port connections. Do
    # not assume that its internal alias is accepted by the physical tool.
    reset_stages={}
    for stage,models,top in [('parent',old,old_top),('candidate',new,new_top)]:
        a=models['accel']
        cell=a.cells['engine_resetn_4_s0']
        local=cell['pins']['Q']
        external=top['u_accel']['pins'].get(local)
        if not external:
            raise ValueError('Reset4 output alias missing')
        reset_stages[stage]=dict(internal_alias='u_accel/'+local,top_alias=external,
            driver='u_accel/engine_resetn_4_s0',cell=cell,parameters=a.params['engine_resetn_4_s0'])
    globals_by_stage={}
    for stage,path in [('parent',PARENT/'console_neo.vg'),('candidate',new_path)]:
        nets={e['stages'][stage]['proposed_routed_name'] for e in entries}|{reset_stages[stage]['top_alias']}
        globals_by_stage[stage]=global_connections(path,nets)
    for entry in entries:
        names={s:entry['stages'][s]['proposed_routed_name'] for s in ('parent','candidate')}
        old_connections=globals_by_stage['parent'][names['parent']]
        new_connections=globals_by_stage['candidate'][names['candidate']]
        # Global load set equality is independent of anonymous control-net names.
        same=all(sorted(old_connections[k])==sorted(new_connections[k]) for k in ('drivers','loads'))
        expected_count=8 if entry['label']=='pending' else next(t[4] for t in TARGETS if t[0]==entry['label'])
        if len(new_connections['loads'])!=expected_count:
            raise ValueError('Global load count changed: '+entry['label'])
        if any(CLOCK.fullmatch(pin_base(p)) for _,_,p in new_connections['loads']):
            raise ValueError('A proposed global control feeds a clock')
        entry.update(global_connections=dict(parent=old_connections,candidate=new_connections),
            same_global_connections=same,global_load_count=expected_count)
    reset_connections={s:globals_by_stage[s][reset_stages[s]['top_alias']] for s in ('parent','candidate')}
    # Synthesized reset4 has eight loads. The reference routed netlist has
    # nine after the router splits n1617_s2 into LUT1 plus an inverter.
    if any(len(c['loads'])!=8 for c in reset_connections.values()):
        raise ValueError('Reset4 direct fanout changed')
    same_reset=reset_stages['parent']==reset_stages['candidate'] and reset_connections['parent']==reset_connections['candidate']
    passed=all(e['same_load_set'] and e['same_combinational_cone'] and e['same_global_connections'] for e in entries) and same_reset
    OUT.mkdir()
    result=dict(passed=passed,scope=__doc__,modules=module_comparison,controls=entries,
        reset4=dict(stages=reset_stages,global_connections=reset_connections,unchanged=same_reset,
            synthesis_direct_load_count=8,reference_post_pnr_direct_load_count=9),
        hardware_access=False,route_launched=False,
        sha256={str(p):sha(p) for p in [Path(__file__),PARENT/'console_neo.vg',new_path,
            CANDIDATE/'usb_synthesis_result.json',HERE/'audit_gpu_control_inventory.py',
            HERE/'prove_geometry_controls.py']},
        limitations=['Combinational cone fingerprints stop at named sequential and module-input boundaries; they are not whole-design formal equivalence.',
                    'Candidate hierarchy names require route-time resolution and post-PnR global-route audit.',
                    'Optional controls are identified only; their inclusion in a candidate requires separate review.'])
    (OUT/'resolution.json').write_text(json.dumps(result,indent=2)+'\n')
    fragment='\n'.join(f'CLOCK_LOC "{e["stages"]["candidate"]["proposed_routed_name"]}" LOCAL_CLOCK;'
        for e in entries)+'\n'
    (OUT/'proposed_controls.cst').write_text(fragment)
    print(json.dumps(dict(passed=passed,modules=module_comparison,
        controls=[dict(label=e['label'],same_load_set=e['same_load_set'],same_cone=e['same_combinational_cone'],
            routed_name=e['stages']['candidate']['proposed_routed_name']) for e in entries]),indent=2))
    if not passed:
        raise SystemExit('Control resolution differs; no constraint integration authorized')


if __name__=='__main__':
    main()
