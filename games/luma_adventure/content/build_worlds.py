#!/usr/bin/env python3
"""Build LUMA's authored campaign. Only writes this content directory."""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
W, H, TILE = 80, 64, 32

# World names, characters, discoveries and locations are authored. Terrain detail
# uses an explicit seed; paths are carved only after obstacles and landmarks.
CHAPTERS = [
    dict(id="aube", name="Le Val des Lanternes", subtitle="La lumière se souvient",
         guide="Maëlle, gardienne des graines", guide_art="npc_maelle", vehicle=1,
         greeting="Tu arrives juste avant la pluie d'étoiles. Depuis que le Grand Arbre s'est tu, nos lanternes oublient leur couleur. Je m'appelle Maëlle. Approche les trois balises : chacune garde un souvenir différent.",
         after_guide="La balise du verger est au nord-ouest, celle du moulin à l'est, celle des roseaux au sud. Les sentiers se rejoignent : tu peux choisir ton chemin.",
         biomes=["Bois des Chuchotis", "Verger des Lucioles", "Moulin du Petit Vent", "Prairies de Traverse", "Marais des Reflets", "Observatoire endormi"],
         beacons=[("Le verger qui chante", "Les arbres répondent aux lucioles. En laissant des fleurs entre les vergers, Maëlle protège les pollinisateurs."), ("La roue et la rivière", "L'eau descend ; la roue transforme son mouvement en lumière. Tu as retrouvé le souvenir du courant."), ("Le miroir des roseaux", "Le ciel semble sous tes pieds. Les roseaux freinent l'eau et abritent les jeunes poissons.")],
         keeper="Orme, gardien des saisons", keeper_text="Sous la pierre, Orme reconnaît enfin la voix de Maëlle. Sa colère venait d'un souvenir brisé.",
         companion="Nino, facteur des chemins", companion_text="J'avais perdu le chemin de chez moi. Puis j'ai suivi les moulins : leurs ailes regardent toutes le même vent. Prends mon cheval Brindille, il connaît les passages.",
         secret="Une lettre à demain", secret_text="Dans la boîte : « Quand la forêt reviendra, plante cet éclat là où tu aimerais t'asseoir. » Quelqu'un attendait ton arrivée depuis longtemps.",
         discovery="Le pont des deux ombres", discovery_text="À midi, les deux arbres se touchent par leurs ombres. Sous le pont, tu découvres une ancienne route des jardiniers.",
         closing="L'observatoire s'ouvre. Au-delà de son arche, une forêt respire à travers mille verrières.",
         palette={".":"#719b53","t":"#315e43","~":"#3c9eaa","=":"#d3b57b","#":"#66776d",":":"#d7c58d",",":"#91a962"}),
    dict(id="canopée", name="La Canopée de Verre", subtitle="Apprendre à écouter",
         guide="Silo, botaniste des hauteurs", guide_art="npc_silo", vehicle=4,
         greeting="Les grandes serres ne sont pas des prisons pour les arbres : ce sont leurs instruments. Quelqu'un a fermé les trois soupiraux et la forêt ne respire plus. Je t'ai cousu une aile de feuilles pour traverser les ravines.",
         after_guide="Cherche l'air dans la serre haute, l'eau près des racines et les graines dans la clairière. Écoute avant de couper : ici, même les silences ont une direction.",
         biomes=["Serres d'Émeraude", "Jardin des Échos", "Passerelle des Nuages", "Racines suspendues", "Clairière des Semences", "Grand Poumon de verre"],
         beacons=[("Le souffle des feuilles", "Les nervures conduisent l'eau dans la feuille. Le soupirail ouvert rend son souffle à la serre."), ("La soif des racines", "Sous la surface, racines et filaments de champignons échangent des ressources. Un arbre isolé n'est jamais tout à fait seul."), ("La banque des graines", "Des graines patientaient dans l'obscurité. Tu as ouvert les volets, sans enlever la fraîcheur qui les protège.")],
         keeper="Verrier, le cerf de cristal", keeper_text="Les craquelures du cerf deviennent des branches. Il ne gardait pas un trésor : il protégeait la dernière graine.",
         companion="Pim, réparatrice de cerfs-volants", companion_text="Le vent se voit dans ce qu'il déplace. Observe les herbes avant de quitter le sol. Mon parapente ne fait pas de toi un oiseau, mais il t'apprend à regarder comme lui.",
         secret="Le jardin inversé", secret_text="Une serre poussait sous la serre. Les jardiniers avaient laissé pousser les racines comme une autre forêt.",
         discovery="L'arbre qui voyage", discovery_text="Les graines ailées tournent en tombant. L'air les emporte plus loin de leur arbre ; tu retrouves ce dessin dans ton parapente.",
         closing="La dernière vitre devient une porte. De l'autre côté, la mer fait sonner des cloches de cuivre.",
         palette={".":"#4f8b75","t":"#1d534e","~":"#3d9fac","=":"#b9ba86","#":"#668b89",":":"#c6c49a",",":"#9fb47f"}),
    dict(id="marées", name="L'Archipel des Marées", subtitle="Ce que la mer rapporte",
         guide="Iria, cartographe des courants", guide_art="npc_iria", vehicle=2,
         greeting="Ma carte est fausse deux fois par jour : la mer déplace ses chemins. Les trois phares se sont éteints et les courriers tournent en rond. Mes voiles de chute t'aideront à rejoindre les îles.",
         after_guide="Le phare du sel est au nord-ouest, celui des coquilles à l'est, celui des étoiles au sud. Les ponts restent praticables même lorsque les rochers semblent disparaître.",
         biomes=["Salines de Porcelaine", "Baie des Coquillages", "Atelier des Voiliers", "Chenal des Lanternes", "Île des Veilleurs", "Phare à rebours"],
         beacons=[("Le phare du sel", "Le soleil et le vent emportent l'eau des bassins ; les cristaux de sel restent. Les paludiers guident l'eau sans la presser."), ("Le phare des coquilles", "La spirale d'une coquille grandit sans quitter sa forme. Les bâtisseurs s'en sont inspirés pour l'escalier du phare."), ("Le phare des étoiles", "Les marins regardent un point fixe dans le ciel et comparent sa hauteur. Une étoile devient un repère, pas une destination.")],
         keeper="Nacre, la tortue des courants", keeper_text="La tortue cesse de tourner. Elle portait des balises sur sa carapace : un phare vivant cherchait le rivage.",
         companion="Ollo, réparateur de bouteilles", companion_text="On répare des bateaux, mais aussi les messages qu'ils n'ont jamais livrés. Cette lettre était pour une personne qui habite encore ici. Un voyage peut finir à deux rues de son départ.",
         secret="La poste de la marée basse", secret_text="La boîte contenait des réponses, pas des lettres. Les habitants savaient depuis longtemps que quelqu'un finirait par poser les bonnes questions.",
         discovery="Le sable qui se souvient", discovery_text="Coquilles brisées, cailloux arrondis, grains sombres : chaque poignée raconte plusieurs montagnes et plusieurs vies.",
         closing="Les phares accordent leurs lumières. Un petit train de lanternes désigne les ateliers du désert.",
         palette={".":"#92b77e","t":"#477768","~":"#338fa9","=":"#e2cf9e","#":"#7e9d9a",":":"#ebdcb3",",":"#d7b2b8"}),
    dict(id="cuivre", name="Les Ateliers du Soleil", subtitle="Inventer ensemble",
         guide="Tess, mécanicienne des dunes", guide_art="npc_tess", vehicle=5,
         greeting="Nos machines marchaient avec le soleil et un peu d'entraide. Maintenant, chacun garde son outil et rien ne marche. Relie les trois ateliers : chaleur, mouvement et réserve. Je te prête ma trottinette solaire.",
         after_guide="L'atelier des miroirs se trouve au nord-ouest, la grande roue à l'est et les accumulateurs au sud. Une invention ne sert que si quelqu'un peut la réparer après toi.",
         biomes=["Jardin des Miroirs", "Dunes de Safran", "Place des Engrenages", "Route des Courriers", "Réserve de l'Orage", "Horloge du Zénith"],
         beacons=[("Le soleil apprivoisé", "Des miroirs renvoient la lumière vers le même point. La chaleur recueillie devient utile lorsqu'on sait aussi protéger ce qui l'entoure."), ("La roue patiente", "Une grande roue fait tourner une petite roue plus vite. Vitesse et force s'échangent ; les engrenages ne créent pas d'énergie."), ("La réserve de la nuit", "La journée ne dure pas toujours. Les ateliers partagent leur réserve pour éclairer la ville lorsque le soleil disparaît.")],
         keeper="Méridien, l'automate horloger", keeper_text="L'horloger arrête de compter les retards. Sous sa coque, un minuscule cadran indique seulement : « ensemble ».",
         companion="Basile, coureur aux cent détours", companion_text="Mon vélo a déjà perdu une course et trouvé trois amis. Si tu roules sur le chemin de cuivre, tu verras où les apprentis ont ajouté leurs propres pièces.",
         secret="La machine inutile", secret_text="Cette machine ne fabrique rien. Elle projette l'ombre d'un arbre pour les voyageurs. Tess refuse qu'on l'appelle inutile.",
         discovery="Le cadran sans aiguilles", discovery_text="Un bâton et son ombre suffisent à comparer les heures. L'ombre change de direction parce que la Terre tourne.",
         closing="L'horloge ouvre son cadran. Une route de cuivre grimpe dans des montagnes bleues, là où les nuages se fabriquent.",
         palette={".":"#b8a768","t":"#657857","~":"#689fa4","=":"#c58d59","#":"#a67a6c",":":"#e0bd78",",":"#c49b68"}),
    dict(id="nuages", name="La Mer des Nuages", subtitle="Voir plus loin",
         guide="Anouk, pilote des pluies", guide_art="npc_anouk", vehicle=3,
         greeting="On dit que mes îles flottent. En réalité, les nuages cachent leurs pieds. Les trois stations ont perdu leur mesure du ciel. Mon avion peut suivre la route des sommets ; reviens au sol pour refaire tes réserves.",
         after_guide="Mesure le vent au nord-ouest, retrouve la pluie à l'est, puis allume le refuge des étoiles au sud. La montagne accepte les détours ; elle ne récompense pas la hâte.",
         biomes=["Aiguilles d'Azur", "Terrasses du Vent", "Station des Averses", "Route des Cimes", "Refuge des Astronomes", "Océan du ciel"],
         beacons=[("L'aiguille du vent", "Une girouette indique d'où vient le vent. Les pilotes observent aussi les nuages : plusieurs couches d'air peuvent suivre des chemins différents."), ("La fabrique de pluie", "La vapeur d'eau se condense en minuscules gouttes lorsque l'air refroidit. Un nuage n'est pas fait de fumée."), ("Le refuge des étoiles", "Éteindre une lanterne aide parfois à voir plus loin. Le refuge protège sa nuit pour retrouver les étoiles faibles.")],
         keeper="Cirrus, le grand oiseau d'étain", keeper_text="Cirrus replie ses ailes. Ses plumes sont des relevés météo ; il cherchait un endroit où déposer toutes les pluies.",
         companion="Eden, observateur des ombres", companion_text="J'ai voulu dessiner tout le ciel. Puis j'ai appris à noter une chose, chaque jour, au même endroit. Une petite observation répétée peut raconter une grande histoire.",
         secret="L'île qui n'était pas sur la carte", secret_text="L'île était dessinée au dos. Anouk avait retourné sa carte pour en faire un cerf-volant lorsqu'elle était enfant.",
         discovery="L'écho du petit refuge", discovery_text="Une paroi renvoie ta voix après un court délai. Le son parcourt le chemin aller et le chemin retour : l'écho mesure aussi la distance.",
         closing="Les stations dessinent une constellation sur le sol. Son dernier point brille au cœur du Grand Arbre.",
         palette={".":"#a1baaf","t":"#547d83","~":"#c3dde0","=":"#d7c8aa","#":"#798eaa",":":"#d9dfe0",",":"#a6aec7"}),
    dict(id="racines", name="Le Jardin des Retours", subtitle="Ce que l'on choisit de garder",
         guide="Maëlle, sous le Grand Arbre", guide_art="npc_maelle", vehicle=7,
         greeting="Tu as rapporté des graines, des lettres, des outils et des histoires. Le Grand Arbre ne demandait pas un héros : il attendait que les mondes se parlent de nouveau. Porte leurs trois souvenirs jusqu'au cœur des racines.",
         after_guide="Le premier jardin garde ce qui pousse, le deuxième ce que l'on construit, le dernier ce que l'on partage. Tous les chemins que tu as appris se retrouvent ici.",
         biomes=["Jardin de Ce Qui Pousse", "Allée des Anciennes Lettres", "Atelier de Ce Qui Relie", "Route des Retours", "Clairière des Promesses", "Cœur du Grand Arbre"],
         beacons=[("Le souvenir du vivant", "Les graines de la Canopée trouvent ici une nouvelle terre. Elles portent le souvenir des jardins sans en faire des copies."), ("Le souvenir des mains", "Les outils du désert réparent le canal de l'archipel. Les inventions voyagent mieux quand on explique comment les refaire."), ("Le souvenir des voix", "Les lettres retrouvent leurs destinataires. Les mots n'ont pas changé, mais celles et ceux qui les lisent ont grandi.")],
         keeper="L'Oubli, gardien des portes fermées", keeper_text="L'Oubli n'était pas un ennemi venu d'ailleurs. C'était la place laissée vide entre les mondes. La lumière y fait de nouveau un chemin.",
         companion="Nino, revenu de partout", companion_text="Cette petite voiture transporte des outils, des graines et les amis trop fatigués pour marcher. La plus grande invention du voyage, c'est de pouvoir revenir ensemble.",
         secret="La graine de ton premier jardin", secret_text="La graine du village avait déjà germé. Ton aventure n'a pas attendu la dernière porte pour changer quelque chose.",
         discovery="Le banc de tous les départs", discovery_text="Les noms des voyageurs sont gravés sous le banc, à l'abri de la pluie. Tu laisses une place pour la prochaine personne.",
         closing="Le Grand Arbre rallume ses lanternes. Les six mondes respirent ensemble. Tes découvertes restent ouvertes : chaque retour peut commencer une autre histoire.",
         palette={".":"#7da272","t":"#3b6864","~":"#589da6","=":"#d4bd92","#":"#818689",":":"#dcd0a8",",":"#c69cb0"})
]

