#!/usr/bin/env python3
"""Author runtime mission graphs. Duration is established by playtests, not text length."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def point(x,y,radius=46):return dict(x=x*32+16,y=y*32+16,radius=radius)
def mission(mid,title,text,kind,requires=(),reward=None,required=True,**fields):
    return dict(id=mid,title=title,text=text,type=kind,requires=list(requires),reward=reward or {},required=required,**fields)
def talk(mid,title,text,target,requires=(),**extra):return mission(mid,title,text,'talk',requires,target=target,**extra)
def visit(mid,title,text,x,y,requires=(),**extra):return mission(mid,title,text,'visit',requires,point=point(x,y),**extra)
def choose(mid,title,text,target,options,answer,feedback,requires=(),**extra):return mission(mid,title,text,'choice',requires,target=target,options=options,answer=answer,feedback=feedback,**extra)
def route(mid,title,text,vehicle,points,requires=(),**extra):return mission(mid,title,text,'vehicle_route',requires,vehicle=vehicle,checkpoints=[point(*p,64) for p in points],**extra)
def collect(mid,title,text,targets,count,requires=(),**extra):return mission(mid,title,text,'collect',requires,targets=targets,count=count,**extra)
def defeat(mid,title,text,targets,count,requires=(),**extra):return mission(mid,title,text,'defeat',requires,targets=targets,count=count,**extra)

def main():
    worlds=[]
    worlds.append(dict(world=0,arc="Les lanternes n’ont pas perdu leur lumière : elles ont perdu les chemins qui reliaient leurs souvenirs.",missions=[
        talk('a01','Un nom au bord du chemin','Parler à Maëlle. Retenir où se trouvent le verger, le moulin et le marais.','guide'),
        visit('a02','Le verger silencieux','Rejoindre le vieux verger. Observer les fleurs avant de toucher sa balise.',15,13,['a01']),
        choose('a03','Ce que les fleurs protègent','Lire le carnet du verger et choisir ce qui rendra sa prochaine récolte possible.','observation_1',['Enlever toutes les fleurs entre les arbres','Garder des fleurs pour les pollinisateurs','Couvrir les arbres pour arrêter le vent'],1,'Les fleurs nourrissent les pollinisateurs, qui transportent le pollen entre les fleurs. Le verger a besoin de voisins vivants.',['a02']),
        collect('a04','Les réserves des anciens','Trouver trois réserves distinctes près du verger, du moulin ou des chemins. Une réserve ouverte compte même si ses éclats ont déjà servi.',['cache_1','cache_2','crystal_03','crystal_04','crystal_05'],3,['a01']),
        defeat('a05','Faire place aux jeunes pousses','Repousser l’ombre qui tourne autour du verger. Approcher en observant ses déplacements.',['sentinel_1'],1,['a03']),
        talk('a06','Le premier souvenir','Réveiller le verger avec deux éclats. Sa lumière devient le premier repère du voyage.','beacon_1',['a04','a05']),
        talk('a07','Brindille connaît la route','Rencontrer Nino et apprendre à voyager avec son cheval. Il partage une route, pas seulement une monture.','companion',['a01']),
        route('a08','La tournée des moulins','Avec Brindille, suivre dans l’ordre le village, le passage central, le moulin et la prairie. La tournée restaure le souvenir du courant.',1,[(16,37),(37,37),(63,22),(29,50)],['a07','a04'],reward={'flags':4}),
        choose('a09','Le bord de la rivière','Observer les roseaux. Choisir une manière de protéger le marais sans fermer le chemin des voyageurs.','observation_3',['Couper tous les roseaux pour voir le fond','Creuser le lit le plus vite possible','Garder une rive plantée et un passage étroit'],2,'Les roseaux ralentissent l’eau, retiennent des sédiments et offrent un abri. Le passage étroit garde une place aux voyageurs.',['a06','a08'],reward={'flags':8}),
        defeat('a10','La colère d’Orme','Les trois souvenirs sont revenus. Apaiser Orme à l’entrée de l’observatoire, en alternant esquive, épée et tir.',['keeper'],1,['a06','a08','a09']),
        visit('a11','Un banc pour deux','Rejoindre la halte centrale après le combat. Laisser au voyage une place sans urgence.',37,33,['a10']),
        visit('a12','La carte au-delà du ciel','Retrouver l’arche au sud-est. Toutes les autres étapes principales doivent être terminées avant le départ.',65,51,['a10','a11'])
    ]))
    worlds.append(dict(world=1,arc="La Canopée respire par un réseau vivant : pour rouvrir ses serres, il faut comprendre ce qui circule sans se voir.",missions=[
        talk('b01','Une forêt sous verre','Écouter Silo et retrouver la différence entre protéger une plante et l’enfermer.','guide'),
        talk('b02','Le vent dans les herbes','Pim confie une aile de feuilles. Observer comment l’air déplace les herbes avant de quitter le sol.','companion',['b01']),
        route('b03','La leçon de l’air','En parapente, franchir les ravines en reliant quatre clairières. Se poser entre les traversées pour reprendre son souffle.',4,[(20,39),(36,14),(63,22),(29,50)],['b02']),
        choose('b04','Ouvrir sans dessécher','Au carnet de la serre haute, choisir comment rendre son souffle au jardin.','observation_1',['Ouvrir les soupiraux et préserver l’eau des racines','Retirer toutes les vitres d’un seul coup','Fermer chaque ouverture pour garder la chaleur'],0,'La circulation d’air évite l’enfermement ; les racines ont toujours besoin d’eau. Le premier soupirail s’ouvre.',['b03'],reward={'flags':2}),
        collect('b05','Une réserve de graines','Retrouver quatre petits dépôts de mémoire sans épuiser tous les lieux à la fois.',['crystal_03','crystal_04','crystal_05','crystal_06','cache_1','cache_2'],4,['b01']),
        visit('b06','La serre sous la serre','Découvrir le petit jardin au fond du détour nord-ouest. Les racines dessinent un autre paysage.',7,8,['b04','b05']),
        choose('b07','Les voisins invisibles','Lire le carnet des racines et expliquer pourquoi un arbre peut dépendre d’un champignon.','observation_2',['Le champignon remplace toutes les feuilles','Les deux échangent des ressources utiles','Les racines mangent la roche sans aide'],1,'Certains filaments apportent eau et minéraux ; l’arbre leur fournit des sucres. La deuxième serre retrouve son réseau.',['b06'],reward={'flags':4}),
        defeat('b08','Les graines dans la nuit','Repousser les deux ombres du sud avant de rouvrir la banque des semences.',['sentinel_3','wanderer_5'],2,['b07']),
        choose('b09','Attendre le bon printemps','Au carnet des semences, choisir ce qu’il faut préserver pour que les graines puissent attendre.','observation_3',['Une chaleur maximale toute la journée','Un bain permanent dans l’eau','Une réserve fraîche et protégée'],2,'Une graine n’a pas besoin de germer tout de suite. La réserve lui permet d’attendre un milieu favorable. Le dernier soupirail s’ouvre.',['b08','b05'],reward={'flags':8}),
        defeat('b10','Le cerf de cristal','Apaiser Verrier sans confondre ses craquelures avec une blessure à agrandir.',['keeper'],1,['b04','b07','b09']),
        route('b11','Rapporter une graine','Revenir en parapente du grand jardin à la halte, puis aux serres. La route est devenue un lien dans les deux sens.',4,[(65,49),(37,33),(15,13),(63,22)],['b10']),
        visit('b12','L’odeur de la mer','Rejoindre la porte du Grand Poumon. La lumière qui la traverse porte déjà le sel de l’archipel.',65,51,['b11'])
    ]))
    worlds.append(dict(world=2,arc="Une cartographe, un facteur et une tortue-phare cherchent chacun une adresse. Leurs routes forment la même carte.",missions=[
        talk('c01','Une carte deux fois fausse','Rencontrer Iria. Sur une île, un chemin peut changer sans que le voyageur se trompe.','guide'),
        visit('c02','Le rivage à lire','Observer les traces du rivage dans la baie nord-ouest. Chercher ce que l’eau a laissé.',15,13,['c01']),
        choose('c03','Le travail du soleil','Au carnet des salines, retrouver ce qui reste quand l’eau s’évapore.','observation_1',['Le sel reste dans les bassins','Le vent transforme le sel en sable','L’eau devient du cuivre'],0,'L’eau peut s’évaporer, mais le sel dissous reste. Les bassins recueillent patiemment ce que la mer apporte. Le premier phare se rallume.',['c02'],reward={'flags':2}),
        talk('c04','Les lettres qui reviennent','Rencontrer Ollo. Il a conservé des lettres dont le trajet semblait terminé.','companion',['c01']),
        collect('c05','Les boîtes du courrier perdu','Ouvrir les trois réserves des voyageurs pour reconstruire la tournée qui reliait les îles.',['cache_1','cache_2','cache_3'],3,['c04']),
        route('c06','La poste des petites îles','Avec la voile de chute, rejoindre les quatre haltes dans l’ordre du courrier : baie, atelier, île sud, chenal.',2,[(15,13),(63,22),(29,50),(16,37)],['c04','c05'],reward={'flags':4}),
        choose('c07','Une forme qui grandit','Au phare des coquilles, expliquer ce que sa spirale permet de conserver en grandissant.','observation_2',['La même taille pour toujours','Une forme organisée malgré la croissance','Un mouvement perpétuel'],1,'La coquille ajoute de la matière en conservant une organisation reconnaissable. Le phare emprunte cette forme, pas un pouvoir magique.',['c06']),
        defeat('c08','Les veilleurs du chenal','Repousser deux ombres qui empêchent le courrier de traverser. Les îles doivent rester reliées après ton départ.',['wanderer_2','sentinel_3'],2,['c07']),
        choose('c09','Un repère qui ne se visite pas','Au carnet du phare des étoiles, choisir l’usage d’une étoile pour un navigateur.','observation_3',['Naviguer jusqu’à toucher l’étoile','Comparer sa direction et sa hauteur dans le ciel','Attendre qu’elle tombe sur le rivage'],1,'Une étoile aide à comparer une direction ou une hauteur. C’est un repère dans une carte du ciel. Le troisième phare retrouve son regard.',['c08'],reward={'flags':8}),
        defeat('c10','Le phare vivant','Apaiser Nacre. Sa carapace porte les lumières d’une route oubliée.',['keeper'],1,['c03','c06','c09']),
        visit('c11','L’adresse retrouvée','Revenir au jardin caché du sud-est. Les réponses aux lettres attendaient tout près du destinataire.',71,56,['c10']),
        visit('c12','La route du cuivre','Rejoindre l’arche du phare. Les prochains habitants ont besoin des idées que les îles ont conservées.',65,51,['c11'])
    ]))
    worlds.append(dict(world=3,arc="Les ateliers possèdent encore leurs machines. Ce qui leur manque est une façon de partager l’énergie, les outils et le savoir.",missions=[
        talk('d01','La ville des outils gardés','Écouter Tess. Une machine peut être entière et une ville pourtant arrêtée.','guide'),
        collect('d02','L’inventaire des ateliers','Retrouver cinq dépôts dans les différents ateliers, plutôt que vider une seule réserve.',['cache_1','cache_2','cache_3','crystal_05','crystal_06','crystal_09','crystal_10'],5,['d01']),
        choose('d03','Rassembler la lumière','Au jardin des miroirs, choisir comment chauffer un point sans inventer de l’énergie.','observation_1',['Tourner les miroirs pour renvoyer la lumière au même endroit','Couvrir les miroirs de sable','Faire tourner les miroirs dans le noir'],0,'Les miroirs concentrent une énergie reçue du soleil. La surface éclairée et les protections comptent aussi. Le premier atelier redémarre.',['d02'],reward={'flags':2}),
        talk('d04','Le véhicule réparable','Rencontrer Basile et prendre la trottinette. Repérer les pièces qu’un autre habitant pourrait réparer.','companion',['d01']),
        route('d05','Le réseau des courriers','En trottinette, relier la place, le jardin des miroirs, les engrenages et la réserve. Il faut livrer chaque atelier dans l’ordre.',5,[(16,37),(15,13),(63,22),(29,50),(37,33)],['d03','d04']),
        choose('d06','Vitesse contre force','Au carnet des engrenages, retrouver ce qu’une transmission peut réellement changer.','observation_2',['Créer de l’énergie en tournant plus vite','Échanger vitesse et force','Annuler tous les frottements'],1,'Les engrenages changent la relation entre vitesse et force. Les pertes et le travail nécessaire restent réels. Le deuxième atelier se remet en mouvement.',['d05'],reward={'flags':4}),
        defeat('d07','Une place pour les réparateurs','Dégager les routes de deux ombres pour que les apprentis puissent rejoindre les machines.',['wanderer_1','wanderer_2'],2,['d06']),
        visit('d08','La machine qui fait de l’ombre','Découvrir le petit jardin nord-ouest. Sa machine ne produit rien à vendre : elle protège les voyageurs.',7,8,['d07']),
        choose('d09','L’atelier après le coucher du soleil','À la réserve, décider comment garder une ville utile lorsque le jour s’arrête.','observation_3',['Dépenser toute la réserve avant le soir','Partager une réserve et limiter les besoins inutiles','Promettre que le soleil ne se couchera plus'],1,'Stocker aide, mais répartir les usages et réduire les pertes permet aussi de traverser la nuit. La réserve commune rallume le troisième atelier.',['d08'],reward={'flags':8}),
        defeat('d10','L’horloge sans retard','Apaiser Méridien, qui confondait précision et obligation de ne jamais s’arrêter.',['keeper'],1,['d03','d06','d09']),
        route('d11','Une dernière livraison','En trottinette, ramener les outils aux trois haltes avant de quitter les ateliers. La ville doit continuer sans attendre ton retour.',5,[(65,49),(63,22),(29,50),(16,37)],['d10']),
        visit('d12','L’heure des sommets','Rejoindre l’Horloge du Zénith. Son cadran est une route vers les stations du ciel.',65,51,['d11'])
    ]))
    worlds.append(dict(world=4,arc="Les stations voient chacune une partie du ciel. Comprendre la pluie exige de réunir des observations, pas de trouver un instrument parfait.",missions=[
        talk('e01','Les pieds des îles','Rencontrer Anouk. Les montagnes ne flottent pas : les nuages en cachent les pieds.','guide'),
        talk('e02','La règle de la pilote','Préparer le petit avion avec Eden. Un vol se prépare en gardant un endroit où revenir au sol.','companion',['e01']),
        route('e03','La première boucle du ciel','En avion, relier les quatre terrains de repos. Refaire ses réserves au sol entre les traversées.',3,[(16,37),(36,14),(63,22),(29,50)],['e02']),
        choose('e04','D’où vient le vent ?','Au carnet des vents, expliquer le rôle de la girouette.','observation_1',['Elle fabrique le vent','Elle indique d’où vient le vent','Elle mesure la distance aux étoiles'],1,'La girouette se place selon l’air qui arrive. Différentes couches d’air peuvent suivre des directions différentes. La station du vent retrouve sa mesure.',['e03'],reward={'flags':2}),
        collect('e05','Des observations espacées','Retrouver quatre dépôts entre les stations. Une série de mesures doit conserver plusieurs lieux, pas seulement plusieurs nombres.',['crystal_04','crystal_05','crystal_06','crystal_08','crystal_09','cache_2'],4,['e04']),
        choose('e06','La matière d’un nuage','Au carnet de pluie, choisir ce que contient le nuage visible.','observation_2',['De la fumée blanche','Seulement un vide froid','De minuscules gouttes ou cristaux de glace'],2,'La vapeur d’eau est invisible. En refroidissant, elle peut former des gouttes ou des cristaux : le nuage devient visible. La station des averses se réveille.',['e05'],reward={'flags':4}),
        visit('e07','L’autre côté de la carte','Découvrir l’île cachée près du détour nord-ouest. Le dos d’une carte peut garder un ancien projet.',7,8,['e06']),
        defeat('e08','Le passage des astronomes','Repousser les deux ombres près des stations du nord et du sud pour ouvrir la tournée nocturne.',['wanderer_4','sentinel_3'],2,['e07']),
        choose('e09','Éteindre pour regarder','Au refuge des astronomes, choisir ce qui aide à voir une étoile faible.','observation_3',['Allumer tous les projecteurs vers le ciel','Réduire les lumières inutiles et laisser les yeux s’adapter','Regarder uniquement les objets les plus brillants'],1,'Une lumière proche peut cacher une lumière lointaine. Protéger la nuit rend visibles des étoiles que la puissance d’une lampe ne révèle pas. Le troisième refuge s’ouvre.',['e08'],reward={'flags':8}),
        defeat('e10','L’oiseau des relevés','Apaiser Cirrus. Ses plumes portent les mesures qu’aucune station ne pouvait lire seule.',['keeper'],1,['e04','e06','e09']),
        route('e11','La constellation terrestre','En avion, relier les points de la constellation dessinée par les stations, puis revenir à la grande arche.',3,[(15,13),(63,22),(29,50),(65,49)],['e10']),
        visit('e12','Au cœur des racines','Rejoindre l’arche au-delà des nuages. Tous les voyages convergent maintenant vers le Grand Arbre.',65,51,['e11'])
    ]))
    worlds.append(dict(world=5,arc="Le Grand Arbre ne réclame pas six trophées. Il demande que les façons d’apprendre, de réparer et de partager deviennent un seul jardin.",missions=[
        talk('f01','Maëlle, autrement','Retrouver Maëlle sous le Grand Arbre. Le retour change autant la personne qui accueille que celle qui arrive.','guide'),
        collect('f02','Ce que les mondes ont confié','Réunir les trois réserves des jardins. Ce qu’elles représentent compte davantage que leur valeur en éclats.',['cache_1','cache_2','cache_3'],3,['f01']),
        choose('f03','Un jardin qui n’est pas une copie','Au carnet du vivant, décider comment accueillir les graines venues d’ailleurs.','observation_1',['Tout planter de la même façon sans observer le lieu','Observer le milieu et préserver la diversité','Remplacer toutes les plantes déjà présentes'],1,'Une graine arrive avec une histoire, mais rencontre un nouveau milieu. Observer permet d’accueillir sans effacer ce qui vit déjà. Le jardin du vivant s’ouvre.',['f02'],reward={'flags':2}),
        talk('f04','Une place pour les autres','Retrouver Nino et sa petite voiture. Elle transporte aussi les voyageurs trop fatigués pour finir la route à pied.','companion',['f01']),
        route('f05','La tournée des retours','Avec la voiture, relier le village, les jardins et l’atelier. Ramener les ressources là où elles pourront servir après ton passage.',7,[(16,37),(15,13),(63,22),(29,50),(37,33)],['f03','f04']),
        choose('f06','L’invention qui continue','Au carnet des mains, choisir ce qui rend un outil durable au-delà de son inventeur.','observation_2',['Cacher la méthode pour rester indispensable','Le rendre impossible à ouvrir','Expliquer comment le réparer et partager ses plans'],2,'Une invention continue de servir quand d’autres peuvent la comprendre, la réparer et l’adapter. L’atelier des liens retrouve sa lumière.',['f05'],reward={'flags':4}),
        defeat('f07','Les portes encore fermées','Repousser les deux ombres qui isolent les jardins. Les chemins doivent rester ouverts à ceux qui viendront ensuite.',['wanderer_1','wanderer_5'],2,['f06']),
        visit('f08','La graine du premier jour','Rejoindre le petit jardin nord-ouest. La première graine avait commencé à pousser bien avant la dernière porte.',7,8,['f07']),
        choose('f09','Le souvenir que l’on partage','Au carnet des voix, choisir ce que signifie transmettre un souvenir.','observation_3',['Imposer à tout le monde le même récit','Donner des repères et laisser les autres ajouter leur histoire','Fermer le jardin pour que rien ne change'],1,'Transmettre ne fige pas le monde. Cela laisse des repères et une place aux nouvelles voix. Le dernier jardin se rallume.',['f08'],reward={'flags':8}),
        defeat('f10','La place laissée à l’Oubli','Affronter le gardien des portes fermées. Ce combat conclut les apprentissages du voyage ; il ne les remplace pas.',['keeper'],1,['f03','f06','f09']),
        route('f11','Le chemin à pied','Revenir à pied du grand jardin jusqu’au premier banc, puis parcourir les trois jardins. Prendre le temps de reconnaître ce qui a changé.',0,[(65,49),(37,33),(15,13),(63,22),(29,50)],['f10']),
        visit('f12','Une place pour le prochain départ','Rejoindre le cœur du Grand Arbre. La conclusion laisse les mondes ouverts à l’exploration et aux retours.',65,51,['f11'])
    ]))
    for world in worlds:
        i=world['world']; prefix='abcdef'[i]; titles=[('La question qui voyage','La graine à deux ailes','Ce qui se transmet','Le dessin du voyage'),('Le réseau invisible','Le carnet sous l’écorce','Observer sans arracher','Un échantillon vivant'),('Le message sans destinataire','Une adresse sous la marée','Le prochain voyageur','Réparer une boîte'),('Le vélo aux deux roues','Le dessin des rapports','Aucun rapport pour tout','Le vélo de Basile'),('La pluie qui n’arrivait pas','Une mesure sans contexte','L’autre versant','Les pages de demain'),('Une place pour demain','La ligne laissée libre','Le carnet ouvert','Les graines différentes')][i]
        world['missions'].extend([
            talk(prefix+'13',titles[0],'Rencontrer la personne au sud-ouest qui a conservé une question plutôt qu’une réponse.','sidequest_start',[prefix+'01'],required=False),
            talk(prefix+'14',titles[1],'Retrouver la plaque au nord-ouest et lire son observation. Le lieu et le texte sont deux parties du même indice.','sidequest_clue',[prefix+'13'],required=False),
            talk(prefix+'15',titles[2],'Rejoindre la pierre du jardin sud avec l’indice retrouvé. Elle relie la question à une manière d’agir.','sidequest_memory',[prefix+'14'],required=False),
            collect(prefix+'16',titles[3],'Ouvrir la boîte à l’est du jardin sud. Son cadeau garde la trace de ce que tu as compris.',['sidequest_reward'],1,[prefix+'15'],required=False,reward={'vehicle':6} if i==3 else {'crystals':2})
        ])
    dungeon_manifest=ROOT/'dungeons/manifest.json'
    if dungeon_manifest.exists() and json.loads(dungeon_manifest.read_text()).get('integrated'):
        worlds[0]['missions']=[m for m in worlds[0]['missions'] if m['id']!='a16']
        worlds[0]['missions'].append(mission('a17_sanctuary','Le Jardin sous les Racines',"Entrer dans le sanctuaire près du jardin nord, traverser ses dix salles et retrouver la première graine. Les interrupteurs, tirs, caisses, dalles et séquences y conservent leurs états.",'dungeon',['a09'],target_world=15,complete_flags=32))
        next(m for m in worlds[0]['missions'] if m['id']=='a12')['requires'].append('a17_sanctuary')
    canopy_manifest=ROOT/'canopy_candidate/manifest.json'
    if canopy_manifest.exists() and json.loads(canopy_manifest.read_text()).get('integrated'):
        worlds[1]['missions']=[m for m in worlds[1]['missions'] if m['id']!='b16']
        worlds[1]['missions'].append(mission('b17_herbarium',"L'Herbier des Ombres","Après avoir retrouvé le carnet sous l'écorce et la mémoire du jardin sud, entrer dans la serre souterraine au nord du passage central. Traverser les dix chambres de lumière, d'ombre et de semences, puis rapporter l'herbier à Silo.",'dungeon',['b15'],target_world=25,complete_flags=32,required=False,reward={'crystals':2}))
    reflections_manifest=ROOT/'reflections_candidate/manifest.json'
    reflections_integrated=reflections_manifest.exists() and json.loads(reflections_manifest.read_text()).get('integrated')
    if reflections_integrated:
        connection=json.loads((ROOT/'reflections_candidate/integration.json').read_text())['phase_one']
        replacement=connection['replace_mission']
        worlds[2]['missions']=[replacement['new'] if m['id']==replacement['old_id'] else m for m in worlds[2]['missions']]
    data=dict(schema=1,title='LUMA — Les Jardins du Souvenir',duration=dict(design_goal_hours=[6,10],measured_campaign_minutes=None,reference_prototype_minutes=34.1,note='The missions and first sanctuary are an initial gameplay extension, not a measured multi-hour campaign. Additional playable spaces and mechanics plus playtesting are required to substantiate the global duration target.'),runtime_contract=dict(max_worlds=96,max_missions_per_world=16,local_mission_ids=True,successful_prior_interactions_count=True,collection_and_defeat_retroactive=True,choices_retry_without_loss=True,route_progress_persistent=True,all_required_missions_gate_forward_portals=True),worlds=worlds)
    if canopy_manifest.exists() and json.loads(canopy_manifest.read_text()).get('integrated'):
        data['mission_changes']=[dict(world=1,removed='b16',added='b17_herbarium',mapping='No completion transfer: new activity has a new persistent ID.',preserved='b01..b15 IDs, existing chest sidequest_reward, inventory, collected objects and every vehicle unlock.',reward='Old b16 granted two extra crystals, never a vehicle. Already earned crystals remain in inventory; b17 grants its own two crystals only on completion.')]
        data['duration']['note']='Two playable sanctuaries extend the prototype. Their oracle traversal times are not human playtimes; a multi-hour campaign remains an unverified design goal.'
    if reflections_integrated:
        data.setdefault('mission_changes',[]).append(dict(world=2,removed='c16',added='c17_reflections',mapping='No completion transfer: new activity has a new persistent ID.',preserved='c01..c15 IDs, existing chest sidequest_reward, inventory, collected objects and every vehicle unlock.',reward='Old c16 granted two extra crystals, never a vehicle. Previously earned crystals stay acquired. New c17 grants its own two crystals and local flag 512, reopening both ends of the gallery only once.'))
        data['duration']['note']='Three playable sanctuaries extend the prototype with distinct mechanisms. Oracle traversal times do not measure human playtime; a multi-hour campaign remains an unverified design goal.'
    (ROOT/'campaign_arcs.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f"Authored {sum(len(w['missions']) for w in worlds)} runtime missions. Duration remains unmeasured.")

if __name__=='__main__':main()
