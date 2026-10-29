#!/usr/bin/env python3
"""Ten authored, persistent rooms for the first playable sanctuary.

Builds room data and executable solution witnesses. Integration into campaign
is explicit so the engine can review/test its new mechanics first.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dungeons';BASE=6;TILE=32

def pos(x,y):return dict(x=x*TILE+16,y=y*TILE+16)
def entity(eid,kind,x,y,name,**kw):
    e=dict(id=eid,kind=kind,**pos(x,y),name=name,text='',after='',requires=0,grants=0,cost=0,vehicle=0,art={'door':'portal','sequence':'lamp'}.get(kind,kind));e.update(kw);return e
def action(kind,target,**kw):return dict(action=kind,target=target,**kw)
def room(n,name,hint):
    rows=[list('#'*32) if y in (0,23) else list('#'+'='*30+'#') for y in range(24)]
    entities=[entity('return','door',2,12,'Revenir sur ses pas',target_world=n+BASE-1 if n else 0,**({'target_x':36*TILE+16,'target_y':14*TILE+16} if not n else {'target_x':26*TILE+16,'target_y':12*TILE+16})),entity('hint','sign',5,14,'Le carnet du jardinier',text=hint),entity('reset','sign',5,10,'Recommencer cette salle',text="Si une caisse est coincée ou si tu veux recommencer, utilise R. Les autres salles conservent leurs souvenirs.",reset_room=True)]
    return dict(schema=1,id=f'aube_sanctum_{n+1:02}',title='LUMA — Les Jardins du Souvenir',name=name,subtitle='Le Jardin sous les Racines',chapter=1,width=32,height=24,tile=TILE,indoors=True,spawn=pos(4,12),terrain={'rows':rows,'palette':{'.':'#55766c','=':'#b0a687','#':'#52696a','~':'#3d9298'}},regions=[],entities=entities,decorations=[],quests=[])
def wall(w,x1,y1,x2,y2,gaps=()):
    for y in range(y1,y2+1):
        for x in range(x1,x2+1):
            if (x,y) not in gaps:w['terrain']['rows'][y][x]='#'
def gate(w,x,y,requires):w['entities'].append(entity('gate','door',x,y,'La porte des jardiniers',requires=requires,target_world=BASE+int(w['id'].rsplit('_',1)[1])-1,target_x=(x+2)*TILE+16,target_y=y*TILE+16))
def exit_room(w,n,requires):
    w['entities'].append(entity('exit','door',28,12,'Continuer dans les racines' if n<9 else 'Revenir au village',requires=requires,target_world=BASE+n+1 if n<9 else 0,**({} if n<9 else {'target_x':36*TILE+16,'target_y':14*TILE+16})))

def build():
    rooms=[];witnesses=[]
    w=room(0,'Le seuil de la mémoire',"Approche la pierre au nord et réveille-la avec E. La lumière garde son état lorsque tu t'éloignes. Une porte reconnaît ce que tu as changé, pas l'endroit où tu te tiens.")
    wall(w,13,3,15,8);wall(w,13,16,15,20)
    w['entities'].append(entity('first_switch','switch',10,6,'La première lueur',grants=1));exit_room(w,0,1)
    rooms.append(w);witnesses.append([action('interact','first_switch'),action('exit','exit')])
    w=room(1,'La galerie des deux saisons',"La serre garde deux souvenirs : l'ombre fraîche et le soleil. Allume les deux pierres. Revenir sur une pierre déjà allumée l'éteint ; observe avant d'appuyer.")
    wall(w,3,8,28,8,gaps={(5,8),(26,8)});wall(w,3,16,28,16,gaps={(6,16),(25,16)})
    w['entities'] += [entity('shade_switch','switch',8,5,"L'ombre fraîche",grants=1),entity('sun_switch','switch',24,19,'Le soleil doux',grants=2)]
    exit_room(w,1,3);rooms.append(w);witnesses.append([action('interact','shade_switch'),action('interact','sun_switch'),action('exit','exit')])
    w=room(2,'Le courant et la cible',"La lumière de ton arc franchit l'eau, mais la pierre l'arrête. Tire sur le cristal de l'autre rive depuis la berge centrale. Le passage au nord reconnaîtra sa lumière.")
    for y in range(1,23):
        for x in range(16,19):w['terrain']['rows'][y][x]='~'
    for x in range(16,19):w['terrain']['rows'][4][x]='='
    w['entities'].append(entity('water_target','target',23,12,'Le cristal du courant',grants=1));gate(w,16,4,1);exit_room(w,2,1)
    rooms.append(w);witnesses.append([action('shoot','water_target',**{'from':pos(14,12)}),action('exit','exit')])
    w=room(3,'Ce qui reste en place',"La dalle n'écoute pas la lumière : elle attend un poids. Pousse la caisse vers la dalle avec E, en te tenant du côté opposé au déplacement. La caisse gardera la porte ouverte pendant ton passage.")
    wall(w,16,1,16,22,gaps={(16,12)})
    w['entities'] += [entity('weight','crate',10,8,'La caisse de graines'),entity('floor_plate','plate',8,8,'La dalle des racines',grants=1)]
    gate(w,16,12,1);exit_room(w,3,1);rooms.append(w);witnesses.append([action('push','weight',**{'from':pos(11,8),'direction':[-1,0],'count':2}),action('exit','exit')])
    w=room(4,'La grammaire du vivant',"Les jardiniers suivent le trajet de l'eau : elle entre par la RACINE, rejoint la FEUILLE, puis nourrit la FLEUR. Les lanternes attendent ce même ordre. Une erreur efface seulement la séquence ; tu peux réessayer.")
    wall(w,12,6,12,17,gaps={(12,11),(12,12)});wall(w,20,6,20,17,gaps={(20,11),(20,12)})
    w['entities'] += [entity('root','sequence',8,6,'Racine',cost=1,grants=1),entity('leaf','sequence',24,6,'Feuille',cost=2,grants=2),entity('flower','sequence',16,18,'Fleur',cost=3,grants=4)]
    exit_room(w,4,7);rooms.append(w);witnesses.append([action('interact','root'),action('interact','leaf'),action('interact','flower'),action('exit','exit')])
    w=room(5,'Les ombres de la réserve',"Les trois ombres tournent autour des réserves, pas autour de toi. Utilise les piliers pour choisir tes approches. La porte retiendra chaque ombre apaisée, même si tu dois revenir au seuil.")
    for x,y in [(12,7),(20,16),(12,17),(22,6)]:wall(w,x,y,x+1,y+1)
    for eid,x,y,flag in [('shadow_a',8,6,1),('shadow_b',24,8,2),('shadow_c',23,18,4)]:w['entities'].append(entity(eid,'enemy',x,y,"Éclat d'oubli",grants=flag))
    exit_room(w,5,7);rooms.append(w);witnesses.append([action('defeat','shadow_a'),action('defeat','shadow_b'),action('defeat','shadow_c'),action('exit','exit')])
    w=room(6,'Les deux manières de tenir',"Une caisse peut tenir une porte pendant que tu vises une lumière. Commence par la dalle du nord-ouest, puis cherche une ligne dégagée vers le cristal de l'autre aile.")
    wall(w,16,1,16,22,gaps={(16,12)})
    w['entities'] += [entity('weight','crate',10,17,'La caisse des semences'),entity('floor_plate','plate',10,8,'La dalle du nord',grants=1),entity('far_target','target',23,7,'Le cristal de la seconde aile',grants=2)]
    gate(w,16,12,1);exit_room(w,6,3);rooms.append(w);witnesses.append([action('push','weight',**{'from':pos(10,18),'direction':[0,-1],'count':9}),action('shoot','far_target',**{'from':pos(23,18)}),action('exit','exit')])
    w=room(7,'La chanson de la roue',"Le VENT fait tourner la ROUE ; la roue remonte l'EAU ; l'eau rejoint la FLEUR. Quatre lanternes racontent ce mouvement. Les ombres n'effacent pas un ordre déjà retrouvé.")
    wall(w,16,3,16,20,gaps={(16,11),(16,12),(16,13)})
    for eid,x,y,order,flag in [('wind',8,5,1,1),('wheel',24,18,2,2),('water',24,5,3,4),('flower',8,18,4,8)]:w['entities'].append(entity(eid,'sequence',x,y,{'wind':'Vent','wheel':'Roue','water':'Eau','flower':'Fleur'}[eid],cost=order,grants=flag))
    w['entities'].append(entity('shadow','enemy',24,12,"L'ombre de l'aiguillage",grants=16));exit_room(w,7,31)
    rooms.append(w);witnesses.append([action('defeat','shadow'),*[action('interact',s) for s in ('wind','wheel','water','flower')],action('exit','exit')])
    w=room(8,'Le jardin des deux poids',"Deux dalles, deux caisses. Prépare la route de chaque caisse avant de la pousser : une caisse ne peut pas tirer l'autre. Si tu coinces un passage, R recommence seulement cette salle.")
    wall(w,16,1,16,22,gaps={(16,12)})
    w['entities'] += [entity('weight_a','crate',8,9,'La caisse du printemps'),entity('weight_b','crate',8,15,"La caisse de l'automne"),entity('plate_a','plate',10,6,'La dalle du printemps',grants=1),entity('plate_b','plate',10,18,"La dalle de l'automne",grants=2)]
    gate(w,16,12,3);exit_room(w,8,3);rooms.append(w);witnesses.append([action('push','weight_a',**{'from':pos(7,9),'direction':[1,0],'count':2}),action('push','weight_a',**{'from':pos(10,10),'direction':[0,-1],'count':3}),action('push','weight_b',**{'from':pos(7,15),'direction':[1,0],'count':2}),action('push','weight_b',**{'from':pos(10,14),'direction':[0,1],'count':3}),action('exit','exit')])
    w=room(9,'La mémoire sous les racines',"Le gardien n'a pas oublié le village : il gardait sa première graine. Apaise-le, puis ouvre la réserve derrière lui. Le chemin de retour doit rester un choix, jamais une récompense qui disparaît.")
    for x,y in [(11,5),(21,5),(11,18),(21,18)]:wall(w,x,y,x+1,y+1)
    w['entities'] += [entity('root_keeper','boss',19,12,'Le jardinier de pierre',grants=1,art='boss',after="Le gardien laisse ses racines se reposer. La graine n'avait pas besoin d'être enfermée pour être protégée."),entity('memory_seed','chest',25,12,'La première graine',requires=1,grants=32,cost=8,art='chest',after="Tu retrouves la graine gardée par les premiers jardiniers. Elle rejoint le village, et le jardin souterrain restera ouvert.")]
    exit_room(w,9,33);rooms.append(w);witnesses.append([action('defeat','root_keeper'),action('interact','memory_seed'),action('exit','exit')])
    for w in rooms:
        w['terrain']['rows']=[''.join(row) for row in w['terrain']['rows']]
        for e in w['entities']:
            if e['kind'] in ('door','switch','sequence'):
                w['decorations'].append(dict(art='flowers',x=e['x']+40,y=e['y']+20,w=24,h=24))
    return rooms,witnesses

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--integrate',action='store_true');a=p.parse_args();OUT.mkdir(exist_ok=True)
    rooms,witnesses=build();files=[]
    for n,w in enumerate(rooms):
        filename=f'aube_{n+1:02}.json';(OUT/filename).write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n');files.append('dungeons/'+filename)
    solutions=dict(schema=1,coordinates='world pixels; push direction is a unit tile vector',rooms=[dict(world=BASE+n,id=w['id'],solution=witnesses[n]) for n,w in enumerate(rooms)])
    (OUT/'solutions.json').write_text(json.dumps(solutions,ensure_ascii=False,indent=2)+'\n')
    previous=json.loads((OUT/'manifest.json').read_text()) if (OUT/'manifest.json').exists() else {}
    (OUT/'manifest.json').write_text(json.dumps(dict(schema=1,base_index=BASE,worlds=files,final_world=15,complete_flags=32,integrated=a.integrate or previous.get('integrated',False),status='authored; validate witness and actual runtime before claiming playable',duration_measured=None),ensure_ascii=False,indent=2)+'\n')
    if a.integrate:
        subprocess.run([sys.executable,str(ROOT/'build_worlds.py')],check=True)
        subprocess.run([sys.executable,str(ROOT/'build_arcs.py')],check=True)
    print(f'Wrote {len(rooms)} authored sanctuary rooms and action witnesses; integrated={a.integrate or previous.get("integrated",False)}.')

if __name__=='__main__':main()