SIDEQUESTS = [
    ("Ada, collectionneuse de questions", "La question qui voyage", "J'ai trouvé une devinette : qu'est-ce qui peut voyager sans avoir de jambes ? Cherche la petite plaque au bord du bois, au nord-ouest. Puis suis ce qu'elle t'apprendra jusqu'au jardin du sud.", "La graine à deux ailes", "Une graine voyage avec le vent, un message avec une personne, une idée avec ceux qui la comprennent. La pierre du jardin sud attend un souvenir que l'on peut transmettre.", "Ce qui se partage ne disparaît pas toujours. Ada a laissé une boîte près du détour, à l'est du jardin.", "Tu trouves un dessin de ton voyage, tracé avant ton arrivée. Les mêmes routes accueillent des histoires différentes."),
    ("Boro, chercheur de champignons", "Le réseau invisible", "On accuse les champignons de voler la nourriture des arbres. Mes observations racontent autre chose. Lis mon carnet au nord-ouest, puis retrouve la pierre au sud pour réunir les indices.", "Le carnet sous l'écorce", "Des filaments de champignons aident certaines racines à absorber eau et minéraux ; l'arbre leur fournit des sucres. Cet échange s'appelle une symbiose. La pierre du jardin sud garde la suite.", "Boro avait observé les racines sans les arracher. Tu assembles son carnet ; sa boîte d'échantillons est à l'est du jardin.", "Dans la boîte, un champignon sculpté dans le bois. Le véritable échantillon a été laissé dans la forêt, là où il est utile."),
    ("Lise, gardienne des bouteilles", "Le message sans destinataire", "Une bouteille est revenue trois fois sans que personne l'ouvre. Le sceau porte le dessin d'une coquille. Lis la plaque du rivage nord-ouest, puis rejoins le jardin sud.", "Une adresse sous la marée", "« À la personne qui trouvera ceci : quelqu'un a construit un pont pour toi sans savoir ton nom. Un jour, répare-le pour quelqu'un d'autre. » La suite est gravée sur la pierre du jardin sud.", "Le message n'était pas perdu. Il était destiné à chaque personne qui le lirait. Une boîte attend à l'est du jardin.", "Une petite clé et du fil de cuivre : juste de quoi réparer la boîte aux lettres du quai. Les grands voyages ont parfois de très petits bagages."),
    ("Ada, apprentie des engrenages", "Le vélo aux deux roues", "Basile dit que son vélo avance mieux avec des questions qu'avec des réponses. Retrouve son dessin au nord-ouest, puis sa maquette dans le jardin sud. Il te prêtera son vélo si tu comprends ce qu'il a changé.", "Le dessin des deux roues", "Une roue dentée entraîne l'autre par une chaîne. Le rapport entre leurs tailles change l'effort et la distance parcourue à chaque tour de pédale. Compare-les sur la pierre du jardin sud.", "La maquette révèle deux rapports pour la même route. Aucun n'est meilleur partout. Basile et son vélo t'attendent à l'est du jardin.", "Le vélo de Basile est à toi. Ses réparations restent visibles : chaque pièce raconte quelqu'un qui a refusé de le jeter."),
    ("Ivo, apprenti météorologue", "La pluie qui n'arrivait pas", "J'ai noté une semaine de nuages, mais oublié la direction du vent. Retrouve ma première mesure au nord-ouest, puis la pierre des observations au sud. Un chiffre sans contexte peut raconter n'importe quoi.", "Le cahier des vents", "Lundi : air humide venu de la mer. Mardi : le même air rencontre la montagne et monte. En altitude, il refroidit. Les observations suivantes t'attendent au jardin sud.", "Tu relies les observations : la pluie est tombée sur l'autre versant. Ivo n'avait pas tort de regarder ici ; il lui manquait un autre point de vue. Sa boîte attend à l'est.", "Ivo partage ses pages blanches. Tu ne gagnes pas une prévision parfaite : tu sais maintenant quoi observer demain."),
    ("Ada, devenue passeuse", "Une place pour demain", "Nous avons gardé les souvenirs des autres. Il manque ce que nous voulons transmettre. Relis la petite plaque du nord-ouest, puis viens au jardin sud. Personne ne peut choisir ce souvenir à ta place.", "La place laissée vide", "Sous les noms des anciens voyageurs, une ligne est restée libre. Le Grand Arbre n'a jamais été achevé : chaque génération lui ajoute un chemin. La pierre du sud garde une place pour toi.", "Tu poses ton premier carnet sur la pierre. D'autres pourront y ajouter leurs découvertes. Ada a laissé une dernière boîte à l'est du jardin.", "La boîte est pleine de graines différentes. Une étiquette dit seulement : « Ne plante pas tout au même endroit. Laisse le monde te surprendre. »")
]


