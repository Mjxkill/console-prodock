#!/usr/bin/env python3
"""Authored second sanctuary; campaign linkage follows the saved manifest.

Crate puzzles are original deterministic reverse constructions, independently
solved on their complete embedded floor. Witnesses use real engine actions.
"""
import json
from pathlib import Path

from build_dungeons import action, entity, pos, wall
from puzzle_factory import generate, solve, solve_lights

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'canopy_candidate'
BASE=16
OUTDOOR_RETURN=pos(39,15)

def room(n,name,hint,empty=False):
    rows=[list('#'*32) if empty or y in (0,23) else list('#'+'='*30+'#') for y in range(24)]
    return dict(schema=1,id=f'canopy_sanctum_{n+1:02}',title='LUMA — Les Jardins du Souvenir',
        name=name,subtitle="L'Herbier des Ombres",chapter=2,width=32,height=24,tile=32,indoors=True,
        spawn=pos(4,12),terrain=dict(rows=rows,palette={'.':'#566c62','=':'#87947e','#':'#344d51','~':'#438c91'}),
        regions=[],entities=[
            entity('return','door',2,12,'Revenir vers la lumière',target_world=BASE+n-1 if n else 1,
                **({'target_x':OUTDOOR_RETURN['x'],'target_y':OUTDOOR_RETURN['y']} if not n else {})),
            entity('hint','sign',4,15,"Les notes de Silo",text=hint),
            entity('reset_note','sign',4,9,'Reprendre les expériences',text='R replace les caisses et éteint les circuits de cette salle. Tes autres découvertes sont conservées.')],
        decorations=[],quests=[],design=dict(status='authored_room',mechanics=[]))

def finish(w,n,requires,forbids=0,x=28,y=12):
    w['entities'].append(entity('exit','door',x,y,"Vers la serre suivante" if n<9 else "Retrouver Silo",requires=requires,forbids=forbids,
        target_world=BASE+n+1 if n<9 else 1,**({} if n<9 else {'target_x':OUTDOOR_RETURN['x'],'target_y':OUTDOOR_RETURN['y']})))

def lights(w,masks,target,forbids,switch_positions,lamp_positions):
    colors=['Mousse','Fougère','Lune','Rosée','Graine','Aube']
    for i,(x,y) in enumerate(lamp_positions):
        bit=1<<i
        w['entities'].append(entity(f'lamp_{i}','lamp',x,y,colors[i]+(' : à éclairer' if target&bit else ' : au repos'),grants=bit,art='lantern'))
    for i,(mask,(x,y)) in enumerate(zip(masks,switch_positions)):
        affects=' + '.join(colors[b] for b in range(len(lamp_positions)) if mask&(1<<b))
        w['entities'].append(entity(f'lever_{i}','switch',x,y,affects,grants=mask,after='Observe les lampes : un même levier peut en allumer certaines et en éteindre d’autres.'))
    solution=solve_lights(masks,target,forbids)
    w['design']['mechanics'].append('coupled_lamps')
    w['design']['light_proof']=dict(masks=masks,required_on=target,required_off=forbids,minimum_toggles=len(solution),solution=solution)
    return [action('interact',f'lever_{i}') for i in solution]

