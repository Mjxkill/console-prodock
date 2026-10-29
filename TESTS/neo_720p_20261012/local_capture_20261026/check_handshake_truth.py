#!/usr/bin/env python3
"""Exhaustive bit-parallel truth tables; no SAT search or timing inference."""
from functools import lru_cache
import json
import re
import signal
from pathlib import Path
from prepare_memory_observer import HERE, PARENT, sha, block, pins

def main():
    signal.alarm(60)
    net=PARENT/'console_neo.vg';text=net.read_text();results=[]
    def test(mod,name,roots,reference_leaves,actual,expected,cut=()):
        b=block(text,mod);drivers={}
        for m in re.finditer(r'^\s*(\w+)\s+(\\?\S+)\s+\((.*?)\);',b,re.M|re.S):
            ps=dict(re.findall(r'\.(\w+)\(([^()]*)\)',m[3]));q=ps.get('F',ps.get('Q',''))
            if q:drivers[q]=(m[1],m[2],ps)
        leaves=set(reference_leaves)
        @lru_cache(None)
        def collect(n):
            if n in ('VCC','GND'):return
            if n in cut or n not in drivers or drivers[n][0].startswith('DFF'):
                leaves.add(n);return
            typ,inst,ps=drivers[n];assert re.fullmatch(r'LUT[1-4]',typ),(n,typ)
            for i in range(int(typ[-1])):collect(ps['I'+str(i)])
        for n in roots:collect(n)
        names=sorted(leaves);assert len(names)<=24
        combinations=1<<len(names);mask=(1<<combinations)-1;bytes_count=(combinations+7)//8
        values={}
        for i,n in enumerate(names):
            if i<3:data=bytes([((0xaa,0xcc,0xf0)[i])])*bytes_count
            else:
                run=1<<(i-3);data=(bytes(run)+b'\xff'*run)*(bytes_count//(2*run))
            values[n]=int.from_bytes(data,'little')&mask
        @lru_cache(None)
        def E(n):
            if n=='VCC':return mask
            if n=='GND':return 0
            if n in values:return values[n]
            typ,inst,ps=drivers[n];count=int(typ[-1])
            p=re.search(r'defparam '+re.escape(inst)+r"\.INIT\s*=\s*(\d+)'h([0-9a-fA-F]+);",b);assert p
            assert int(p[1])==1<<count
            init=int(p[2],16);args=[E(ps['I'+str(i)]) for i in range(count)];answer=0
            for index in range(1<<count):
                if not init>>index&1:continue
                term=mask
                for i,x in enumerate(args):term &= x if index>>i&1 else ~x
                answer |= term
            return answer
        got=actual(E)&mask;wanted=expected(E)&mask;difference=got^wanted
        r=dict(name=name,variables=len(names),combinations=combinations,equivalent=difference==0,
            leaves=names,cut_signals=list(cut))
        if difference:
            first=(difference&-difference).bit_length()-1
            r['counterexample']={n:bool(first>>i&1) for i,n in enumerate(names)}
        results.append(r);print(json.dumps({k:v for k,v in r.items() if k!='leaves'}),flush=True)
    def OR(E,names):
        result=0
        for n in names:result |= E(n)
        return result
    def issue(E):
        alpha256=E('alpha[8]')&~OR(E,[f'alpha[{i}]' for i in range(8)])
        background=~alpha256|E('flags[5]')|(E('flags[0]')&E('tex_argb'))
        return (E('state[14]')&background)|(E('state[16]')&E('flags[1]'))|(
            E('state[28]')&E('chunk_dirty'))|E('state[30]')|(
            E('state[36]')&E('clear_flags[0]'))|(E('state[38]')&E('clear_flags[1]'))
    refs=[f'alpha[{i}]' for i in range(9)]+[f'state[{i}]' for i in (14,16,28,30,36,38)]+[
        'flags[0]','flags[1]','flags[5]','tex_argb','chunk_dirty','clear_flags[0]','clear_flags[1]']
    test('gpu_v1','native_issue',['native_issue'],refs,lambda E:E('native_issue'),issue)
    assert results[-1]['equivalent'],'Do not use an unproved cut signal'
    b=block(text,'gpu_v1');ff=pins(b,'native_valid_s1')
    refs=['native_issue','native_valid','fetch_valid','v1_accepted','v1_select']+[f'state[{i}]' for i in (15,17,29,31,37,39)]
    test('gpu_v1','native_valid_next_without_reset',[ff['CE'],ff['D']],refs,
        lambda E:(E(ff['CE'])&E(ff['D']))|(~E(ff['CE'])&E('native_valid')),
        lambda E:E('native_issue')|(E('native_valid')&OR(E,[f'state[{i}]' for i in (15,17,29,31,37,39)])&
            ~(E('v1_accepted')&E('v1_select')&~E('fetch_valid'))),cut=('native_issue',))
    b=block(text,'gpu_accel');pending=pins(b,'v1_pending_s2');accepted=pins(b,'v1_accepted_s0')
    assert pending['CE']==accepted['CE']=='VCC'
    refs=['v1_select','native_valid','copy_valid','cache_valid','fetch_valid','raster_valid','v1_pending','v1_accepted','b_grant']
    def pending_next(E):
        request=(E('v1_select')&OR(E,['native_valid','copy_valid','cache_valid','fetch_valid']))|(~E('v1_select')&E('raster_valid'))
        return (E('v1_pending')&~E('b_grant'))|(~E('v1_pending')&request&~E('v1_accepted'))
    test('gpu_accel','pending_next_without_reset',[pending['D']],refs,lambda E:E(pending['D']),pending_next)
    test('gpu_accel','accepted_next_without_reset',[accepted['D']],['v1_pending','b_grant'],lambda E:E(accepted['D']),lambda E:E('v1_pending')&E('b_grant'))
    result=dict(passed=all(r['equivalent'] for r in results),proofs=results,
        method='Exhaustive bit-parallel truth-table equality; native_issue cut used only after separate exhaustive equivalence',
        inputs={str(net):sha(net),str(Path(__file__)):sha(Path(__file__))},
        assumptions=['Reset inactive; documented D/CE flip-flop behavior.', 'Arbitrary Boolean leaves, no one-hot assumption.'],
        limits=['No clock, propagation delay, physical connectivity or metastability model.',
                'No complete GPU or memory-address/payload qualification.'])
    out=HERE/'handshake_truth_proof.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
