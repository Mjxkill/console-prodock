#!/usr/bin/env python3
"""Check mission graphs against actual maps, entities, vehicles and quest flags."""
import hashlib
import json
from collections import Counter,deque
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    campaign=json.loads((ROOT/'campaign.json').read_text())
    worlds=[json.loads((ROOT/p).read_text()) for p in campaign['worlds']]
    arcs=json.loads((ROOT/'campaign_arcs.json').read_text());reports=[]
    for arc in arcs['worlds']:
        world=worlds[arc['world']];entities={e['id']:e for e in world['entities']}
        missions=arc['missions'];ids={m['id'] for m in missions}
        assert len(missions)<=16 and len(ids)==len(missions)
        done=set();flags=0;vehicles={0};order=[];all_collectibles=set()
        def valid_point(p,air=False):
            x=int(p['x']//world['tile']);y=int(p['y']//world['tile'])
            assert 1<=x<world['width']-1 and 1<=y<world['height']-1
            assert p.get('radius',46)>0
        def valid_zone(p,air,state):
            """A checkpoint needs reachable space in its radius, not its centre."""
            tile=world['tile'];rows=world['terrain']['rows']
            closed={(int(e['x']//tile),int(e['y']//tile)) for e in entities.values() if e['kind']=='door' and (state&e['requires']!=e['requires'] or state&e.get('forbids',0))}
            start=(int(world['spawn']['x']//tile),int(world['spawn']['y']//tile));seen={start};queue=deque([start])
            while queue:
                x,y=queue.popleft()
                if (x*tile+tile/2-p['x'])**2+(y*tile+tile/2-p['y'])**2<=p.get('radius',46)**2:return
                for xx,yy in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    q=(xx,yy)
                    if q in seen or q in closed or not(1<=xx<world['width']-1 and 1<=yy<world['height']-1):continue
                    if not air and rows[yy][xx] in '~#tH':continue
                    seen.add(q);queue.append(q)
            raise AssertionError((world['id'],p,'no reachable checkpoint area with current door state',state))
        for m in missions:
            assert set(m['requires'])<=ids and m['id'] not in m['requires']
            assert m['type'] in ('talk','visit','collect','defeat','choice','vehicle_route','dungeon')
            assert m['title'] and m['text']
            if 'target' in m:
                assert m['target'] in entities
                assert not (m['required'] and entities[m['target']]['kind']=='portal'), 'A portal cannot require its own activation'
            if 'targets' in m:
                assert set(m['targets'])<=set(entities)
                assert 1<=m['count']<=len(set(m['targets']))
                allowed={'chest','crystal'} if m['type']=='collect' else {'enemy','boss'}
                assert all(entities[x]['kind'] in allowed for x in m['targets'])
                if m['type']=='collect':all_collectibles.update(m['targets'])
            if m['type']=='choice':assert len(m['options'])==3 and 0<=m['answer']<3 and len(set(m['options']))==3 and m['feedback']
            if m['type']=='visit':valid_point(m['point'])
            if m['type']=='vehicle_route':
                assert 0<=m['vehicle']<8 and len(m['checkpoints'])>=2
                for p in m['checkpoints']:valid_point(p,m['vehicle'] in (2,3,4))
            if m['type']=='dungeon':
                assert 0<=m['target_world']<len(worlds)
                target=worlds[m['target_world']];assert target.get('indoors')
                grants=0
                for e in target['entities']:grants|=e['grants']
                assert grants&m['complete_flags']==m['complete_flags']
                proof_path=(ROOT/campaign['worlds'][m['target_world']]).parent/'validation.json'
                proof=json.loads(proof_path.read_text());assert proof['status']=='PASS'
                assert any(r['world']==m['target_world'] and r['id']==target['id'] and r['status']=='PASS' for r in proof['rooms'])
        while len(done)<len(missions):
            progress=False
            for m in missions:
                if m['id'] in done or not set(m['requires'])<=done:continue
                if m['type']=='vehicle_route' and m['vehicle'] not in vehicles:continue
                targets=[entities[m['target']]] if m.get('target') else [entities[x] for x in m.get('targets',[])]
                if any(e['requires']&flags!=e['requires'] for e in targets):continue
                if m['type']=='visit':valid_zone(m['point'],False,flags)
                if m['type']=='vehicle_route':
                    for p in m['checkpoints']:valid_zone(p,m['vehicle'] in (2,3,4),flags)
                for e in targets:
                    # A talk interaction executes the entity's existing grants.
                    # Defeats execute enemy grants; mission choices use reward.
                    if m['type'] in ('talk','defeat'):
                        flags|=e['grants'];vehicles.add(e['vehicle'])
                    if m['type']=='collect' and e['kind']=='chest':vehicles.add(e['vehicle'])
                flags|=m['reward'].get('flags',0)
                vehicles.add(m['reward'].get('vehicle',0))
                done.add(m['id']);order.append(m['id']);progress=True
            assert progress,(world['id'],'dependency/flag/vehicle cycle',ids-done,flags,vehicles)
        assert flags&30==30,(world['id'],'cannot reach portal',flags)
        reports.append(dict(world=world['id'],missions=len(missions),required=sum(m['required'] for m in missions),types=dict(Counter(m['type'] for m in missions)),topological_progression=order,obtainable_vehicles=sorted(vehicles),portal_requirements_obtainable=True))
    result=dict(status='PASS',scope='mission schema, DAG, references, positions, prior interactions, flags, vehicles and portal reachability; duration remains unmeasured',worlds=reports,inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['campaign_arcs.json']+campaign['worlds']})
    (ROOT/'arcs_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f"PASS: {sum(r['missions'] for r in reports)} missions across {len(reports)} worlds; no dependency, flag or vehicle cycles. Duration not measured.")

if __name__=='__main__':main()
