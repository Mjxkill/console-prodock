#!/usr/bin/env python3
"""Mapped helper only: scalar net drivers and combinatorial cycles, no STA."""
from collections import defaultdict
import json
import time
import recipe as r


def inspect(text):
    a=r.modules_api();modules=a.modules(text)
    r.need(set(modules)=={r.TOP},'Unexpected helper hierarchy')
    block=modules[r.TOP];r.need(not a.statements(block,'assign'),'Assignments need explicit support')
    cells=a.instances(block);drivers=defaultdict(list);consumers=[];edges={}
    for name,decl in a.declarations(block).items():
        if decl[0]!='input':continue
        if len(decl)==1:drivers[(name,)].append('input')
        else:
            r.need(len(decl)==6 and decl[1]=='[' and decl[3]==':' and decl[5]==']','Unexpected port range')
            for bit in range(int(decl[4]),int(decl[2])+1):drivers[(name,'[',str(bit),']')].append('input')
    for name,c in cells.items():
        kind=c['kind'];ports=c['ports']
        if kind.startswith('LUT'):
            width=int(kind[3:]);r.need(width in (2,3,4),'Unexpected LUT')
            output=ports['F'];inputs=[ports['I'+str(i)] for i in range(width)]
            edges[output]=inputs
        elif kind=='DFFRE':output=ports['Q'];inputs=[ports[k] for k in ('D','CLK','CE','RESET')]
        elif kind in ('VCC','GND'):output=ports['V' if kind=='VCC' else 'G'];inputs=[]
        elif kind=='GSR':
            r.need(ports=={'GSRI':('VCC',)},'Active/unknown global reset');continue
        else:raise ValueError('Unsupported primitive '+kind)
        drivers[output].append(name)
        consumers.extend((name,p) for p in inputs)
    multiple={''.join(k):v for k,v in drivers.items() if len(v)!=1}
    undriven=[dict(cell=n,net=''.join(k)) for n,k in consumers if k not in drivers]
    visited=set();active=set();cycles=[];depths={}
    def visit(node,path):
        if node in active:cycles.append([''.join(x) for x in path+[node]]);return 0
        if node in visited:return depths.get(node,0)
        active.add(node)
        d=1+max((visit(child,path+[node]) for child in edges.get(node,[]) if child in edges),default=0)
        active.remove(node);visited.add(node);depths[node]=d;return d
    for node in edges:visit(node,[])
    return dict(passed=not multiple and not undriven and not cycles,cells=len(cells),
        combinational_nodes=len(edges),max_lut_depth=max(depths.values()),multiple_drivers=multiple,
        undriven_consumers=undriven,combinational_cycles=cycles,
        limits='Structural scalar mapped connections only; cuts every FF Q, no timing/simulation qualification.')


if __name__=='__main__':
    start=time.monotonic();path=r.HERE/'stage_02/helper'/f'{r.TOP}.vg';s=path.read_text();result=inspect(s)
    # Adversarial controls: feedback into a real LUT, then double-drive a FF Q.
    a=r.modules_api();cells=a.instances(a.modules(s)[r.TOP]);name,c=next((n,c)for n,c in cells.items()if c['kind'].startswith('LUT'))
    first=''.join(c['ports']['I0']);out=''.join(c['ports']['F'])
    changed=c['raw'].replace('.I0('+first+')','.I0('+out+')',1)
    r.need(changed!=c['raw'],'Counterexample construction failed')
    badcycle=inspect(s.replace(c['raw'],changed,1));r.need(badcycle['combinational_cycles'],'Cycle mutant escaped')
    ff=[c for c in cells.values()if c['kind']=='DFFRE'][:2]
    changed=ff[1]['raw'].replace('.Q('+''.join(ff[1]['ports']['Q'])+')','.Q('+''.join(ff[0]['ports']['Q'])+')',1)
    baddrive=inspect(s.replace(ff[1]['raw'],changed,1));r.need(baddrive['multiple_drivers'],'Driver mutant escaped')
    result.update(source_sha256=r.sha(path),negative_controls_detected=['LUT self feedback','FF duplicate driver'],elapsed_seconds=time.monotonic()-start)
    r.save(r.HERE/'HELPER_GRAPH.json',result);print(json.dumps(result,indent=2))
