#!/usr/bin/env python3
"""Compare public post-route USB cells; retain raw differences and provenance.

Names are compared literally. Whitespace is normalized only in connection
expressions; this is not a graph equivalence proof or a physical route match.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BUILDS = {'g22':ROOT/'tang/impl/gpu_geometry_g22r0',
          'r5':ROOT/'tang/impl/prodock_sd_boot_20261029_r5'}
CELL = re.compile(r'^([A-Z][A-Z0-9_]*)\s+(\\\S+|\w+)\s+\(\s*(.*?)\)\s*;', re.M|re.S)
PARAM = re.compile(r'^defparam\s+(\\\S+|\w+)\s*\.(\w+)\s*=\s*([^;]+);', re.M)
SPECIAL = {'PLL','CLKDIV','IDES8','IDES16','OSER16','IBUF','IOBUF','ELVDS_IOBUF','TBUF','DHCE'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(name):
    return 'usb' in name.lower() or name.startswith(('\\u_pll_f/', '\\u_pll_b/'))


def parse(text):
    cells = {}
    for kind, name, body in CELL.findall(text):
        assert name not in cells, name
        cells[name] = {'kind':kind, 'ports':{k:re.sub(r'\s+','',v)
                         for k,v in re.findall(r'\.(\w+)\(\s*(.*?)\s*\)',body)}, 'params':{}}
    for name, key, value in PARAM.findall(text):
        if name in cells:
            assert key not in cells[name]['params'], (name,key)
            cells[name]['params'][key] = value.strip()
    return cells


def changed(a,b):
    return {k:[a.get(k),b.get(k)] for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)}


def main():
    all_cells = {}; inputs = {}; raw = {}
    for label, build in BUILDS.items():
        vo = next((build/'impl/pnr').glob('*.vo'))
        raw[label] = vo.read_text()
        inputs[label] = {'vo':str(vo.relative_to(ROOT)), 'sha256':sha(vo)}
        all_cells[label] = parse(raw[label])
    cells = {label:{n:c for n,c in cs.items() if selected(n)} for label,cs in all_cells.items()}
    a,b = cells['g22'],cells['r5']; diffs=[]; i3=[]
    for name in sorted(a.keys()&b.keys()):
        if a[name]==b[name]:continue
        x,y = a[name],b[name]
        ports,params = changed(x['ports'],y['ports']),changed(x['params'],y['params'])
        diff = {'name':name, 'kind':[x['kind'],y['kind']], 'ports':ports, 'params':params}
        # Keep separate; official ALU model, not this condition, establishes
        # whether an I3-only difference affects the selected arithmetic mode.
        if x['kind']==y['kind']=='ALU' and set(ports)=={'I3'} and not params:
            i3.append({'name':name,'mode':x['params'].get('ALU_MODE'),'I3':ports['I3']})
        else:diffs.append(diff)
    missing=sorted(a.keys()-b.keys());added=sorted(b.keys()-a.keys())
    critical={label:{n:c for n,c in cs.items() if c['kind'] in SPECIAL} for label,cs in cells.items()}
    critical_changes=[d for d in diffs if d['name'] in critical['g22'] or d['name'] in critical['r5']]
    # Include changed blocks plus their direct combinational drivers so an
    # independent reviewer can inspect actual renamed nets, not just counts.
    cones={}
    output_ports={'F','O','Q','Q0','Q1','Q2','Q3','SUM','COUT','CLKOUT','CLKOUT0','CLKOUT1','LOCK'}
    for label,cs in all_cells.items():
        names={d['name'] for d in diffs if d['name'] in cs}|set(missing if label=='g22' else added)
        drivers={v:n for n,c in cs.items() for k,v in c['ports'].items() if k in output_ports}
        for _ in range(2):
            parents=set()
            for n in names:
                c=cs[n]
                if c['kind'].startswith('DFF'):continue
                parents.update(drivers[v] for k,v in c['ports'].items() if k not in output_ports and v in drivers)
            names |= parents
        cones[label]={n:cs[n] for n in sorted(names)}
    result={'scope':'literal public post-route USB/PLL graph comparison; not timing or graph equivalence',
        'hardware':False,'inputs':inputs,'cell_counts':{k:len(v) for k,v in cells.items()},
        'kinds':{k:dict(Counter(c['kind'] for c in v.values())) for k,v in cells.items()},
        'missing':missing,'added':added,'changed_count':len(diffs)+len(i3),
        'i3_only_alu_count':len(i3),'i3_modes':dict(Counter(x['mode'] for x in i3)),
        'other_changes':diffs,'critical_changes':critical_changes}
    for filename,data in [('result.json',result),('critical_cells.json',critical),
                          ('changed_cones.json',cones),('i3_only_changes.json',i3)]:
        (OUT/filename).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'counts':result['cell_counts'],'changed':result['changed_count'],
        'i3_modes':result['i3_modes'],'other':len(diffs),'critical_changes':critical_changes},indent=2))


if __name__ == '__main__':main()
