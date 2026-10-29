#!/usr/bin/env python3
"""Prove the one reset-inverter split flagged by the strict observer audit.

Preserve the original FAIL report. This is Boolean equivalence only; STA and
physical reset distribution remain separate mandatory checks.
"""
import json
from pathlib import Path
import re
import sys
from prepare_scan_observer import ROOT,HERE,sha
from route_scan_observer_placement import OUT,NETSHA
sys.path.insert(0,str(HERE.parent/'n55_gpu_diagnosis_20261021'))
from build_local_controls import cells

def main():
    initial=OUT/'scan_observer_audit.json'
    original=json.loads(initial.read_text())
    assert original['passed'] is False
    assert original['errors']==['Observer register function/clock/reset/init changed after synthesis']
    assert sha(OUT/'console_neo.vg')==NETSHA
    for name,digest in original['sha256'].items():assert sha(Path(name))==digest
    text=(OUT/'console_neo.vg').read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    top=cells(modules['console_neo'])
    mon=cells(modules[top['u_scan_observe']['kind']])
    assert mon['n6_s2']==dict(kind='INV',pins=dict(O='n6_6',I='vid_hrstn'))
    assert top['u_scan_observe']['pins']['n6_6']=='n6_6'
    assert top['u_scan_observe']['pins']['vid_hrstn']=='vid_hrstn'
    routed=cells((OUT/'impl/pnr/console_neo.vo').read_text())
    old='n6_6';new='u_scan_observe/gowin_split_inv_from_n6_s2_onet'
    found=[(name,c) for name,c in routed.items() if c['pins'].get('O')==new]
    assert found==[('u_scan_observe/gowin_split_inv_from_n6_s2',dict(kind='INV',pins=dict(I='vid_hrstn',O=new)))]
    changed_pins={}
    assert len(original['register_changes'])==374
    for entry in original['register_changes']:
        before,after=entry['before'],entry['after']
        assert before['kind']==after['kind'] and entry['before_init']==entry['after_init']
        wanted=dict(before['pins'])
        different=[pin for pin in wanted if wanted[pin]!=after['pins'].get(pin)]
        assert len(different)==1 and different[0] in ('RESET','CLEAR')
        pin=different[0]
        assert wanted[pin]==old and after['pins'][pin]==new
        wanted[pin]=new
        assert wanted==after['pins']
        changed_pins[pin]=changed_pins.get(pin,0)+1
    result=dict(passed=True,scope='Logical observer register equivalence, allowing exactly one proven INV copy on reset',
        reset_function='!vid_hrstn',source_driver=mon['n6_s2'],routed_driver=found[0],
        register_counts=original['register_counts'],reset_alias_count=changed_pins,
        all_other_register_fields_identical=True,original_fail_preserved=str(initial),
        controls=original['controls'],global_scanout_ce=original['global_scanout_ce'],
        sha256={str(p):sha(p) for p in (initial,Path(__file__),OUT/'console_neo.vg',OUT/'impl/pnr/console_neo.vo')},
        hardware_access=False,timing_qualification='FAIL',
        limits='No waiver for timing, polarity changes, clock changes, different reset sources or other register changes.')
    with (OUT/'scan_observer_reset_alias_proof.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ('passed','reset_alias_count','all_other_register_fields_identical','timing_qualification')},indent=2))

if __name__=='__main__':main()