def crate_room(n,name,seed,hint):
    w=room(n,name,hint,empty=True);puzzle=generate(seed);ox,oy=10,8
    for y,row in enumerate(puzzle['rows']):
        for x,c in enumerate(row):w['terrain']['rows'][y+oy][x+ox]='=' if c=='.' else '#'
    # Bent single-width vestibules do not become a large crate parking area.
    # The proof below includes them, rather than asserting kernel optimality.
    for x,y in [(10,12),(9,12),(8,12),(8,13),(8,14),(8,15),(20,12),(21,12),(22,12),(22,13),(22,14),(22,15)]:
        w['terrain']['rows'][y][x]='='
    w['spawn']=pos(puzzle['player'][0]+ox,puzzle['player'][1]+oy)
    w['entities']=[entity('return','door',8,15,'Revenir à la serre précédente',target_world=BASE+n-1),
        entity('hint','sign',8,14,"L'étiquette des semences",text=hint)]
    boxes=[(x+ox,y+oy) for x,y in puzzle['boxes']];goals=[(x+ox,y+oy) for x,y in puzzle['goals']]
    for i,(x,y) in enumerate(boxes):w['entities'].append(entity(f'crate_{i}','crate',x,y,f'Réserve de semences {i+1}'))
    for i,(x,y) in enumerate(goals):w['entities'].append(entity(f'plate_{i}','plate',x,y,f'Racine {i+1}',grants=1<<i))
    floor={(x,y) for y,row in enumerate(w['terrain']['rows']) for x,c in enumerate(row) if c=='='}
    proof=solve(floor,boxes,tuple((w['spawn'][a]-16)//32 for a in ('x','y')),goals)
    assert proof['solution'] is not None,(name,'embedded puzzle is unsolvable')
    assert proof['pushes']>=14,(name,'embedding made the puzzle too trivial')
    tracked={p:f'crate_{i}' for i,p in enumerate(boxes)};witness=[]
    for move in proof['solution']:
        box=tuple(move['box']);eid=tracked.pop(box);dx,dy=move['direction'];tracked[(box[0]+dx,box[1]+dy)]=eid
        witness.append(action('push',eid,**{'from':pos(*move['stance']),'direction':[dx,dy],'count':1}))
    finish(w,n,7,x=22,y=15);witness.append(action('exit','exit'))
    w['design']['mechanics']=['three_crates','live_plates','corridor_ordering']
    w['design']['crate_proof']=dict(seed=seed,generator_attempt=puzzle['attempt'],kernel_minimum_pushes=puzzle['proof']['pushes'],
        complete_floor_minimum_pushes=proof['pushes'],expanded_states=proof['expanded'],optimal=proof['optimal'],solution=proof['solution'])
    return w,witness

def build():
    rooms=[];witnesses=[]
    w=room(0,'Les ombres utiles',"Les plantes ont besoin de lumière et de repos. Les trois lampes du sud sont, de gauche à droite : Mousse, Fougère, Lune. Éclaire Mousse et Lune, mais laisse Fougère dans l'ombre. Chaque levier relie plusieurs lampes ; son nom décrit ces liens.")
    for x in (11,21):wall(w,x,8,x,15,gaps={(x,11),(x,12)})
    witness=lights(w,[3,6,7],5,2,[(8,6),(16,6),(24,6)],[(12,18),(16,18),(20,18)])
    finish(w,0,5,2);rooms.append(w);witnesses.append(witness+[action('exit','exit')])

    w,ws=crate_room(1,'La réserve des trois saisons',1062401,"Trois caisses nourrissent trois racines. Une caisse contre un angle ne peut plus reculer. Cherche d'abord la place nécessaire pour te tenir derrière chacune, puis choisis celle qui doit rejoindre le fond. R reprend l'expérience sans perdre tes autres découvertes.")
    rooms.append(w);witnesses.append(ws)

    w=room(2,'Le ciel de six feuilles',"De gauche à droite, les six lampes sont Mousse, Fougère, Lune, Rosée, Graine et Aube. Mousse, Lune, Rosée et Aube doivent briller ; Fougère et Graine se reposent. Un levier peut éteindre une lampe déjà allumée. Lis les liens pour composer ce ciel.")
    for x,y in [(10,10),(21,10),(10,16),(21,16)]:wall(w,x,y,x+1,y+1)
    witness=lights(w,[3,6,12,24,48,37],45,18,[(7,5),(16,5),(25,5),(7,19),(16,19),(25,19)],[(11+i*2,13) for i in range(6)])
    finish(w,2,45,18);rooms.append(w);witnesses.append(witness+[action('exit','exit')])

    w=room(3,'Le pont qui doit dormir',"Le cristal de la rive ouest alimente le pont. Tire pour l'ouvrir, traverse, puis réveille la graine à l'est. La porte suivante exige que le pont soit éteint : retrouve une ligne de tir depuis la rive est pour rendre son repos au cristal. Tu peux toujours tirer à nouveau pour revenir.")
    for y in range(1,23):
        for x in range(14,17):w['terrain']['rows'][y][x]='~'
    for x in range(14,17):w['terrain']['rows'][12][x]='='
    w['entities'] += [entity('bridge_target','target',9,7,'Le cristal du pont',grants=1),
        entity('bridge','door',14,12,'Le pont de lumière',requires=1,target_world=BASE+3,target_x=pos(18,12)['x'],target_y=pos(18,12)['y']),
        entity('east_seed','switch',24,16,'La graine de la rive est',grants=2),
        entity('bridge_lamp','lamp',20,14,'Le pont doit dormir',grants=1,art='lantern'),
        entity('seed_lamp','lamp',23,14,'La graine doit briller',grants=2,art='lantern')]
    finish(w,3,2,1);w['design']['mechanics']=['shoot_across_water','reversible_bridge','required_dark_state']
    rooms.append(w);witnesses.append([action('shoot','bridge_target',**{'from':pos(9,12)}),action('interact','east_seed'),action('shoot','bridge_target',**{'from':pos(20,7)}),action('exit','exit')])

    w=room(4,'Les veilleurs immobiles',"Ces veilleurs suivent ton mouvement du regard, mais leurs racines ne bougent plus. Leurs traits s'arrêtent sur la pierre. Utilise les deux piliers pour interrompre une ligne de tir, puis attaque un veilleur à la fois. Le dernier ne s'éveille qu'après les deux premiers.")
    for x,y in [(12,7),(12,15),(21,7),(21,15)]:wall(w,x,y,x+1,y+2)
    w['entities'] += [entity('watcher_w','enemy',18,6,'Veilleur de la rosée',behavior='turret',hp=5,shot_period=1.8,grants=1,art='enemy_wisp'),
        entity('watcher_s','enemy',18,19,'Veilleur de la mousse',behavior='turret',hp=5,shot_period=1.5,grants=2,art='enemy_wisp'),
        entity('watcher_e','enemy',26,12,'Veilleur des graines',behavior='turret',hp=7,shot_period=1.3,requires=3,grants=4,art='enemy_wisp')]
    finish(w,4,7);w['design']['mechanics']=['stationary_aimed_fire','stone_cover','conditional_encounter']
    rooms.append(w);witnesses.append([action('defeat',e) for e in ('watcher_w','watcher_s','watcher_e')]+[action('exit','exit')])

    w,ws=crate_room(5,'Le passage des réserves',1062402,"Les trois réserves doivent rejoindre le même jardin, mais elles partagent un passage étroit. Ranger la caisse la plus proche trop tôt peut fermer la route des autres. Prépare le fond du jardin avant de remplir son entrée. Les trois dalles doivent rester occupées lorsque tu rejoins la sortie.")
    rooms.append(w);witnesses.append(ws)

    w=room(6,'Les reflets que l’on choisit',"Les lampes du sud sont Mousse, Fougère, Lune et Rosée, de gauche à droite. Éclaire Mousse et Lune seulement. Les cristaux relient deux voisines : nord-ouest Mousse/Fougère, nord-est Fougère/Lune, sud-est Lune/Rosée, sud-ouest Rosée/Mousse. L'eau laisse passer tes traits.")
    for y in range(8,15):
        for x in range(9,23):w['terrain']['rows'][y][x]='~'
    masks=[3,6,12,9];positions=[(11,9),(20,9),(20,13),(11,13)];stances=[(11,5),(20,5),(20,18),(11,18)]
    names=['Mousse + Fougère','Fougère + Lune','Lune + Rosée','Rosée + Mousse']
    for i,((x,y),mask) in enumerate(zip(positions,masks)):w['entities'].append(entity(f'reflector_{i}','target',x,y,names[i],grants=mask))
    for i in range(4):w['entities'].append(entity(f'lamp_{i}','lamp',12+i*3,20,['Mousse','Fougère','Lune','Rosée'][i],grants=1<<i,art='lantern'))
    sequence=solve_lights(masks,5,10);finish(w,6,5,10)
    w['design']['mechanics']=['coupled_targets','water_shot_lines','required_dark_state'];w['design']['minimum_target_toggles']=len(sequence)
    rooms.append(w);witnesses.append([action('shoot',f'reflector_{i}',**{'from':pos(*stances[i])}) for i in sequence]+[action('exit','exit')])

    w,ws=crate_room(7,'La chambre des racines croisées',1062403,"Ici les trois racines ne partagent pas la même orientation. Déplacer une réserve peut libérer l'endroit où tu devras te placer pour la suivante. Pense aussi aux cases de passage, pas seulement aux dalles. Les essais font partie de l'herbier ; R permet de repartir sans pénalité.")
    rooms.append(w);witnesses.append(ws)

    w=room(8,'La relève des gardiens',"Le premier veilleur garde le passage central. Quand il s'apaise, les deux sentinelles du fond s'éveillent. L'une te rejoint, l'autre reste à sa place : utilise leurs différences pour choisir ton côté. Les colonnes protègent des traits, mais pas d'une sentinelle qui les contourne.")
    wall(w,15,1,15,22,gaps={(15,11),(15,12),(15,13)})
    for x,y in [(20,6),(22,16),(26,10)]:wall(w,x,y,x+1,y+2)
    w['entities'] += [entity('first_watcher','enemy',11,12,'Le veilleur du passage',behavior='turret',hp=5,shot_period=1.8,grants=1,art='enemy_wisp'),
        entity('pursuer','enemy',25,6,'La sentinelle des feuilles',behavior='melee',hp=6,requires=1,grants=2),
        entity('last_watcher','enemy',26,19,'La sentinelle des racines',behavior='turret',hp=7,shot_period=1.5,requires=1,grants=4,art='enemy_wisp'),
        entity('shutter','door',15,12,'Le passage des veilleurs',requires=1,target_world=BASE+8,target_x=pos(18,12)['x'],target_y=pos(18,12)['y'])]
    # Every gap in the divider is gated: no diagonal walk around the shutter.
    w['terrain']['rows'][11][15]='#';w['terrain']['rows'][13][15]='#'
    finish(w,8,7);w['design']['mechanics']=['staged_encounter','mixed_pursuit_and_turret','gated_cover']
    rooms.append(w);witnesses.append([action('defeat',e) for e in ('first_watcher','pursuer','last_watcher')]+[action('exit','exit')])

    w=room(9,"La graine de l'ombre", "Les trois lampes sont Mousse, Fougère et Lune, de gauche à droite. Éclaire les deux extrêmes, garde la dalle occupée par une réserve, puis apaise les veilleurs. Silo avait raison : éclairer chaque recoin aurait brûlé la dernière graine. L'ombre compte aussi.")
    for x,y in [(16,10),(23,10),(19,17)]:wall(w,x,y,x+1,y+1)
    witness=lights(w,[3,6,7],5,2,[(8,5),(16,5),(24,5)],[(9,8),(12,8),(15,8)])
    w['entities'] += [entity('last_crate','crate',9,18,'La réserve des plantes nocturnes'),entity('last_plate','plate',9,14,'La racine de la nuit',grants=16),
        entity('keeper_w','enemy',21,6,'Le gardien du matin',behavior='turret',hp=7,shot_period=1.6,grants=64,art='enemy_wisp'),
        entity('keeper_e','enemy',26,17,'Le gardien du soir',behavior='turret',hp=7,shot_period=1.4,requires=64,grants=128,art='enemy_wisp'),
        entity('shadow_seed','chest',26,8,"L'herbier des ombres",requires=213,forbids=2,grants=32,cost=6,after="Tu retrouves les plantes qui fleurissent dans l'ombre. Silo pourra rétablir les nuits de la canopée, au lieu de laisser toutes les serres éclairées.")]
    finish(w,9,245,2);w['design']['mechanics']+=['maintained_weight','staged_turrets','combined_dark_and_light']
    rooms.append(w);witnesses.append(witness+[action('push','last_crate',**{'from':pos(9,19),'direction':[0,-1],'count':4}),action('defeat','keeper_w'),action('defeat','keeper_e'),action('interact','shadow_seed'),action('exit','exit')])
    for w in rooms:
        w['terrain']['rows']=[''.join(row) for row in w['terrain']['rows']]
        for e in w['entities']:
            if e.get('behavior')=='turret':e['art']='turret'
    return rooms,witnesses

def main():
    OUT.mkdir(exist_ok=True);rooms,witnesses=build();files=[]
    old=json.loads((OUT/'manifest.json').read_text()) if (OUT/'manifest.json').exists() else {}
    for n,w in enumerate(rooms):
        filename=f'canopy_{n+1:02}.json';files.append('canopy_candidate/'+filename)
        (OUT/filename).write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n')
    (OUT/'solutions.json').write_text(json.dumps(dict(schema=1,coordinates='world pixels; push directions are unit tile vectors',rooms=[dict(world=BASE+i,id=w['id'],solution=witnesses[i]) for i,w in enumerate(rooms)]),ensure_ascii=False,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(dict(schema=1,base_index=BASE,worlds=files,final_world=25,complete_flags=32,integrated=old.get('integrated',False),
        status='authored and runtime-tested; see validation and integration records',duration_measured=None,
        integration_note='World 1 entrance herbarium_entry and optional mission b17_herbarium are added only when integrated is true. Persistent entity/world IDs remain stable.'),ensure_ascii=False,indent=2)+'\n')
    print('Wrote ten second-sanctuary rooms; integration='+str(old.get('integrated',False)))

if __name__=='__main__':main()