def build(ch, index):
    rng = random.Random(10623 + index * 1009)
    rows = [["." for _ in range(W)] for _ in range(H)]
    # Regional ground and winding water feature; land bridges follow the paths.
    for y in range(H):
        for x in range(W):
            if x in (0, W-1) or y in (0, H-1):
                rows[y][x] = "#"
            elif index == 2 and ((x-42)**2/24**2 + (y-31)**2/20**2 > 1.25):
                rows[y][x] = "~"
            elif index == 3:
                rows[y][x] = ":" if rng.random() < .87 else "."
            elif index == 4 and ((x//13 + y//11) % 3 == 0):
                rows[y][x] = "~"
            elif x < 24 and y < 25:
                rows[y][x] = "t" if rng.random() < .56 else ","
            elif x > 52 and y < 30:
                rows[y][x] = ":" if rng.random() < .7 else "."
            elif y > 43 and x < 38:
                rows[y][x] = "," if rng.random() < .5 else "."
            elif rng.random() < .035:
                rows[y][x] = "t"
    for y in range(2,H-2):
        mid = 43 + round(3*math.sin(y*.16 + index))
        for x in range(mid-1,mid+2):
            rows[y][x] = "~"
    # Six visually distinct areas with loops, a central hub, and generous paths.
    hubs = [(15,13),(36,14),(63,22),(16,37),(29,50),(65,49)]
    def clear(cx,cy,r=3,char="."):
        for yy in range(max(1,cy-r),min(H-1,cy+r+1)):
            for xx in range(max(1,cx-r),min(W-1,cx+r+1)):
                if (xx-cx)**2+(yy-cy)**2 <= (r+.5)**2:
                    rows[yy][xx] = char
    def path(a,b):
        x,y=a; bx,by=b
        while (x,y)!=(bx,by):
            clear(x,y,0,"=")
            if x!=bx:x += 1 if bx>x else -1
            elif y!=by:y += 1 if by>y else -1
        clear(x,y,0,"=")
    for a,b in [(hubs[0],hubs[1]),(hubs[1],hubs[2]),(hubs[2],hubs[5]),(hubs[5],hubs[4]),(hubs[4],hubs[3]),(hubs[3],hubs[0]),(hubs[3],hubs[2]),(hubs[1],hubs[4])]:
        path(a,b)
    for p in hubs:clear(*p,3,":" if index in (2,3) else ".")
    entities=[]
    def add(eid,kind,x,y,name,text="",after="",requires=0,grants=0,cost=0,vehicle=0,art=None,**extra):
        clear(x,y,2)
        # Every point is connected to its closest hub on the pedestrian graph.
        hub=min(hubs,key=lambda p:abs(p[0]-x)+abs(p[1]-y))
        path(hub,(x,y))
        entity=dict(id=eid,kind=kind,x=x*TILE+16,y=y*TILE+16,name=name,text=text,dialogue=[text] if text else [],after=after,requires=requires,grants=grants,cost=cost,vehicle=vehicle,art=art or kind)
        entity.update(extra);entities.append(entity)
    add("guide","npc",15,35,ch['guide'],ch['greeting'],ch['after_guide'],grants=1,vehicle=0,art=ch['guide_art'])
    add("companion","npc",20,39,ch['companion'],ch['companion_text'],requires=1,vehicle=ch['vehicle'],art="npc_companion")
    add("stable","stable",12,40,"La halte des voyageurs",ch['companion_text'],requires=1,vehicle=ch['vehicle'],art=["horse","glider","parachute","scooter","plane","car"][index])
    for n,((x,y),(name,after)) in enumerate(zip([hubs[0],hubs[2],hubs[4]],ch['beacons'])):
        add(f"beacon_{n+1}","shrine",x,y,name,after=after,requires=1,grants=2<<n,cost=2,art="shrine")
        add(f"sentinel_{n+1}","enemy",x+3,y-2,"Éclat d'oubli",requires=1,art="enemy")
        add(f"cache_{n+1}","chest",x-4,y+3,"Réserve des voyageurs",after="Trois éclats sont restés au sec dans cette boîte. Les anciens voyageurs pensaient à ceux qui viendraient ensuite.",cost=3,art="chest")
        add(f"observation_{n+1}","sign",x-3,y-4,"Carnet d'observation",text=after,art="sign")
    add("keeper","boss",65,44,ch['keeper'],after=ch['keeper_text'],requires=14,grants=16,art=['boss','boss_cerf','boss_tortue','boss_clock','boss_bird','boss_root'][index])
    add("observatory","portal",65,51,ch['biomes'][-1],after=ch['closing'],requires=30,grants=32,art="portal",target_world=index+1 if index<5 else -1)
    if index:
        add("return_gate","portal",10,35,"Le chemin du retour",after="Le chemin reste ouvert. Ce que tu as réveillé ne s'efface pas quand tu pars.",art="portal",target_world=index-1,target_x=65*TILE+16,target_y=53*TILE+16,return_portal=True)
    add("secret_letter","chest",7,8,ch['secret'],after=ch['secret_text'],cost=5,art="chest",secret=True)
    add("secret_garden","chest",71,56,"Le jardin derrière la porte",after="Une lanterne minuscule veille sur un banc. Le trésor de ce lieu était aussi le détour pour le trouver.",cost=4,art="chest",secret=True)
    add("discovery","sign",35,12,ch['discovery'],text=ch['discovery_text'],art="sign")
    add("map_sign","sign",17,32,"Les routes de ce monde",text="Les chemins clairs relient les trois balises. Les lanternes marquent les haltes. Ouvre la carte pour te repérer, le journal pour retrouver ton objectif. Les détours cachent des coffres et des histoires.",art="sign")
    add("rest","npc",37,33,"Miette, voyageuse sans montre",text="Je compte les voyages en rencontres, jamais en minutes. Ici, tu peux rester sans rien réussir. Le paysage continue de vivre.",after="Miette a déplacé son banc pour laisser une place à côté d'elle.",art="npc_miette")
    giver,side_title,side_intro,clue_title,clue,remember,side_reward=SIDEQUESTS[index]
    add("sidequest_start","npc",8,45,giver,text=side_intro,requires=1,grants=64,art="npc")
    add("sidequest_clue","sign",9,19,clue_title,text=clue,requires=64,grants=128,art="sign")
    add("sidequest_memory","shrine",39,55,"La mémoire en partage",after=remember,requires=192,grants=256,cost=0,art="shrine")
    add("sidequest_reward","chest",49,55,"La boîte des passeurs",after=side_reward,requires=256,cost=5,vehicle=6 if index==3 else 0,art="chest",secret=True)
    if index==3:
        add("bike_teacher","npc",49,52,"Basile et son vélo",text="Ada t'a confié son carnet ? Alors tu sais voyager avec une question. Prends mon vélo : chaque roue tournera aussi pour les histoires que tu rapporteras.",requires=256,vehicle=6,art="npc_companion")
    for n,(x,y) in enumerate([(18,30),(23,36),(12,26),(20,17),(34,17),(55,22),(61,28),(58,41),(46,49),(32,46),(21,49),(10,44)]):
        add(f"crystal_{n+1:02}","crystal",x,y,"Éclat de mémoire",art="crystal")
    for n,(x,y) in enumerate([(31,22),(52,33),(44,55),(58,12),(21,56)]):
        add(f"wanderer_{n+1}","enemy",x,y,"Ombre errante",requires=1,art="enemy")
    decorations=[]
    # Places are composed around the paths. Building feet occupy two tiles;
    # their roofs overhang freely and do not obstruct the whole painted sprite.
    for x,y,art,w,h,solid in [(11,33,'house',96,96,True),(22,34,'house',96,96,True),(11,43,'house',96,96,True),(22,44,'greenhouse',96,96,True),(16,40,'well',48,48,False),(13,36,'flower_pot',32,40,False),(19,35,'flower_pot',32,40,False),(15,10,'tree_pink',96,112,False),(18,11,'tree_pink',80,96,False),(60,19,'windmill',96,112,True),(67,48,'observatory',128,144,True),(34,11,'telescope',56,64,False),(26,51,'reeds',48,48,False),(32,52,'reeds',48,48,False),(39,31,'lantern',32,48,False),(17,34,'lantern',32,48,False),(63,52,'lantern',32,48,False),(67,52,'lantern',32,48,False)]:
        if solid:
            for xx in (x-1,x):rows[y][xx]='H'
        decorations.append(dict(art=art,x=x*TILE+16,y=(y+1)*TILE,w=w,h=h))
    for n in range(45):
        x=rng.randrange(2,W-2);y=rng.randrange(2,H-2)
        if rows[y][x] in ('.',',') and all(abs(x-e['x']/TILE)+abs(y-e['y']/TILE)>2 for e in entities):
            decorations.append(dict(art='flowers' if n%3 else 'flower_pot',x=x*TILE+16,y=y*TILE+28,w=32,h=32))
    if index==0:
        # Compose the actual 400x240-world-unit starting view, not just its map.
        # Replacing the old rectangular branch network is visual only: the
        # courtyard remains traversable and every entity is revalidated below.
        for yy in range(30,46):
            for xx in range(8,26):rows[yy][xx]='.'
        curves=[[(7,37),(9,37),(11,38),(14,38),(16,37)],[(15,29),(15,32),(14,34),(15,35),(16,37)],[(16,37),(17,38),(18,39),(20,39),(22,40),(25,42),(26,42)],[(26,37),(23,37),(22,38),(20,39)],[(16,46),(16,43),(17,41),(18,39)],[(12,38),(12,40)]]
        for curve in curves:
            for a,b in zip(curve,curve[1:]):path(a,b)
        decorations=[d for d in decorations if not (8*TILE<=d['x']<26*TILE and 30*TILE<=d['y']<46*TILE)]
        for art,x,y,w,h in [('house',400,1216,96,92),('greenhouse',656,1200,100,88),('tree',398,1324,116,130),('tree_pink',700,1294,92,110),('well',564,1260,44,50),('flower_pot',450,1210,30,36),('flower_pot',607,1198,30,36),('flower_pot',694,1204,30,36),('flowers',445,1250,46,34),('flowers',608,1276,40,30),('flowers',478,1136,32,28),('reeds',716,1178,32,44),('lantern',478,1200,26,42),('lantern',590,1168,26,42)]:
            decorations.append(dict(art=art,x=x,y=y,w=w,h=h))
        for x,y in [(11,37),(12,37),(19,37),(20,37),(12,41),(21,40),(17,39)]:rows[y][x]='H'
    regions=[]
    for n,(name,(x,y)) in enumerate(zip(ch['biomes'],hubs)):
        regions.append(dict(id=f"region_{n+1}",name=name,x=x*TILE,y=y*TILE,radius=260))
    quests=[dict(id="meeting",title="Une voix au bord du chemin",requires=0,complete_mask=1,objective=f"Rencontrer {ch['guide']}.")]
    for n,(name,_) in enumerate(ch['beacons']):
        quests.append(dict(id=f"beacon_{n+1}",title=name,requires=1,complete_mask=2<<n,objective=f"Trouver et réveiller « {name} » : deux éclats et les alentours apaisés."))
    quests.extend([dict(id="keeper",title=ch['keeper'],requires=14,complete_mask=16,objective="Apaiser le gardien, puis écouter le souvenir qu'il protégeait."),dict(id="crossing",title="Le passage retrouvé",requires=30,complete_mask=32,objective="Rejoindre l'arche de l'observatoire au sud-est.")])
    quests.append(dict(id='passing_on',title=side_title,requires=64,complete_mask=256,optional=True,objective="Retrouver la plaque au nord-ouest, puis la mémoire du jardin sud et sa boîte à l'est."))
    dungeon_manifest=ROOT/'dungeons/manifest.json'
    if index==0 and dungeon_manifest.exists() and json.loads(dungeon_manifest.read_text()).get('integrated'):
        add('sanctuary_entry','door',36,14,'Le Jardin sous les Racines',text="Sous l'observatoire des graines, les anciens jardiniers ont laissé des salles pour apprendre à leur succéder.",requires=14,art='portal',target_world=6)
    canopy_manifest=ROOT/'canopy_candidate/manifest.json'
    if index==1 and canopy_manifest.exists() and json.loads(canopy_manifest.read_text()).get('integrated'):
        add('herbarium_entry','door',39,14,"L'Herbier des Ombres",text="Silo a retrouvé le passage des plantes nocturnes. Le carnet sous l'écorce et la mémoire du jardin sud en expliquent l'accès. Dans ces serres, certaines lumières doivent rester éteintes.",requires=256,art='portal',target_world=16)
    reflections_manifest=ROOT/'reflections_candidate/manifest.json'
    if index==2 and reflections_manifest.exists() and json.loads(reflections_manifest.read_text()).get('integrated'):
        connection=json.loads((ROOT/'reflections_candidate/integration.json').read_text())['phase_one']
        # These sites already have verified pedestrian access. Do not clear land
        # or draw new paths over the established chapter-three terrain.
        entities.extend(connection['add_entities'])
    result=dict(schema=1,id=ch['id'],title="LUMA — Les Jardins du Souvenir",name=ch['name'],subtitle=ch['subtitle'],chapter=index+1,width=W,height=H,tile=TILE,spawn=dict(x=16*TILE+16,y=37*TILE+16),terrain=dict(rows=["".join(row) for row in rows],palette=ch['palette']),regions=regions,entities=entities,decorations=decorations,quests=quests,completion=dict(required_flags=63,final_chapter=index==5))
    if index==0:
        result['road_override_rect']=dict(x=8*TILE,y=30*TILE,w=18*TILE,h=16*TILE)
        result['road_paths']=[dict(width=22,points=[[x*TILE+16,y*TILE+16] for x,y in curve],interpolation='catmull_rom',caps='round') for curve in curves]
    return result


def main():
    worlds=[]
    for index,ch in enumerate(CHAPTERS):
        world=build(ch,index)
        filename="world.json" if not index else f"world_{index+1:02}.json"
        (ROOT/filename).write_text(json.dumps(world,ensure_ascii=False,indent=2)+"\n")
        worlds.append(dict(id=ch['id'],file=filename,name=ch['name'],chapter=index+1))
    campaign=dict(schema=1,title="LUMA — Les Jardins du Souvenir",initial_world=0,worlds=[w['file'] for w in worlds],world_metadata=worlds,vehicle_progression=[dict(chapter=i+1,vehicle=c['vehicle'],teacher=c['companion']) for i,c in enumerate(CHAPTERS)],runtime_contract=dict(max_entities_per_world=64,local_flags=True,persistent_world_state=True,shared_inventory=True,portal_target="target_world integer; -1 completes campaign; return_portal never completes a chapter"))
    for dungeon_manifest in (ROOT/'dungeons/manifest.json',ROOT/'canopy_candidate/manifest.json',ROOT/'reflections_candidate/manifest.json'):
      if dungeon_manifest.exists():
        manifest=json.loads(dungeon_manifest.read_text())
        if manifest.get('integrated'):
            assert len(campaign['worlds'])==manifest['base_index'],'Sanctuary world indices must remain stable'
            campaign['worlds'].extend(manifest['worlds'])
            for filename in manifest['worlds']:
                room=json.loads((ROOT/filename).read_text());campaign['world_metadata'].append(dict(id=room['id'],file=filename,name=room['name'],chapter=room['chapter'],indoors=True))
    (ROOT/'campaign.json').write_text(json.dumps(campaign,ensure_ascii=False,indent=2)+"\n")
    print(f"Wrote {len(worlds)} worlds: " + ", ".join(w['name'] for w in worlds))


if __name__ == '__main__':main()
