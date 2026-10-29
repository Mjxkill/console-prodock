#!/usr/bin/env python3
"""Structural + reachability + progression validation for authored LUMA worlds."""
from collections import deque
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BLOCKED=set('~#tH')

def walkable(world,x,y):
    return 1<=x<world['width']-1 and 1<=y<world['height']-1 and world['terrain']['rows'][y][x] not in BLOCKED

def validate():
    campaign=json.loads((ROOT/'campaign.json').read_text())
    worlds=[json.loads((ROOT/p).read_text()) for p in campaign['worlds']]
    arcs=json.loads((ROOT/'campaign_arcs.json').read_text())
    reports=[];proof_files=set()
    for index,world in enumerate(worlds):
        for e in world['entities']:
            if e['kind'] not in ('portal','door'):continue
            target=e['target_world'];assert -1<=target<len(worlds),(world['id'],e['id'],'invalid destination')
            if target>=0:
                dest=worlds[target];sp=dest['spawn'];tile=dest['tile']
                x=int(e.get('target_x',sp['x'])//tile);y=int(e.get('target_y',sp['y'])//tile)
                assert walkable(dest,x,y),(world['id'],e['id'],'bad arrival')
        if world.get('indoors'):continue
        tile=world['tile']; rows=world['terrain']['rows']; entities=world['entities']
        assert len(rows)==world['height'] and all(len(r)==world['width'] for r in rows)
        assert set(''.join(rows))<=set('.t~=#:,H'), world['id']
        assert 0<len(entities)<=64
        assert len({e['id'] for e in entities})==len(entities)
        start=(int(world['spawn']['x']//tile),int(world['spawn']['y']//tile))
        assert walkable(world,*start)
        distance={start:0}; queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for q in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
                if q not in distance and walkable(world,*q):
                    distance[q]=distance[(x,y)]+1;queue.append(q)
        for e in entities:
            p=(int(e['x']//tile),int(e['y']//tile))
            assert p in distance,(world['id'],e['id'],'unreachable')
            assert e['kind'] in ('npc','shrine','chest','crystal','enemy','sign','portal','stable','boss','door')
            assert 0<=e['vehicle']<8
            if e['kind']=='portal':
                target=e['target_world'];assert -1<=target<len(worlds)
                if target>=0:
                    dest=worlds[target];sp=dest['spawn']
                    x=int(e.get('target_x',sp['x'])//tile);y=int(e.get('target_y',sp['y'])//tile)
                    assert walkable(dest,x,y),(world['id'],e['id'],'bad arrival')
        # Monotone prerequisites must admit a complete ordering. Chests + pickups
        # alone pay all mandatory costs: a player is never forced to farm enemies.
        # Interior completions may return new flags to an outdoor region. Their
        # room witness is checked here; validate_arcs checks the mission DAG.
        external_rewards=[]
        for arc in arcs['worlds']:
            if arc['world']!=index:continue
            for m in arc['missions']:
                reward=m.get('reward',{}).get('flags',0)
                if m['type']!='dungeon' or not reward:continue
                target=m['target_world'];assert 0<=target<len(worlds)
                proof_path=(ROOT/campaign['worlds'][target]).parent/'validation.json'
                proof_files.add(str(proof_path.relative_to(ROOT)))
                proof=json.loads(proof_path.read_text());assert proof['status']=='PASS'
                assert any(r['world']==target and r['id']==worlds[target]['id'] and r['status']=='PASS' for r in proof['rooms'])
                grants=0
                for e in worlds[target]['entities']:grants|=e['grants']
                assert grants&m['complete_flags']==m['complete_flags']
                external_rewards.append((m['id'],reward))
        flags=0; done=set(); crystals=0; order=[]
        while True:
            progress=False
            for e in entities:
                if e['id'] in done or e['requires']&flags!=e['requires']:continue
                if e['kind']=='shrine' and crystals<e['cost']:continue
                done.add(e['id']);progress=True
                if e['kind']=='crystal':crystals+=1
                if e['kind']=='chest':crystals+=e['cost'] or 4
                if e['kind']=='shrine':crystals-=e['cost']
                if e['grants']:
                    flags|=e['grants'];order.append(e['id'])
            if not progress:
                for mid,reward in external_rewards:
                    if flags&reward!=reward:flags|=reward;order.append('mission:'+mid);progress=True
                if not progress:break
        assert flags&63==63,(world['id'],'progression blocked',flags)
        assert len(done)==len(entities),(world['id'],'unreachable prerequisite')
        supply=sum((e['cost'] or 4) if e['kind']=='chest' else 1 if e['kind']=='crystal' else 0 for e in entities)
        required=sum(e['cost'] for e in entities if e['kind']=='shrine')
        assert supply>=required
        forward=[e for e in entities if e['kind']=='portal' and not e.get('return_portal')]
        assert len(forward)==1 and forward[0]['target_world']==(index+1 if index+1<6 else -1)
        if index:assert any(e.get('return_portal') and e['target_world']==index-1 and not e['requires'] for e in entities)
        reports.append(dict(world=world['id'],entities=len(entities),walkable_tiles=len(distance),all_entities_reachable_on_foot=True,mandatory_cost=required,noncombat_crystals=supply,progression=order,proven_interior_rewards=dict(external_rewards),max_walk_tiles=max(distance[(int(e['x']//tile),int(e['y']//tile))] for e in entities)))
    result=dict(status='PASS',scope='content structure, foot reachability, noncombat resources, prerequisites, portal destinations and proven interior reward flags; mission dependency order is checked by validate_arcs; not hardware or runtime combat',worlds=reports,inputs={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in ['campaign.json','campaign_arcs.json']+campaign['worlds']+sorted(proof_files)})
    (ROOT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':validate()
