#!/usr/bin/env python3
"""Prepare and check the chapter-three connection without editing the campaign."""
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from build_dungeons import entity,pos

def save(name,value):
    path=HERE/name
    data=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if not path.exists() or path.read_text()!=data:path.write_text(data)

def tile(p):return int(p['x']//32),int(p['y']//32)

def main():
    campaign=json.loads((ROOT/'campaign.json').read_text())
    arcs=json.loads((ROOT/'campaign_arcs.json').read_text())
    world_file=campaign['worlds'][2]
    world=json.loads((ROOT/world_file).read_text())
    arc=next(a for a in arcs['worlds'] if a['world']==2)
    assert len(campaign['worlds'])==26,'This proposal is based on the 26-map campaign'
    old={m['id']:m for m in arc['missions']}
    assert 'c16' in old and 'c17_reflections' not in old
    flag=512
    assert not any((e.get('grants',0)|e.get('requires',0)|e.get('forbids',0))&flag for e in world['entities'])
    assert not any(m.get('reward',{}).get('flags',0)&flag for m in arc['missions'])
    new_mission=dict(id='c17_reflections',title='Les réponses ont aussi une adresse',
        text="Après la pierre du jardin sud, entrer dans la Poste des Reflets, à l'ouest du phare vivant. Retrouver les réponses en conduisant la lumière vers les disques et en protégeant les lampes des oiseaux. Revenir au quai pour rouvrir la galerie des facteurs.",
        type='dungeon',requires=['c15'],target_world=35,complete_flags=32,
        reward=dict(flags=flag,crystals=2),required=False)
    entry=entity('reflections_entry','door',56,42,'La Poste des Reflets',
        requires=256,target_world=26,art='portal',
        text="Les lettres du phare attendent leurs réponses. La pierre du jardin sud garde le signe qui ouvre la poste.",
        after="Un miroir donne une direction au courrier ; une caisse peut garder une fenêtre dans l'ombre.")
    west=entity('post_gallery_west','door',18,40,'La galerie des facteurs — quai du village',
        requires=flag,target_world=2,target_x=pos(58,29)['x'],target_y=pos(58,29)['y'],art='portal',
        text="La galerie reliait ce quai à celui des coquilles. Les réponses de la Poste des Reflets permettront à Iria de la rouvrir.",
        after="La galerie est de nouveau ouverte. Les prochains courriers éviteront le détour des ponts.")
    east=entity('post_gallery_east','door',57,29,'La galerie des facteurs — quai des coquilles',
        requires=flag,target_world=2,target_x=pos(18,41)['x'],target_y=pos(18,41)['y'],art='portal',
        text="Derrière la grille, la galerie rejoint le quai du village. Il manque les réponses de la Poste des Reflets.",
        after="Le trajet rejoint le quai du village. Le courrier peut maintenant circuler dans les deux sens.")
    additions=[entry,west,east]
    existing={e['id']:e for e in world['entities']}
    assert not set(existing)&{e['id'] for e in additions}
    assert len(existing)+len(additions)<=64
    new_missions=[new_mission if m['id']=='c16' else m for m in arc['missions']]
    assert len(new_missions)==16
    assert all(m==old[m['id']] for m in new_missions if m['id']!='c17_reflections')
    # All three new doors are initially closed; they must not sever prior routes.
    closed={tile(e) for e in additions}
    closed.update(tile(e) for e in world['entities'] if e['kind']=='door' and e.get('requires'))
    rows=world['terrain']['rows']
    def free(q,with_doors=True):
        x,y=q
        return 0<x<world['width']-1 and 0<y<world['height']-1 and rows[y][x] not in '~#tH' and (not with_doors or q not in closed)
    def distances(start,with_doors=True):
        seen={start:0};queue=deque([start]);assert free(start,with_doors)
        while queue:
            x,y=queue.popleft()
            for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if q not in seen and free(q,with_doors):seen[q]=seen[(x,y)]+1;queue.append(q)
        return seen
    reachable=distances(tile(world['spawn']))
    assert all(tile(e) in reachable for e in world['entities']),'New doors cut an old entity off'
    checkpoints=[(m['id'],p) for m in arc['missions'] for p in ([m['point']] if 'point' in m else m.get('checkpoints',[]))]
    for mid,p in checkpoints:
        assert any(math.hypot(x*32+16-p['x'],y*32+16-p['y'])<=p.get('radius',46) for x,y in reachable),(mid,'no reachable point inside objective radius')
    sites=[]
    for e in additions:
        p=tile(e);assert free(p,False)
        assert all(tile(old_e)!=p for old_e in world['entities'])
        assert any(math.hypot(x*32+16-e['x'],y*32+16-e['y'])<=48 for x,y in reachable)
        clearance=min(math.hypot(pnt['x']-e['x'],pnt['y']-e['y'])-pnt.get('radius',46) for _,pnt in checkpoints)
        assert clearance>32,(e['id'],'door too close to a prior checkpoint zone')
        nearest=min(math.hypot(old_e['x']-e['x'],old_e['y']-e['y']) for old_e in world['entities'])
        assert nearest>48,(e['id'],'ambiguous interaction near an old entity')
        for d in world['decorations']:
            # Decorations use bottom-centre anchors. Check a 32x32 door footprint.
            overlaps=(e['x']+16>d['x']-d['w']/2 and e['x']-16<d['x']+d['w']/2 and e['y']+16>d['y']-d['h'] and e['y']-16<d['y'])
            assert not overlaps,(e['id'],'overlaps visible decoration',d['art'])
        sites.append(dict(id=e['id'],tile=list(p),terrain=rows[p[1]][p[0]],closed_door_interaction_reachable=True,
            nearest_old_entity_pixels=round(nearest,2),old_checkpoint_radius_clearance_pixels=round(clearance,2)))
    arrivals=[pos(56,43),pos(18,41),pos(58,29)]
    for p in arrivals:
        assert tile(p) in reachable
        assert all(math.hypot(p['x']-e['x'],p['y']-e['y'])>48 for e in world['entities'])
    route_distance=distances(tile(pos(18,41)),False)[tile(pos(58,29))]
    manifest=json.loads((HERE/'manifest.json').read_text())
    assert manifest['base_index']==26 and manifest['final_world']==35
    assert len(manifest['worlds'])==10 and not manifest['integrated']
    sources=['campaign.json','campaign_arcs.json',world_file,*manifest['worlds'],'reflections_candidate/solutions.json']
    inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
    proposal=dict(schema=1,status='proposal_only_not_applied',world=2,world_id=world['id'],
        narrative="Iria retrouve le trajet des réponses ; la lettre de Lise devient un service pour les prochains voyageurs. La lumière permet de livrer le courrier tout en préservant les refuges nocturnes.",
        phase_one=dict(append_worlds=manifest['worlds'],add_entities=additions,
            replace_mission=dict(old_id='c16',new=new_mission),return_position=pos(56,43),
            migration=dict(no_completion_transfer=['c16 -> c17_reflections'],unchanged_mission_ids=[m['id'] for m in new_missions if m['id']!='c17_reflections'],
                preserve_existing_entities=True,preserve_chest_ids=['sidequest_reward'],preserve_inventory=True,preserve_vehicle_unlocks=True,
                completed_old_c16_reward="Keep its previously granted two crystals. c17 is new optional content with its own reward; do not revoke or replay c16."),
            consequence=dict(id='post_gallery',kind='two_way_local_shortcut',requires=flag,
                endpoints=['post_gallery_west','post_gallery_east'],old_foot_route_tiles=route_distance,
                behavior="The dungeon mission grants local flag 512 after returning outdoors; both existing quays then connect through the gallery. Arrival stays one tile off the opposite door.")),
        later_separate_phase=[dict(id='post_archive',kind='visible_locked_annex',proposed_entry=pos(58,44),requires=flag,
            story="Jade, l'apprentie des cartes, garde les réponses qui n'ont pas encore de destinataire. Elle invite à comparer deux tracés du même rivage et à rapporter une observation à Iria.",
            design="A visible closed archive and a short authored interior, with an observation puzzle and a new letter. Separate map, solution witness and migration check required before adding any door.",status='not_built_no_world_index_reserved'),
            dict(id='post_reply',kind='return_conversation',requires=flag,
            story="Revenir voir Lise pour lui montrer une réponse : son message a permis de rétablir un trajet pour quelqu'un d'autre. Ollo peut citer un courrier qui a emprunté la galerie.",
            design="Use a new conditional reply or a new letter entity; never reset the existing sidequest chest or claim an old visit completed the new exchange.",status='proposal_only_requires_dialogue_contract')],
        integration_gate="Wait for the engine owner's signal. Preserve current campaign and art while preview/input validation is completed; then update durable generators and check migration 26 to 36 maps.",
        duration=dict(human_playtest=None,claimed_hours=None),inputs=inputs)
    save('integration_proposal.json',proposal)
    save('integration_validation.json',dict(status='PASS',scope='Dry-run placement and backward route/missions checks only. No active campaign mutation; runtime shortcut/save-migration validation pending.',
        entities_before=len(existing),entities_after=len(existing)+3,mission_count=16,retained_missions=15,
        reachable_old_entities=len(existing),reachable_old_checkpoint_zones=len(checkpoints),sites=sites,arrivals=arrivals,
        original_foot_route_tiles=route_distance,inputs=inputs))
    print(f'PASS: proposal only; 15 missions and {len(existing)} entities retained; three gated doors checked; gallery bypasses a {route_distance}-tile foot route. No human duration estimate.')

if __name__=='__main__':main()
