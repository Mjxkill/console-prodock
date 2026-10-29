#!/usr/bin/env python3
"""Audit completed N56r4 routing and available placement evidence, no hardware."""
from collections import Counter
import json
import re
from pathlib import Path

from build_observer_placement import (
    ROOT, PARENT, NAME, TARGETS, CONTROLS, ADDITION, SHA_NET, SHA_SDC, sha, dump,
)
from build_timing_placement import initial_values
from build_local_controls import cells


def audit():
    build=ROOT/'tang/impl'/NAME
    errors=[]
    original=json.loads((PARENT/'sources.json').read_text())
    manifest=json.loads((build/'sources.json').read_text())
    actual={str(p.relative_to(build/'source')):sha(p) for p in (build/'source').rglob('*') if p.is_file()}
    if actual!=manifest:
        errors.append('Frozen source drift')
    if set(manifest)!=set(original) or sorted(k for k in manifest if manifest[k]!=original[k])!=['tang/boards/neo/neo.cst']:
        errors.append('Unexpected source mutation')
    cst=(build/'source/tang/boards/neo/neo.cst').read_text()
    if cst!=(PARENT/'source/tang/boards/neo/neo.cst').read_text()+ADDITION:
        errors.append('CST differs from reviewed seven placements')
    if sha(build/'console_neo.vg')!=SHA_NET or sha(build/'source/tang/boards/neo/neo.sdc')!=SHA_SDC:
        errors.append('Synthesis netlist or SDC drift')
    pt=(PARENT/'impl/pnr/console_neo.vo').read_text()
    ct=(build/'impl/pnr/console_neo.vo').read_text()
    pc,cc=cells(pt),cells(ct)
    pi,ci=initial_values(pt),initial_values(ct)

    def loads(data,net):
        return sorted((n,c['kind'],p) for n,c in data.items() for p,v in c['pins'].items()
                      if v==net and p not in ('F','Q','O','OF'))

    def resources(path):
        table=re.search(r'\n6\. Global Clock Signals\n(.*?)\n7\. Pinout by Port Name\n',path.read_text(),re.S)
        if not table:
            raise ValueError('Complete global table absent')
        return [dict(net=n.strip(),resource=r,location=loc.strip()) for n,r,loc in
                re.findall(r'^\s*(\S+)\s*\|\s*(PRIMARY|LW|HCLK)\s*\|\s*(.*?)\s*$',table[1],re.M)]

    previous=resources(PARENT/'impl/pnr/console_neo.rpt.txt')
    current=resources(build/'impl/pnr/console_neo.rpt.txt')
    routes={(r['net'],r['resource']) for r in current}
    old_routes={(r['net'],r['resource']) for r in previous}
    newly=[]
    for net,resource in sorted(routes-old_routes):
        drivers=[dict(instance=n,**c) for n,c in cc.items() if any(c['pins'].get(p)==net for p in ('F','Q','O'))]
        newly.append(dict(net=net,resource=resource,drivers=drivers,
            load_pin_counts=dict(Counter(p for _,_,p in loads(cc,net)))))
    controls=[]
    for net,count in zip((*CONTROLS,'gpu_debug_state[48]'),(312,283,2,253,9)):
        issues=[]
        pd=[n for n,c in pc.items() if any(c['pins'].get(p)==net for p in ('F','Q','O'))]
        cd=[n for n,c in cc.items() if any(c['pins'].get(p)==net for p in ('F','Q','O'))]
        if len(pd)!=1 or pd!=cd:
            issues.append('Driver differs')
        name=pd[0]
        if cc.get(name)!=pc[name] or ci.get(name)!=pi.get(name):
            issues.append('Driver primitive, pins or INIT differ')
        before,after=loads(pc,net),loads(cc,net)
        if before!=after or len(after)!=count:
            issues.append('Complete load set differs')
        if any(r['net']==net for r in current):
            issues.append('Control still uses a global resource')
        if cst.count(f'CLOCK_LOC "{net}" LOCAL_CLOCK;')!=1:
            issues.append('Required LOCAL_CLOCK changed')
        controls.append(dict(net=net,driver=name,loads=len(after),errors=issues,
                             same_driver_pins_init=cc.get(name)==pc[name] and ci.get(name)==pi.get(name)))
    locations={}
    with (build/'impl/pnr/console_neo.tr').open() as stream:
        for line in stream:
            m=re.search(r'\b(R\d+C\d+\[\d+\]\[[AB]\])\s+(\S+)',line)
            if m:
                name=m[2].rsplit('/',1)[0]
                if name in TARGETS:
                    locations.setdefault(name,set()).add(m[1])
    targets=[]
    for name,(kind,init,region) in TARGETS.items():
        issues=[]
        if name not in cc or cc[name]!=pc[name] or ci.get(name)!=pi.get(name):
            issues.append('Placed cell logic differs')
        if cst.count(f'INS_LOC "{name}" {region};')!=1:
            issues.append('Placement constraint changed')
        bounds=tuple(map(int,re.fullmatch(r'R\[(\d+):(\d+)\]C\[(\d+):(\d+)\]',region).groups()))
        sites=sorted(locations.get(name,[]))
        for site in sites:
            row,col=map(int,re.match(r'R(\d+)C(\d+)',site).groups())
            if not (bounds[0]<=row<=bounds[1] and bounds[2]<=col<=bounds[3]):
                issues.append('Reported location outside region: '+site)
        targets.append(dict(instance=name,region=region,reported_locations=sites,
            placement_proven_by_report=bool(sites) and not issues,errors=issues))
    files=[build/p for p in ('sources.json','console_neo.vg','source/tang/boards/neo/neo.cst',
        'source/tang/boards/neo/neo.sdc','impl/pnr/console_neo.vo','impl/pnr/console_neo.tr','impl/pnr/console_neo.rpt.txt')]
    files += [PARENT/'impl/pnr/console_neo.vo',PARENT/'impl/pnr/console_neo.rpt.txt',Path(__file__)]
    return dict(passed=not errors and all(not c['errors'] for c in controls+targets),errors=errors,
        controls=controls,targets=targets,global_resources=current,newly_global_nets=newly,
        removed_global_nets=[dict(net=n,resource=r) for n,r in sorted(old_routes-routes)],
        placement_reported_count=sum(t['placement_proven_by_report'] for t in targets),
        all_placements_proven_by_report=all(t['placement_proven_by_report'] for t in targets),
        sha256={str(p):sha(p) for p in files},hardware_access=False,
        limitations=['Missing location in timing reports is unknown, not proof that placement was applied.',
            'No independent bitstream placement decoder; vendor .p/.pr files are encrypted.',
            'This audit supplements full timing, DDR and GPU structural qualification; it does not replace them.'])


if __name__=='__main__':
    result=audit()
    dump(ROOT/'tang/impl'/NAME/'observer_placement_audit.json',result)
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise SystemExit('Observer placement/control audit failed')
