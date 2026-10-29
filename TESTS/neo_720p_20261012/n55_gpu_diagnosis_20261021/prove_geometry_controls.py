#!/usr/bin/env python3
"""Exact N56r3 CAMERA/FACE driver and scalar/vector CE proof, no build/hardware."""
import json
import re
from collections import Counter
from pathlib import Path
from audit_gpu_control_inventory import bit_expander, primitive_directions, CLOCK, pin_base
from build_local_controls import cells
from build_timing_placement import HERE, ROOT, SHA_NET, sha, initial_values

BUILD = ROOT/'tang/impl/console_neo_n56r3'
CAMERA_FIELDS = dict(near_z=32,far_z=32,fx=32,fy=32,cx=16,cy=16,width=16,height=16,camera_bad=6)
CONTROLS = {
    'n57378_3': dict(label='CAMERA', driver='n57378_s0', kind='LUT3', init="8'h80",
        flops={f'{field}_{i}_s0' for field,count in CAMERA_FIELDS.items() for i in range(count)},
        dsp={'n55271_0_s':'CE[1]','n55272_0_s':'CE[1]','n169811_0_s':'CE[0]',
             'n169812_0_s':'CE[0]','n170451_0_s':'CE[0]','n170452_0_s':'CE[0]'}),
    'n59467_5': dict(label='FACE', driver='n59467_s1', kind='LUT4', init="16'h8000",
        flops={f'face_{i}_s0' for i in range(256) if not 160<=i<=175},
        dsp={'n1300_s':'CE[1]','n1300_s0':'CE[1]','light_total_0_s':'CE[1]',
             'n5043_s':'CE[0]','n5007_s':'CE[0]','n5025_s':'CE[0]'})}


def parameters(text):
    result={}
    for name,param,value in re.findall(r'^\s*defparam\s+(\\\S+|\w+)\s*\.(\w+)\s*=\s*([^;]+);',text,re.M):
        result.setdefault(name.removeprefix('\\'),{})[param]=value.strip()
    return result


def prove():
    vg=BUILD/'console_neo.vg'
    if sha(vg)!=SHA_NET:
        raise ValueError('Changed synthesis netlist')
    text=vg.read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    top=cells(modules['console_neo'])
    if cells(modules[top['u_accel']['kind']])['u_v1']['kind']!='gpu_geometry':
        raise ValueError('Changed geometry hierarchy')
    directions=primitive_directions()
    stages={}
    for stage,body,prefix in [('synthesis',modules['gpu_geometry'],''),
        ('routed',(BUILD/'impl/pnr/console_neo.vo').read_text(),'u_accel/u_v1/')]:
        cc,expand,params=cells(body),bit_expander(body),parameters(body)
        inits=initial_values(body)
        entries=[]
        for local,spec in CONTROLS.items():
            net,driver=prefix+local,prefix+spec['driver']
            if cc[driver]['kind']!=spec['kind'] or inits[driver]!=spec['init']:
                raise ValueError('Changed driver primitive/INIT: '+net)
            expected_pins=(dict(I0='gpu_debug_state[46]' if prefix else 'gpu_debug_state_46',
                I1=prefix+'state[67]',I2=prefix+'n57378_4',F=net) if spec['label']=='CAMERA' else
                dict(I0='gpu_debug_state[46]' if prefix else 'gpu_debug_state_46',
                I1=prefix+'state[12]',I2='u_accel/v1_select' if prefix else 'v1_select',
                I3='u_accel/v1_rx_valid' if prefix else 'v1_rx_valid',F=net))
            if cc[driver]['pins']!=expected_pins:
                raise ValueError('Changed control driver inputs: '+net)
            found=[];drivers=[]
            for name,c in cc.items():
                for port,expression in c['pins'].items():
                    bits=expand(expression)
                    vector=len(bits)>1 or expression.startswith('{')
                    for index,bit in enumerate(bits):
                        if bit!=net:
                            continue
                        pin=f'{port}[{len(bits)-1-index}]' if vector else port
                        output=directions.get(c['kind'],{}).get(port)=='output'
                        (drivers if output else found).append(dict(instance=name,primitive=c['kind'],pin=pin))
            if drivers!=[dict(instance=driver,primitive=spec['kind'],pin='F')]:
                raise ValueError('Control driver resolution differs: '+net)
            expected={(prefix+n,'CE') for n in spec['flops']}|{(prefix+n,p) for n,p in spec['dsp'].items()}
            if {(x['instance'],x['pin']) for x in found}!=expected or len(found)!=len(expected):
                raise ValueError('Unexpected scalar/vector load set: '+net)
            if any(CLOCK.fullmatch(pin_base(x['pin'])) for x in found):
                raise ValueError('A control drives a clock')
            if any(cc[prefix+n]['kind']!='DFFRE' for n in spec['flops']):
                raise ValueError('Changed flop type')
            entries.append(dict(label=spec['label'],net=net,driver=driver,
                driver_cell=cc[driver],driver_parameters=params[driver],loads=found,
                load_count=len(found),dff_ce_count=len(spec['flops']),dsp_ce_count=len(spec['dsp']),clock_pin_count=0,
                load_cells={name:dict(**cc[name],parameters=params.get(name,{})) for name,_ in sorted(expected)}))
        stages[stage]=entries
    report=(BUILD/'impl/pnr/console_neo.rpt.txt').read_text()
    for local in CONTROLS:
        if not re.search(r'^\s*'+re.escape('u_accel/u_v1/'+local)+r'\s*\|\s*LW\s*\|',report,re.M):
            raise ValueError('Expected parent LW missing')
    paths=[vg,BUILD/'impl/pnr/console_neo.vo',BUILD/'impl/pnr/console_neo.rpt.txt',
        Path(__file__),HERE/'audit_gpu_control_inventory.py']
    return dict(passed=True,stages=stages,hardware_access=False,compilation=False,
        sha256={str(p):sha(p) for p in paths},
        limitations=['A no-SDF simulation passes CAMERA while the board rejects it; this proof establishes the control cone, not the physical cause.',
                     'Direct scalar and vector loads are covered. DSP CE pins can serve internal registers whose uses must be read from their parameters.',
                     'The exact same netlist must be reaudited after PnR; no timing or hardware validation is implied.'])


if __name__=='__main__':
    result=prove()
    path=HERE/'n56r5_control_inventory/geometry_controls_proof.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],path=str(path),
        controls=[{k:e[k] for k in ('label','load_count','dff_ce_count','dsp_ce_count','clock_pin_count')}
                  for e in result['stages']['routed']]),indent=2))
