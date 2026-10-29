#!/usr/bin/env python3
"""Boolean equivalence of the mapped native VALID and pending/ACK logic."""
from functools import lru_cache
import json
import re
from sympy import Symbol, And, Or, Not, Xor, true, false
from sympy.logic.inference import satisfiable
from prepare_memory_observer import HERE, PARENT, sha, block, pins

def main():
    net=PARENT/'console_neo.vg';text=net.read_text()
    proofs=[]
    def cone(mod):
        b=block(text,mod);drivers={}
        for m in re.finditer(r'^\s*(\w+)\s+(\\?\S+)\s+\((.*?)\);',b,re.M|re.S):
            ps=dict(re.findall(r'\.(\w+)\(([^()]*)\)',m[3]));q=ps.get('F',ps.get('Q',''))
            if q:drivers[q]=(m[1],m[2],ps)
        def leaf(n):return Symbol(mod+'/'+n)
        @lru_cache(None)
        def evaluate(n):
            if n=='VCC':return true
            if n=='GND':return false
            if n not in drivers:return leaf(n)
            typ,name,ps=drivers[n]
            if typ.startswith('DFF'):return leaf(n)
            assert re.fullmatch(r'LUT[1-4]',typ),(n,typ)
            p=re.search(r'defparam '+re.escape(name)+r"\.INIT\s*=\s*(\d+)'h([0-9a-fA-F]+);",b);assert p,name
            count=int(typ[-1]);assert int(p[1])==1<<count
            value=int(p[2],16);inputs=[evaluate(ps['I'+str(i)]) for i in range(count)]
            return Or(*[And(*[x if k>>i&1 else Not(x) for i,x in enumerate(inputs)]) for k in range(1<<count) if value>>k&1])
        return b,leaf,evaluate
    def prove(name,actual,expected):
        different=Xor(actual,expected)
        counterexample=satisfiable(different,algorithm='dpll2')
        r=dict(name=name,variables=len(different.free_symbols),equivalent=counterexample is False)
        if counterexample is not False:r['counterexample']={str(k):bool(v) for k,v in counterexample.items()}
        proofs.append(r);print(json.dumps(r),flush=True)
    b,L,E=cone('gpu_v1')
    alpha_256=And(L('alpha[8]'),*[Not(L(f'alpha[{i}]')) for i in range(8)])
    background=Or(Not(alpha_256),L('flags[5]'),And(L('flags[0]'),L('tex_argb')))
    issue=Or(And(L('state[14]'),background),And(L('state[16]'),L('flags[1]')),
        And(L('state[28]'),L('chunk_dirty')),L('state[30]'),
        And(L('state[36]'),L('clear_flags[0]')),And(L('state[38]'),L('clear_flags[1]')))
    wait=Or(*[L(f'state[{i}]') for i in (15,17,29,31,37,39)])
    ready=And(L('v1_accepted'),L('v1_select'),Not(L('fetch_valid')))
    q=L('native_valid');ff=pins(b,'native_valid_s1')
    actual=Or(And(E(ff['CE']),E(ff['D'])),And(Not(E(ff['CE'])),q))
    prove('native_issue',E('native_issue'),issue)
    prove('native_valid_next_without_reset',actual,Or(issue,And(q,wait,Not(ready))))
    b,L,E=cone('gpu_accel')
    request=Or(And(L('v1_select'),Or(*[L(n) for n in ('fetch_valid','native_valid','cache_valid','copy_valid')])),
               And(Not(L('v1_select')),L('raster_valid')))
    pending=L('v1_pending');accepted=L('v1_accepted');ready=L('b_grant')
    ff=pins(b,'v1_pending_s2');assert ff['CE']=='VCC'
    prove('pending_next_without_reset',E(ff['D']),Or(And(pending,Not(ready)),And(Not(pending),request,Not(accepted))))
    ff=pins(b,'v1_accepted_s0');assert ff['CE']=='VCC'
    prove('accepted_next_without_reset',E(ff['D']),And(pending,ready))
    out=HERE/'handshake_boolean_proof.json';assert not out.exists()
    r=dict(passed=all(p['equivalent'] for p in proofs),proofs=proofs,method='SAT: XOR of mapped LUT truth tables and RTL next-state equations is unsatisfiable',
        inputs={str(net):sha(net),__file__:sha(__import__('pathlib').Path(__file__))},
        assumptions=['Synchronous reset inactive; flip-flops follow their documented D/CE transition.',
                     'Inputs are arbitrary Boolean values; no one-hot assumption was required.'],
        limits=['No propagation delays, metastability, physical connectivity or clock/reset arrival proof.',
                'Does not prove the complete GPU/arbiter or memory payload addressing.'])
    out.write_text(json.dumps(r,indent=2)+'\n')
    if not r['passed']:raise SystemExit(1)

if __name__=='__main__':main()
