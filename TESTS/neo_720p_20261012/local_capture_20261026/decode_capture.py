#!/usr/bin/env python3
"""Interpret a frozen NCP1 report; never treat an absent capture as PASS."""
import argparse
import json

def decode(value,expected_opcode,epoch):
    if not 0<=value<1<<64 or not 0<=expected_opcode<256 or epoch not in (0,1):
        raise ValueError('Invalid report/opcode/epoch')
    if value>>56!=0xc1:raise ValueError('NCP1 signature missing')
    if (value>>54)&1!=epoch:raise ValueError('Report belongs to another arm epoch')
    at=value&0xffffff;after=(value>>24)&0xffffff;flags=(value>>48)&0xff
    def sample(v):
        return dict(d=v&255,q=(v>>8)&255,ce=(v>>16)&1,reset=(v>>17)&1,
                    start=(v>>18)&1,idle=(v>>19)&1,decode_wait=(v>>20)&1,
                    decode=(v>>21)&1,bad=(v>>22)&1,done=(v>>23)&1)
    r=dict(at=sample(at),after=sample(after),flags=flags,complete=False,
           limitation='Opcode bits31:24 only; no subcycle timing or whole-packet qualification')
    if flags&3!=3 or not flags&4 or flags&8:
        r['finding']='NO_COMPLETE_CAPTURE';return r
    a,b=r['at'],r['after'];r['complete']=True
    if a['start']!=1:raise ValueError('Trigger flag inconsistent')
    expected_q=0 if a['reset'] else a['d'] if a['ce'] else a['q']
    r['expected_q']=expected_q;r['register_rule_matches']=b['q']==expected_q
    if a['d']!=expected_opcode:r['finding']='WRONG_OPCODE_AT_D'
    elif a['reset']:r['finding']='RESET_ACTIVE_AT_CAPTURE'
    elif not a['ce']:r['finding']='CAPTURE_ENABLE_ABSENT'
    elif b['q']!=a['d']:r['finding']='OPCODE_NOT_CAPTURED'
    else:r['finding']='OPCODE_CAPTURE_CONSISTENT'
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report',type=lambda x:int(x,0))
    p.add_argument('--opcode',required=True,type=lambda x:int(x,0));p.add_argument('--epoch',required=True,type=int)
    a=p.parse_args();print(json.dumps(decode(a.report,a.opcode,a.epoch),indent=2))
