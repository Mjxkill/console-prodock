#!/usr/bin/env python3
"""Prove the frozen N56 CAMERA capture-enable cone; never build/access hardware."""
from collections import Counter
import json
import re
from pathlib import Path
from build_local_controls import cells
from build_timing_placement import ROOT, HERE, sha, initial_values, SHA_NET

BUILD = ROOT/'tang/impl/console_neo_n56r3'
NET = 'u_accel/u_v1/n57378_3'
COUNTS = dict(near_z=32, far_z=32, fx=32, fy=32, cx=16, cy=16, width=16, height=16, camera_bad=6)


def prove():
    vg = BUILD/'console_neo.vg'
    if sha(vg) != SHA_NET:
        raise ValueError('Unexpected synthesis netlist')
    text = vg.read_text()
    modules = {m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    top = cells(modules['console_neo'])
    if cells(modules[top['u_accel']['kind']])['u_v1']['kind'] != 'gpu_geometry':
        raise ValueError('Geometry hierarchy differs')
    stages = {}
    for stage,body,prefix in [('synthesis',modules['gpu_geometry'],''),
                              ('routed',(BUILD/'impl/pnr/console_neo.vo').read_text(),'u_accel/u_v1/')]:
        cc = cells(body)
        target,driver = prefix+'n57378_3',prefix+'n57378_s0'
        found = [n for n,c in cc.items() if any(c['pins'].get(p)==target for p in ('F','Q','O'))]
        if found != [driver] or cc[driver]['kind'] != 'LUT3' or initial_values(body)[driver] != "8'h80":
            raise ValueError('CAMERA capture driver differs')
        expected_pins = dict(I0='gpu_debug_state[46]' if prefix else 'gpu_debug_state_46',
            I1=prefix+'state[67]',I2=prefix+'n57378_4',F=target)
        if cc[driver]['pins'] != expected_pins:
            raise ValueError('CAMERA capture driver connections differ')
        loads = [dict(instance=n,primitive=c['kind'],pin=p) for n,c in cc.items()
                 for p,v in c['pins'].items() if v==target and p not in ('F','Q','O')]
        expected = {prefix+f'{field}_{i}_s0' for field,count in COUNTS.items() for i in range(count)}
        if {x['instance'] for x in loads} != expected or len(loads)!=198:
            raise ValueError('CAMERA register set differs')
        if any(x['pin']!='CE' or x['primitive']!='DFFRE' for x in loads):
            raise ValueError('Unexpected load type/pin')
        decode = [dict(instance=n,**c) for n,c in cc.items()
                  if any(c['pins'].get(p)==prefix+'n57378_4' for p in ('F','Q','O'))]
        stages[stage] = dict(driver=driver,primitive='LUT3',init="8'h80",pins=cc[driver]['pins'],
            loads=loads,decode_drivers=decode)
    table = (BUILD/'impl/pnr/console_neo.rpt.txt').read_text()
    if not re.search(r'^\s*'+re.escape(NET)+r'\s*\|\s*LW\s*\|',table,re.M):
        raise ValueError('Expected LW route missing')
    paths = [vg,BUILD/'impl/pnr/console_neo.vo',BUILD/'impl/pnr/console_neo.rpt.txt',
             BUILD/'source/tang/rtl/video/gpu_geometry.v',Path(__file__)]
    return dict(passed=True,hardware_access=False,compilation=False,net=NET,current_route='LW',
        proposed_constraint=f'CLOCK_LOC "{NET}" LOCAL_CLOCK;',stages=stages,
        field_counts=COUNTS,loads=198,clock_loads=0,
        sha256={str(p):sha(p) for p in paths},
        interpretation='Missing CAMERA capture would retain old focal lengths/viewport; zero fx/fy can make CAM_DIV invalid. This is a hardware hypothesis, not proof of missing capture.',
        limitations=['N56r3 still fails reset4 routing audit, so the LW CAMERA net is not yet the only hardware difference.',
                     'No new constraint is added to any build by this proof.',
                     'Any future candidate needs full timing/structural audit and command-by-command hardware comparison.'])


if __name__ == '__main__':
    result=prove()
    out=HERE/'viewport_control_proof.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),passed=result['passed'],loads=result['loads'],fields=COUNTS),indent=2))
