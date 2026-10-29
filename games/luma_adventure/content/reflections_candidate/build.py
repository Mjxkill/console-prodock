#!/usr/bin/env python3
"""Ten authored reflection rooms and reproducible solution witnesses.

Only this candidate folder is written. The active campaign remains untouched.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from build_dungeons import entity,pos,wall,action
from beam_model import BeamRoomSolver,choose_configuration,trace,union,validate_contract

BASE=26
COMPLETE=1<<20
RETURN=pos(56,43)

def write_json(path,value):
    """Keep unchanged candidate inputs byte-for-byte, including their mtimes."""
    data=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if not path.exists() or path.read_text()!=data:path.write_text(data)

def room(n,title,objective,hint):
    rows=[list('#'*32) if y in (0,23) else list('#'+'='*30+'#') for y in range(24)]
    return dict(schema=1,id=f'marees_reflections_{n+1:02}',title='LUMA — Les Jardins du Souvenir',name=title,
        subtitle='La Poste des Reflets',chapter=3,width=32,height=24,tile=32,indoors=True,spawn=pos(4,20),
        terrain=dict(rows=rows,palette={'=':'#a5ad98','#':'#344f5a','~':'#317f86'}),regions=[],decorations=[],
        entities=[entity('post_return','door',2,20,'Revenir au quai précédent',target_world=BASE+n-1 if n else 2,
                target_x=pos(27,20)['x'] if n else RETURN['x'],target_y=pos(27,20)['y'] if n else RETURN['y']),
            entity('optics_note','sign',4,17,"Le carnet d'Iria",text=hint),
            entity('optics_reset','sign',4,15,"Reprendre l'expérience",text="R remet les miroirs et les caisses dans leur état de départ. Tes trésors, les gardiens apaisés et les autres salles sont conservés.")],
        quests=[dict(id=f'reflections_goal_{n+1:02}',title=title,objective=objective,requires=0,complete_mask=COMPLETE)],
        design=dict(status='candidate_not_integrated',beam_goal=dict(on=0,off=0),mechanics=[]))

def add(w,eid,kind,x,y,name,**kw):
    e=entity(eid,kind,x,y,name,**kw);w['entities'].append(e);return e
def emitter(w,eid,x,y,direction,**kw):return add(w,eid,'emitter',x,y,"La source du courrier",direction=direction,art='emitter',**kw)
def mirror(w,eid,x,y,orientation=0):return add(w,eid,'mirror',x,y,"Le miroir tournant",orientation=orientation,art='mirror')
def receiver(w,eid,x,y,bit,name,protected=False):return add(w,eid,'receiver',x,y,name,grants=bit,art='lamp' if protected else 'receiver')
def finish(w,n,on,off=0,extra=0):
    w['design']['beam_goal']=dict(on=on,off=off)
    add(w,'post_exit','door',28,20,'La porte de la prochaine adresse' if n<9 else 'Rapporter les réponses au quai',requires=on|extra,forbids=off,grants=COMPLETE,
        target_world=BASE+n+1 if n<9 else 2,**({} if n<9 else dict(target_x=RETURN['x'],target_y=RETURN['y'])))

def rows_done(w):w['terrain']['rows']=[''.join(row) if isinstance(row,list) else row for row in w['terrain']['rows']]

def make_rooms():
    rooms=[];plans=[]
    w=room(0,"La fenêtre de Lise","Tourner le miroir pour éclairer le disque du nord, en gardant la lampe du sud éteinte, puis franchir la porte.",
        "Le courrier du phare voyage en ligne droite. E tourne un miroir entre / et \\. Observe le rayon : le disque du nord attend sa lettre, tandis que la petite lampe du sud doit rester éteinte. Tu peux marcher dans la lumière sans l'arrêter.")
    # The first 400x240-world-pixel viewport includes source, mirror and notebook.
    w['spawn']=pos(10,14)
    next(e for e in w['entities'] if e['id']=='optics_note').update(pos(9,16))
    emitter(w,'beam_sender_a',5,12,0);mirror(w,'beam_mirror_a',14,12,1)
    receiver(w,'beam_address_a',14,5,1,'La fenêtre de Lise');receiver(w,'beam_nest_a',14,21,2,'Le repos des oiseaux',True)
    finish(w,0,1,2);w['design']['mechanics']=['first_reflection','required_dark_receiver'];rooms.append(w);plans.append({})

    w=room(1,"L'adresse derrière le mur","Conduire le rayon autour du mur avec les deux miroirs jusqu'au disque de la rive est.",
        "La pierre arrête la lumière. Le courrier de l'est ne peut donc pas partir tout droit. Deux miroirs permettent de contourner le mur : cherche d'abord le passage au sud, puis la direction de la dernière adresse. La lampe du nord garde son repos.")
    wall(w,18,1,18,14);wall(w,18,18,18,22)
    emitter(w,'beam_sender_a',4,7,0);mirror(w,'beam_mirror_a',12,7,0);mirror(w,'beam_mirror_b',12,16,0)
    receiver(w,'beam_address_a',26,16,1,'La boîte du quai est');receiver(w,'beam_nest_a',12,3,2,'La fenêtre endormie',True)
    finish(w,1,1,2);w['design']['mechanics']=['two_reflections','wall_detour'];rooms.append(w);plans.append({})

    w=room(2,"La lettre qui tournait en rond","Rompre la boucle en dirigeant la lumière vers le disque du sud-ouest, sans allumer les petites lampes.",
        "Cette lettre repasse toujours par les mêmes miroirs. Une boucle n'invente pas une adresse. Suis son trajet et change le miroir qui peut envoyer le rayon vers le disque du sud-ouest. Les autres sorties donnent sur des fenêtres endormies.")
    emitter(w,'beam_sender_a',15,6,0)
    for eid,x,y,o in [('a',8,6,0),('b',24,6,1),('c',24,18,0),('d',8,18,1)]:mirror(w,'beam_mirror_'+eid,x,y,o)
    receiver(w,'beam_address_a',8,21,1,'La sortie du courrier');receiver(w,'beam_nest_a',24,3,2,'La fenêtre du nord',True);receiver(w,'beam_nest_b',28,18,4,'La fenêtre est',True);receiver(w,'beam_nest_c',3,6,8,'La fenêtre ouest',True)
    finish(w,2,1,14);w['design']['mechanics']=['bounded_closed_loop','trace_and_escape'];rooms.append(w);plans.append({})

    w=room(3,"Une lettre peut en porter une autre","Éclairer les deux disques successifs puis placer la caisse entre la dernière adresse et le nid.",
        "Un disque reçoit la lumière sans la retenir. Le rayon peut livrer plusieurs adresses, puis continuer trop loin. Tourne le miroir vers le sud et place une caisse après le second disque pour protéger le nid. L'eau laisse passer la lumière ; la caisse l'arrête.")
    for y in range(10,16):
        for x in range(16,21):w['terrain']['rows'][y][x]='~'
    emitter(w,'beam_sender_a',4,8,0);mirror(w,'beam_mirror_a',18,8,0)
    receiver(w,'beam_address_a',10,8,1,'La première adresse');receiver(w,'beam_address_b',18,17,2,'La seconde adresse');receiver(w,'beam_nest_a',18,21,4,'Le nid du sud',True)
    add(w,'shade_crate_a','crate',15,19,'La caisse écran')
    finish(w,3,3,4);w['design']['mechanics']=['transparent_receivers','water_transmission','crate_occlusion']
    rooms.append(w);plans.append(dict(final_crates={'shade_crate_a':(18,19)},post=[action('push','shade_crate_a',**{'from':pos(14,19),'direction':[1,0],'count':3})]))

    w=room(4,"Le carrefour des reflets","Éclairer les disques du nord et du sud avec les deux sources, en gardant la fenêtre est éteinte.",
        "Deux courriers partagent un carrefour. Un même miroir renvoie chacun selon son côté d'arrivée. Les disques du nord et du sud attendent une lumière ; la petite lampe à l'est ne doit rien recevoir. Observe les deux trajets avant de changer le carrefour.")
    for y in range(10,15):
        for x in range(15,20):w['terrain']['rows'][y][x]='~'
    emitter(w,'beam_sender_a',3,8,0);emitter(w,'beam_sender_b',22,3,1)
    for eid,x,y,o in [('a',12,8,0),('b',22,8,1),('c',12,17,0),('d',22,17,0)]:mirror(w,'beam_mirror_'+eid,x,y,o)
    receiver(w,'beam_address_a',22,21,1,"L'adresse du sud");receiver(w,'beam_address_b',12,3,2,"L'adresse du nord");receiver(w,'beam_nest_a',28,8,4,'La fenêtre est',True)
    finish(w,4,3,4);w['design']['mechanics']=['two_sources','shared_mirror','crossed_routes'];rooms.append(w);plans.append({})

    w=room(5,"Les boîtes d'ombre","Éclairer les deux disques et occulter les deux petites lampes avec les caisses, sans couper une adresse en amont.",
        "Une caisse n'a pas besoin d'être posée sur une dalle pour servir. L'une doit arrêter le rayon sous le disque central ; l'autre doit dépasser le disque de droite avant de couvrir la suite du trajet. Une caisse sur un disque l'empêche aussi de recevoir sa lettre.")
    wall(w,13,9,14,14);wall(w,25,6,26,11)
    emitter(w,'beam_sender_a',3,7,0);emitter(w,'beam_sender_b',3,17,0);mirror(w,'beam_mirror_a',20,7,0)
    receiver(w,'beam_address_a',20,12,1,'Le disque central');receiver(w,'beam_address_b',23,17,2,'Le disque de droite');receiver(w,'beam_nest_a',20,21,4,'Le nid du sud',True);receiver(w,'beam_nest_b',28,17,8,'Le nid de la rive est',True)
    add(w,'shade_crate_a','crate',17,18,'La première caisse écran');add(w,'shade_crate_b','crate',18,17,'La seconde caisse écran')
    finish(w,5,3,12);w['design']['mechanics']=['two_crate_occlusion','receiver_blocked_under_crate','independent_sources']
    rooms.append(w);plans.append(dict(final_crates={'shade_crate_a':(20,18),'shade_crate_b':(25,17)},post=[action('push','shade_crate_a',**{'from':pos(16,18),'direction':[1,0],'count':3}),action('push','shade_crate_b',**{'from':pos(17,17),'direction':[1,0],'count':7})]))

    w=room(6,"Le tri des trois courriers","Relier les trois disques d'adresse aux sources et laisser toutes les petites lampes éteintes.",
        "Le phare trie maintenant trois courriers à la fois. Les grands disques sont les adresses attendues ; les petites lampes signalent les fenêtres à laisser dans l'ombre. Les trajets peuvent partager un miroir. Un changement utile à une lettre peut détourner les deux autres.")
    wall(w,11,8,13,10);wall(w,19,14,21,16)
    for eid,x,y,d in [('a',3,6,0),('b',16,3,1),('c',28,18,2)]:emitter(w,'beam_sender_'+eid,x,y,d)
    for i,(x,y) in enumerate([(8,6),(16,6),(24,6),(8,12),(24,12),(8,18),(16,18),(24,18)]):mirror(w,f'beam_mirror_{i+1:02}',x,y,0)
    sites=[(3,12),(3,18),(28,6),(28,12),(8,3),(24,3),(8,21),(16,21),(24,21)]
    for i,((x,y),bit) in enumerate(zip(sites,[1,2,4,8,16,64,128,256,512])):receiver(w,f'beam_recipient_{i+1:02}',x,y,bit,f'Fenêtre {i+1}',True)
    rows_done(w);groups=defaultdict(list);mirrors=[e for e in w['entities'] if e['kind']=='mirror']
    for state in range(1<<len(mirrors)):
        result=trace(w,{e['id']:(state>>i)&1 for i,e in enumerate(mirrors)})
        if result['flags'].bit_count()==3 and not result['loops']:groups[result['flags']].append((state,len(result['mirrors'])))
    assert groups,'No three-address beam arrangement'
    on=min(groups,key=lambda mask:(len(groups[mask]),-min(used for _,used in groups[mask]),mask));all_bits=union(e['grants'] for e in w['entities'] if e['kind']=='receiver')
    for e in w['entities']:
        if e['kind']=='receiver' and e['grants']&on:e['art']='receiver';e['name']='Une adresse du courrier'
    finish(w,6,on,all_bits^on);w['design']['mechanics']=['three_sources','eight_mirror_network','simultaneous_routes','protected_windows'];rooms.append(w);plans.append(dict(farthest=True))

    w=room(7,"Lire le trajet dans l'autre sens","Basculer le levier sur la source est, éclairer les deux disques et laisser les deux lampes du sud éteintes.",
        "Le levier choisit la source : au repos, le courrier vient de l'ouest ; activé, il vient de l'est. La prochaine tournée doit partir de l'est. Les mêmes miroirs recevront alors la lumière par d'autres côtés. Garde les deux disques éclairés et les lampes du sud éteintes.")
    emitter(w,'beam_sender_w',3,12,0,forbids=128);emitter(w,'beam_sender_e',28,12,2,requires=128)
    for eid,x,y,o in [('a',10,12,1),('b',10,5,1),('c',22,5,0),('d',22,12,0)]:mirror(w,'beam_mirror_'+eid,x,y,o)
    receiver(w,'beam_address_a',10,8,1,'Le disque du passage');receiver(w,'beam_address_b',16,5,2,'Le disque de la voûte');receiver(w,'beam_nest_a',22,20,4,'Le repos du quai est',True);receiver(w,'beam_nest_b',10,20,8,'Le repos du quai ouest',True)
    add(w,'opt_power','switch',5,5,'La source de la tournée est',grants=128,art='switch',after="La tournée part maintenant de l'autre rive. Observe chaque arrivée au miroir.")
    finish(w,7,3,12,extra=128);w['design']['mechanics']=['fixed_source_selection','reverse_incidence','four_mirror_route'];rooms.append(w);plans.append(dict(source_flags=128,pre=[action('interact','opt_power')]))

    w=room(8,"Le quai sous surveillance","Rétablir le trajet des miroirs puis apaiser les deux veilleurs ; protéger les fenêtres du nord et de l'ouest.",
        "Le disque ouvre le quai, mais réveille aussi son veilleur. Tu peux préparer la caisse pour te couvrir avant de livrer la lumière. La seconde sentinelle se mettra en route quand la première se reposera. Les traits des veilleurs s'arrêtent sur les miroirs et les caisses.")
    wall(w,16,9,17,11);wall(w,20,14,21,15);wall(w,26,13,27,14)
    emitter(w,'beam_sender_a',3,7,0);mirror(w,'beam_mirror_a',12,7,0);mirror(w,'beam_mirror_b',12,17,0)
    receiver(w,'beam_address_a',20,17,1,'Le disque du quai');receiver(w,'beam_nest_a',4,17,2,'La fenêtre ouest',True);receiver(w,'beam_nest_b',12,3,4,'La fenêtre nord',True)
    # Move the notebook off the west receiver; passive receivers never steal E.
    note=next(e for e in w['entities'] if e['id']=='optics_note');note.update(pos(5,20))
    add(w,'shade_cover','crate',20,12,'La caisse de protection')
    add(w,'post_watcher','enemy',24,9,'Le veilleur du courrier',behavior='turret',hp=5,shot_period=1.7,requires=1,grants=64,art='turret')
    add(w,'post_sentinel','enemy',24,19,'La sentinelle du quai',behavior='melee',hp=5,requires=64,grants=128,art='enemy')
    finish(w,8,1,6,extra=192);w['design']['mechanics']=['receiver_gated_encounter','movable_cover','reflections_and_combat'];rooms.append(w);plans.append(dict(pre=[action('push','shade_cover',**{'from':pos(19,12),'direction':[1,0],'count':2})],final_crates={'shade_cover':(22,12)},post=[action('defeat','post_watcher'),action('defeat','post_sentinel')]))

    w=room(9,"Les trois adresses de la nuit","Relier les trois disques, préserver les cinq lampes, puis ouvrir la réserve des réponses et revenir à l'archipel.",
        "Trois adresses attendent : le disque à l'ouest et les deux disques du bas. Les petites lampes appartiennent aux oiseaux : elles doivent rester éteintes. Sous chaque disque du bas, une caisse peut arrêter la lumière avant le nid. Les réponses retrouveront enfin leurs quais.")
    for eid,x,y,d in [('a',3,6,0),('b',3,18,0),('c',27,12,2)]:emitter(w,'beam_sender_'+eid,x,y,d)
    for eid,x,y in [('a',9,6),('b',9,12),('c',18,12),('d',18,18),('e',9,18),('f',23,12),('g',23,6),('h',18,6),('i',23,18)]:mirror(w,'beam_mirror_'+eid,x,y,0)
    receiver(w,'beam_address_a',18,20,1,"L'adresse d'Ollo");receiver(w,'beam_address_b',9,20,2,"L'adresse d'Iria");receiver(w,'beam_address_c',3,12,4,'La boîte de Lise')
    for eid,x,y,bit in [('a',18,22,8),('b',9,22,16),('c',9,3,64),('d',18,3,128),('e',28,6,256)]:receiver(w,'beam_nest_'+eid,x,y,bit,'Un refuge des oiseaux',True)
    add(w,'shade_crate_a','crate',15,21,'La caisse du quai est');add(w,'shade_crate_b','crate',6,21,'La caisse du quai ouest')
    add(w,'post_answers','chest',27,17,'Les réponses retrouvées',requires=7,forbids=472,grants=32,cost=6,after="Les lettres avaient une adresse ; les miroirs avaient perdu leur trajet. Iria pourra rouvrir la galerie des facteurs, tout en laissant la nuit aux oiseaux.")
    finish(w,9,7,472,extra=32);w['design']['mechanics']=['three_sources','nine_mirror_network','two_shadow_crates','multiple_receivers','night_protection'];rooms.append(w)
    plans.append(dict(farthest=True,final_crates={'shade_crate_a':(18,21),'shade_crate_b':(9,21)},post=[action('push','shade_crate_a',**{'from':pos(14,21),'direction':[1,0],'count':3}),action('push','shade_crate_b',**{'from':pos(5,21),'direction':[1,0],'count':3}),action('interact','post_answers')]))
    return rooms,plans

def main():
    old=json.loads((HERE/'manifest.json').read_text()) if (HERE/'manifest.json').exists() else {}
    integrated=old.get('integrated',False)
    rooms,plans=make_rooms();witnesses=[];reports=[];files=[]
    for n,(w,plan) in enumerate(zip(rooms,plans)):
        w['design']['status']='integrated_candidate' if integrated else 'candidate_not_integrated'
        rows_done(w);receiver_mask=validate_contract(w)
        final_crates={e['id']:(e['x']//32,e['y']//32) for e in w['entities'] if e['kind']=='crate'};final_crates.update(plan.get('final_crates',{}))
        solution,proof=choose_configuration(w,final_crates,plan.get('source_flags',0),plan.get('farthest',False));w['design']['configuration_proof']=proof
        initial=trace(w);w['design']['initial_receiver_flags']=initial['flags'];w['design']['initial_closed_loops']=initial['loops']
        assert not(initial['flags']&w['design']['beam_goal']['on']==w['design']['beam_goal']['on'] and not initial['flags']&w['design']['beam_goal']['off']),(w['id'],'already solved before any action')
        solver=BeamRoomSolver(w);actions=[]
        for a in plan.get('pre',[]):solver.apply(a);actions.append(a)
        for e in w['entities']:
            if e['kind']=='mirror' and solver.orientations[e['id']]!=solution[e['id']]:
                a=solver.rotation_action(e['id']);solver.apply(a);actions.append(a)
        for a in plan.get('post',[]):solver.apply(a);actions.append(a)
        a=action('exit','post_exit');solver.apply(a);actions.append(a)
        assert solver.flags_at(solver.p)&w['design']['beam_goal']['on']==w['design']['beam_goal']['on']
        assert not solver.flags_at(solver.p)&w['design']['beam_goal']['off']
        filename=f'reflections_{n+1:02}.json';files.append('reflections_candidate/'+filename)
        write_json(HERE/filename,w)
        witnesses.append(dict(world=BASE+n,id=w['id'],solution=actions));reports.append(dict(world=BASE+n,id=w['id'],status='PASS',walking_tiles=solver.steps,rotations=sum(a['action']=='rotate' for a in actions),pushes=sum(a.get('count',0) for a in actions if a['action']=='push'),final_flags=solver.flags_at(solver.p),proof=proof,actions=solver.trace))
    write_json(HERE/'solutions.json',dict(schema=1,coordinates='world pixels; rotate.count toggles orientation; push directions are unit tile vectors',rooms=witnesses))
    write_json(HERE/'manifest.json',dict(schema=1,base_index=BASE,worlds=files,final_world=35,complete_flags=32,integrated=integrated,status='candidate; independent beam and movement witnesses PASS; engine evidence is recorded separately for the exact tested inputs',duration_measured=None,integration_contract='integration.json' if integrated else None))
    inputs={p:hashlib.sha256((HERE.parent/p).read_bytes()).hexdigest() for p in files+['reflections_candidate/solutions.json']}
    write_json(HERE/'validation.json',dict(status='PASS',scope='Independent ray reflection/loop model, receiver exclusivity, mirror assignment search, crate occlusion and physical witness reachability. Declared combat rewards are applied, not AI-simulated; no human duration inferred.',rooms=reports,inputs=inputs))
    print('PASS: ten reflection rooms; '+str(sum(r['rotations'] for r in reports))+' mirror rotations, '+str(sum(r['pushes'] for r in reports))+' crate pushes, '+str(sum(r['walking_tiles'] for r in reports))+' walking/pushing tiles. Integration='+str(integrated)+'. Campaign file unchanged by this generator.')

if __name__=='__main__':main()
