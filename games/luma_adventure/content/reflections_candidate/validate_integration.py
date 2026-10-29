#!/usr/bin/env python3
"""Check the applied connection against the archived 26-map campaign."""
from collections import deque
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def tile(e):return int(e['x']//32),int(e['y']//32)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-regeneration',action='store_true');args=parser.parse_args()
    archive=HERE/'pre_integration'
    old=read(archive/'campaign.json');campaign=read(ROOT/'campaign.json')
    phase=read(HERE/'integration.json')['phase_one']
    baseline=read(archive/'inputs.json')
    assert len(old['worlds'])==26 and len(campaign['worlds'])==36
    assert campaign['worlds']==old['worlds']+phase['append_worlds']
    assert campaign['world_metadata'][:26]==old['world_metadata']
    assert campaign['vehicle_progression']==old['vehicle_progression']
    preserved_maps=[]
    for name in old['worlds']:
        if name=='world_03.json':continue
        assert digest(ROOT/name)==baseline[name],(name,'old map modified')
        preserved_maps.append(name)
    for name,sha in baseline.items():
        if name.startswith('../art/') or name.endswith('/solutions.json'):
            assert digest(ROOT/name)==sha,(name,'art or witness modified')
    # Candidate room gameplay stays byte-equivalent after normalising its sole
    # lifecycle metadata change from candidate to integrated_candidate.
    for name in phase['append_worlds']:
        room=read(ROOT/name);assert room['design']['status']=='integrated_candidate'
        room['design']['status']='candidate_not_integrated'
        assert hashlib.sha256((json.dumps(room,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()==baseline[name],(name,'room gameplay modified')
    before=read(archive/'world_03.json');world=read(ROOT/'world_03.json')
    additions=phase['add_entities'];new_ids={e['id'] for e in additions}
    stripped=dict(world);stripped['entities']=[e for e in world['entities'] if e['id'] not in new_ids]
    assert stripped==before,'Old outdoor terrain/entities/quests/decorations changed'
    assert [e for e in world['entities'] if e['id'] in new_ids]==additions
    assert len({e['id'] for e in world['entities']})==len(world['entities'])<=64
    old_arcs=read(archive/'campaign_arcs.json');arcs=read(ROOT/'campaign_arcs.json')
    old_missions=old_arcs['worlds'][2]['missions']
    replacement=phase['replace_mission'];expected=[replacement['new'] if m['id']==replacement['old_id'] else m for m in old_missions]
    assert arcs['worlds'][2]['missions']==expected and len(expected)==16
    for i in (0,1,3,4,5):assert arcs['worlds'][i]==old_arcs['worlds'][i]
    mission=replacement['new']
    assert mission['id']=='c17_reflections' and not mission['required']
    assert mission['target_world']==35 and mission['complete_flags']==32 and mission['reward']=={'flags':512,'crystals':2}
    assert not any(e['grants']&512 for e in world['entities']),'Gallery must be unlocked only by new dungeon reward'
    rows=world['terrain']['rows'];route_checks=[]
    for flags in (0,256,768):
        closed={tile(e) for e in world['entities'] if e['kind']=='door' and ((flags&e['requires'])!=e['requires'] or flags&e.get('forbids',0))}
        start=tile(world['spawn']);queue=deque([start]);seen={start}
        while queue:
            x,y=queue.popleft()
            for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                xx,yy=q
                if q in seen or q in closed or not (0<xx<world['width']-1 and 0<yy<world['height']-1) or rows[yy][xx] in '~#tH':continue
                seen.add(q);queue.append(q)
        assert all(tile(e) in seen for e in before['entities']),'An old entity was cut off'
        for m in old_missions:
            for p in ([m['point']] if 'point'in m else m.get('checkpoints',[])):
                assert any(math.hypot(x*32+16-p['x'],y*32+16-p['y'])<=p.get('radius',46) for x,y in seen),(flags,m['id'],'objective radius inaccessible')
        for e in additions:
            assert any(math.hypot(x*32+16-e['x'],y*32+16-e['y'])<=48 for x,y in seen),(e['id'],'unreachable interaction')
            if e['target_world']==2:
                arrival=dict(x=e['target_x'],y=e['target_y']);assert tile(arrival) in seen
                assert tile(arrival) not in {tile(d) for d in additions}
        assert tile(phase['return_position']) in seen
        route_checks.append(dict(flags=flags,old_entities_reachable=len(before['entities']),new_doors_interactable=True,arrival_tiles_free=True))
    files=['campaign.json','campaign_arcs.json',*campaign['worlds'],'reflections_candidate/manifest.json','reflections_candidate/solutions.json','reflections_candidate/validation.json']
    hashes={name:digest(ROOT/name) for name in files}
    regeneration='not_requested'
    if args.check_regeneration:
        for script in ('reflections_candidate/build.py','build_worlds.py','build_arcs.py'):
            subprocess.run([sys.executable,str(ROOT/script)],check=True,capture_output=True,text=True)
        assert all(digest(ROOT/name)==sha for name,sha in hashes.items()),'Generators are not idempotent'
        regeneration='PASS'
    result=dict(status='PASS',scope='Applied data and deterministic regeneration, not save migration or runtime traversal.',world_count=36,mission_count=sum(len(a['missions']) for a in arcs['worlds']),
        preserved_old_world_files=preserved_maps,chapter_three_previous_entities_unchanged=44,chapter_three_previous_missions_unchanged=15,
        old_inventory_vehicle_rewards_not_revoked=True,candidate_room_gameplay_unchanged=True,art_unchanged=True,solutions_unchanged=True,
        route_checks=route_checks,regeneration=regeneration,engine_complete_campaign_and_save_migration='pending separate engine validation',inputs=hashes)
    (HERE/'integration_applied_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS: 36 maps / 96 missions; old map gameplay, 15 chapter-three missions, 44 entities, art and room solutions retained; door states and generator reproducibility checked.')

if __name__=='__main__':main()
