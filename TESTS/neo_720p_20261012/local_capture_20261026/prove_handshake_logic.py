#!/usr/bin/env python3
"""Boolean equivalence of the mapped native VALID and pending/ACK logic."""
from functools import lru_cache
import json
import re
import signal
import faulthandler
from sympy import Symbol, And, Or, Not, Xor, true, false
from sympy.logic.inference import satisfiable
from prepare_memory_observer import HERE, PARENT, sha, block, pins

def main():
    signal.alarm(60)
    faulthandler.dump_traceback_later(10)
    net=PARENT/'console_neo.vg';text=net.read_text()
    proofs=[]
    clauses=[]
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
            output=leaf(n)
            for k in range(1<<count):
                clauses.append(Or(output if value>>k&1 else Not(output),
                    *[Not(x) if k>>i&1 else x for i,x in enumerate(inputs)]))
            return output
        return b,leaf,evaluate
    def prove(name,actual,expected):
        print('Preparing SAT '+name,flush=True)
        different=Xor(actual,expected)
        local=[]
        @lru_cache(None)
        def encode(expr):
            if expr in (true,false) or isinstance(expr,Symbol):return expr
            if expr.func is Not:return Not(encode(expr.args[0]))
            args=[encode(x) for x in expr.args]
            z=Symbol('tseitin_'+str(len(local)))
            if expr.func is And:
                local.extend(Or(Not(z),x) for x in args)
                local.append(Or(z,*[Not(x) for x in args]))
            elif expr.func is Or:
                local.extend(Or(z,Not(x)) for x in args)
                local.append(Or(Not(z),*args))
            elif expr.func is Xor:
                assert len(args)==2
                a,b=args
                local.extend([Or(Not(z),a,b),Or(Not(z),Not(a),Not(b)),
                              Or(z,Not(a),b),Or(z,a,Not(b))])
            else:raise ValueError(expr.func)
            return z
        miter=encode(different)
        formula=And(*clauses,*local,miter)
        print('Solving SAT '+name+' clauses='+str(len(clauses)+len(local)+1),flush=True)
        counterexample=satisfiable(formula,algorithm='dpll2')
        r=dict(name=name,variables=len(formula.free_symbols),clauses=len(clauses)+len(local)+1,equivalent=counterexample is False)
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
    clauses=[]
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
    faulthandler.cancel_dump_traceback_later()

if __name__=='__main__':main()
