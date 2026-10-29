# État réel du jeu 3D — 27 octobre 2026

La version visible est **GM1**, `/tmp/luma3d-gm1 --showcase`, PID 2925,
startticks 26240721. Identité et progression vérifiées après lecture finale de
la sauvegarde ; boucle autonome avec stdin `/dev/null`, CDC/verrou libérés.

GM1 passe huit oracles, dix fenêtres A/B et le vrai tour : 17 étapes, huit
activités gagnées, 1079 commandes légales, 772,622 s simulées et 783,232 s murales.
Les glissements blocs/1024, halos Simon et contacts différés visuellement de
la maison sont maintenant sur carte. Art R6 et règles/sauvegardes conservés.

La fluidité reste incomplète. Sur le **tour réel entier**, entrées/transitions
incluses : exploration 10,65 FPS, circuit 19,95, blocs 38,37, formes 20,65,
1024 21,61, maison 11,83, Simon 25,70, shooter 43,40, tour 19,72. Les p99 du circuit
et des formes atteignent 420 ms ; la maison 384 ms. Les fenêtres A/B initiales,
plus courtes, montrent un gain mais ne doivent pas remplacer ces résultats.
Voir le [rapport GM1](tests/hardware/gpu_motion_20261027_gm1_result/README.md).

Le contenu reste deux régions et huit activités courtes ; aucune heure de
campagne supplémentaire n’est revendiquée. Jeux de cartes (défausse type UNO,
poker, tarot), véhicules 3D et audio restent non intégrés. Aucune nouvelle
fonctionnalité FPGA n’est ajoutée. Les essais Neo restent distincts.

La démo n’ouvre aucune sauvegarde. R6 et OP2 restent disponibles, la sauvegarde
V4 `/tmp/op2-live.save` est intacte ; ce stockage demeure volatil. Les preuves
[MO1 FAIL](tests/hardware/motion_20261027_mo1_result/README.md) et
[PP2 R6](tests/hardware/polish_20261027_pp2_result/README.md) sont conservées.

| Domaine | Contenu présent dans GM1 (base SC1/R6) | Limite actuelle |
|---|---|---|
| Paysage | Vallée 160 × 160 m et Terrasses 80 × 80 m, avec bassin et observatoire ; relief cohérent et textures issues de ComfyUI | Deux petites régions ; composition encore simple et surfaces sableuses dominantes dans la nouvelle |
| Personnage | Marche, course, saut, inertie, collisions et caméra arrière | Pas de nage, escalade, monture ou véhicule 3D |
| Habitants | Maëlle, Silo, Iria, Nora et Nils ; dialogues français | Deux nouveaux costumes dérivés de modèles existants ; trois missions courtes |
| Mission | Courrier/relais, ailettes/cloche, puis vannes/bassin/passerelle/Nils et retour | Boucles courtes ; pas une campagne de plusieurs heures |
| Monde animé | Eau par UV, arbres proches, moulin, oiseaux et héros articulé en temps réel | Eau opaque ; pas de simulation de météo ou d’écosystème |
| Interface | Dialogue et carnet via une ou deux couches indexées, cache par page | Aucun inventaire développé ni choix narratif durable |
| Contrôle | WASD, I/U/K/L, espace, E, J et T par terminal ; même physique en automatique | Pas de manette intégrée ; le processus de démonstration tourne avec entrée fermée |
| Progression | Collectes, missions, raccourcis et récompenses uniques ; sauvegarde V5 en manuel et migrations testées localement ; démo sans sauvegarde | Stockage /tmp volatil ; persistance après redémarrage non intégrée |
| Défis | Circuit, blocs, formes, fusion 1024, maison-labyrinthe 3D avec poursuivants, Simon, shooter 2D avec boss, tour 3D avec obstacles | Activités courtes ; pas de combat libre dans la campagne ni de grand donjon |
| Son | Ressources YuE2 expérimentales conservées du chantier précédent | Aucun backend audio intégré au jeu 3D |

La mission est réellement accomplie sur Pro Dock dans l’essai art3 :
`tests/hardware/living_20261024_vl2/REPORT.txt`. Le parcours automatique local
termine la mission en 61,87 secondes simulées, dont 30 secondes de dialogue ;
aller et retour en 93,35 secondes. Ce sont des mesures d’automate, pas une
durée humaine de découverte. Le prototype 2D archivé avait davantage de
contenu ; il n’est pas exécuté par le moteur 3D et sa durée ne s’y ajoute pas.

L’objectif de plusieurs heures, avec une cible de conception de 6 à 10 heures,
n’est pas construit ni mesuré. Il manque notamment des lieux distincts,
énigmes à plusieurs états, rencontres, capacités qui ouvrent de vrais trajets,
conséquences persistantes et stockage durable après redémarrage. Des titres de missions,
des temps d’attente ou des distances artificielles ne constituent pas du contenu.

## Fluidité et qualification

Art3 donne environ 7 à 13 FPS selon les vues fixes ; la cible de 30 FPS n’est
pas atteinte. Le rendu emploie G3D1, Z16, perspective, cache texture, voie opaque
proche, ciel réutilisé par COPY, CLEAR Z, LOD de maillages et couches HUD.
Audit sourcé : `tests/G22R0_FEATURE_AUDIT_ART3.md`.

Le tri terrain seul a été testé sur les six mêmes vues, 30 images après 3 de
chauffe, avec retour témoin final. Toutes les images et banques HUD passent,
mais le candidat n’a pas été conservé : médiane +3,07 %, inférieure au seuil
préfixé de 5 %, et dérive témoin +3,22 %, au-delà de 3 %.
Résultat : `tests/hardware/terrain_order_20261025_to2/trial/AB_REPORT.txt`.
Art3 a été rétabli, sans NEBULA.

Le candidat suivant ajoute un cache CPU statique. Les commandes GPU restent
exactement celles du tri seul sur 1 980 caméras/LOD et 52 positions du parcours.
Les images échantillonnées sont identiques à art3. Son essai to3 a été interrompu
à la demande de l’utilisateur avant toute scène et sans arrêter art3.
La reprise autorisée to4 est terminée : 13 scènes exactes, mais gain médian
de 1,15 %, inférieur au seuil de 5 %. Le candidat n’a pas été retenu ; art3
a été rétabli à la fin de cet essai. Rapport : `tests/hardware/terrain_cpu_20261025_to4/trial/AB_REPORT.txt`.

L’écart entre collision et terrain compact hors chemin est corrigé dans
`build/terrain_surface_20261025_r2` : collision issue des triangles réellement
dessinés, tablier cohérent, 1 960 reprises de positions et parcours complet PASS
localement. Les LOD éloignés restent des approximations visuelles. Le pont n’a
pas encore été traversé manuellement sur carte lors de cet essai.

Ce paquet a passé l’essai Pro Dock sf2, puis a été conservé pour retour : cinq scènes exactes,
mission terminée, sauvegarde puis reprise /tmp identiques. Les vues nouvelles
mesurent 7,75 FPS à l’arrivée, 11,48 chez Silo et 7,61 à la fin. La visite complète
mesure 7,83 FPS sur 165,65 s de processus ; ce total inclut les contrôles autour
des 120 s silencieuses. Aucune amélioration significative de débit n’est revendiquée.
La sauvegarde explicite `--save chemin` contrôle les domaines numériques et
remplace le fichier atomiquement. Le stockage visible demeure volatil dans /tmp,
sans écriture SD ni promesse de reprise après redémarrage.

L’atelier au-delà du pont est maintenant implémenté dans le candidat local
`build/adventure_workshop_20261025_r8` : indication d’Iria, chemin aller-retour,
ailettes couplées, porte, réserve et cloche ramenée à Maëlle. La visite complète
depuis la nouvelle partie passe en 165,97 secondes simulées, dont 50 de dialogue ;
ce n’est pas une durée humaine ni une campagne longue. Les raccords piétons
utilisent 16 triangles rendus et interrogés pour la collision. Sauvegarde V2,
migration du vrai fichier sf2, reprises prolongées, deux profils et seize oracles
passent localement. L’essai Pro Dock ws1 est maintenant terminé : cinq vues exactes, parcours
complet et reprise V2 PASS. La visite avait été laissée visible, commencée près de l’atelier
par 6 280 vrais pas préalables. Le total mesuré est 8,26 FPS sur 285,847 s de
processus, contrôles compris, avec une fenêtre silencieuse de 240 s. L’arrivée
mesure 6,97 FPS contre 7,61 puis 7,37 pour les témoins sf2 : la garde de régression
passe, aucun gain n’est annoncé. Mécanismes 13,81 FPS, réserve 15,02 FPS.
Aucune erreur ; un sliver écarté. La sauvegarde V1 de sf2 reste inchangée.
Rapports : `candidates/adventure_workshop_r1/README.md` (lot local figé) et
`tests/hardware/workshop_20261025_ws1/trial/REPORT.txt` (carte).

Les preuves locales des deux profils, les pixels sur Pro Dock, les débits et
les éventuels essais Neo sont des résultats distincts. Les anciens états et
leurs limites restent conservés dans les rapports historiques ; le précédent
texte de cet état est archivé dans `tests/content_status_20261025_pre_resume.md`.

## Deuxième région — gel local puis essai am1

`build/adventure_amber_20261025_r9` a d’abord été figé et revu localement, avec
ws1 laissé intact. Les manifestes de ce gel gardent cet état historique. Le
passage bleu, ouvert après l’atelier, conduit à une petite région minérale de
80 × 80 m. Nora, une prise d’eau et une vanne commandent le remplissage d’un
bassin et la levée d’une passerelle ; Nils attend dans l’observatoire. Le joueur
peut lui parler, revenir donner ses nouvelles et regagner la vallée. La tour,
le pavillon, les arbres groupés et le chemin distinguent ce lieu de la vallée.
Les modèles et la composition restent simples ; les deux nouveaux costumes
réemploient des formes existantes avec une autre palette.

Les trois missions et le retour passent en 244,97 secondes simulées, sans
prétendre mesurer une durée humaine. Les sauvegardes V3 reprennent dans la bonne
région et migrent les vrais fichiers V1/V2 conservés. Parcours, commandes E,
géométrie/collision, 208 checkpoints et 9 reprises complètes passent localement.
Le contrat GPU vérifie 1 580 états sur les deux profils ; 16 scènes produisent
2 611 200 pixels dans l’oracle indépendant et composent les banques HUD.

Les ressources des deux régions restent en mémoire, avec 4 878 240 octets
effectivement chargés. La région inactive ne soumet aucun objet et ses faces
d’eau ne sont pas réécrites ; ce n’est pas encore un système de streaming pour
une grande campagne. Le terrain ajouté utilise 800 triangles identiques pour
le dessin et la collision. Au gel local, aucun FPS matériel n’était connu.
Les fichiers V3 restent distincts de la sauvegarde V2 de ws1, dans `/tmp`
seulement. Le lot et ses limites sont décrits dans
`candidates/adventure_amber_r1/README.md`, les vues dans
`build/adventure_amber_20261025_r9/captures_final/`, les identités et preuves dans
`local_validation.json`, `review_manifest.json` et `handoff.json` du même build.
L’essai Pro Dock am1 est maintenant terminé : les sept poses passent les pixels
et banques HUD. L’arrivée vallée R9 mesure 7,03 FPS contre 7,18 pour ws1 avant
et après ; les vues des Terrasses mesurent 10,72, 13,43 et 15,73 FPS. Le parcours
complet mesure 9,25 FPS sur 345,261 s de processus, contrôles compris, avec
300 s sans écriture UART. Aucun gain ni percentile stable n’est revendiqué.
Mission complète et retour, sauvegarde V3/reprise identiques et V2 ws1 intacte
sont vérifiés. Aucune erreur GPU/underflow ; six slivers écartés. Le nouveau jeu
reste animé. Qualification séparée : `candidates/adventure_amber_r1/hardware_am1.json`.
Les états précédents de ce document sont conservés dans
`tests/content_status_20261025_pre_amber_r9.md` et `tests/content_status_20261025_pre_am1.md`.


## Historique du 26 octobre — Terrasses ouvertes, OP1 puis OP2

Le candidat `candidates/adventure_amber_paths_r1` est figé dans
`build/amber_paths_20261026_r4`, ELF RV32
`0daa38a57d1dfc149222e35887437bb8c1f5d768cd3ecafdafa526d628a7c0b4`.
Au gel initial, am1 restait la dernière version qualifiée et affichée sur Pro Dock. La préparation
locale n’a pas touché la carte ; l’essai op1 suivant est décrit ci-dessous.

Deux routes relient Nora et Nils, dont un sentier ouest praticable avec le
pont fermé. Cinq activités facultatives sont intégrées dans cette même région :
circuit, blocs, formes, fusion 1024 et maison-labyrinthe en vraie 3D. Le jardin
et la maison donnent chacun un passage permanent ; les autres récompenses
restent des indices/souvenirs. Aucun ensemble de victoires n’est requis pour
traverser la région. La maison possède trois pièces accessibles à pied.

Validation locale PASS : les trajets et cinq victoires par commandes légales,
retour exact à l’exploration, récompenses uniques, reprise V4 depuis les vraies
sauvegardes ws1 V2 et am1 V3, cinq reprises en activité (dont une en l’air),
5 292 corruptions et 5 292 troncatures rejetées. Contrat renderer/CLI et erreurs
sur 800×480 et 1280×720 ; 14 captures du même flux G3D1 et des banques indexées,
2 284 800 pixels natifs modélisés. Les bancs d’ioctl utilisent des périphériques
simulés : leurs compteurs zéro ne sont pas des mesures de la carte.

Les quatre plateaux 2D n’émettent pas de DRAW 3D. Le labyrinthe initial emploie
24 commandes, 13 DRAW et 1 542 triangles soumis. Ces comptes ne promettent pas
un débit matériel. Les textures restent à 4 MiB ; quatre instances régionales
sont ajoutées, et les 25 patches physiques d’ambre gardent leurs triangles R9.

Les huit familles demandées sont consignées dans DESIGN.md. Simon, shooter
vertical et tour de plateformes 3D ont désormais des moteurs séparés testés
sous `minigames/`, mais leurs lieux/rendus/persistance ne sont PAS intégrés à
ce binaire. Les cinq premiers défis sont courts ; aucune campagne de plusieurs
heures n’est annoncée. Voir handoff.json, README.md et HARDWARE_PLAN.txt dans
le candidat pour les preuves et limites du gel initial.

L’essai op1 a validé l’arrivée (96 000 pixels et deux banques HUD exacts) :
am1 7,08 FPS, candidat 7,08 FPS, témoin am1 final 7,00 FPS sur 30 images après
trois images de chauffe. La fixture suivante, le jardin, a échoué sur 28 pixels,
avec les comptes de commandes exacts et zéro erreur GPU/underflow. Le parcours
des activités et les reprises matérielles suivantes n’ont donc pas été exécutés.
Am1 a été restauré et sa progression vérifiée ; CDC et verrou sont libres.
Voir `tests/hardware/paths_20261026_op1_prepared_r4/trial/REPORT.txt`.

La cause est reproduite localement : une remise en place immédiate de caméra
conservait un arrondi dépendant de son initialisation (vallée ou Amber).
Le lot `build/amber_paths_20261026_r5` corrige cette affectation. Les 100 contextes
de reprise, les neuf captures natives RV32 sous QEMU, les suites locales des deux
profils et les 11 groupes globaux passent. Les 14 vues de parcours restent exactes
par rapport à r4. Aucun seuil pixel n’a été assoupli.

L’essai OP2 suivant passe sur Pro Dock : les sept fixtures donnent des pixels
3D et banques indexées exacts, puis le parcours par commandes normales termine
les cinq défis, les deux itinéraires et la sortie secrète. Il utilise 16 544 pas
d’entrée et 426 images échantillonnées, avec cinq reprises à l’entrée des défis.
Une reprise de défi actif passe aussi dans le véritable ELF utilisateur.
Ce replay accéléré de 62,81 s n’est pas une durée humaine ; ses 426 images ne
sont pas comparées une par une. Deux approximations de gradients sont comptées
(`slivers`), sans erreur GPU ni underflow. Les trois fenêtres de pose fixe donnent
7,12 / 6,71 / 6,91 FPS (am1 / r5 / am1), dans les gardes prédéfinies, sans gain
de débit annoncé. La nouvelle visite avait été laissée visible, avec am1 disponible
pour retour. Aucune modification FPGA, noyau, SD ou flash.


## Lot arcade local avant SC1 — huit activités

`build/arcade_world_20261026_r2` intègre les cristaux de mémoire, le vaisseau
2D et la tour de plateformes 3D aux cinq lieux existants. Les huit activités
restent facultatives et accessibles dans la même région ; la tour ouvre un
nouveau portillon. Le terrain et les anciennes surfaces/collisions n'ont pas
changé. V5 migre V2/V3/V4, conserve chaque défi et sa récompense et restaure
exactement la pose d'un défi actif. Les nouvelles ressources natives utilisent
une plage dédiée pour éviter de réécrire une source encore à l'écran.

PC/RV32, intégration physique, codec et contrat GPU/CLI deux profils passent.
Les vues sont produites par le véritable renderer ; seize captures du binaire
RV32 sous QEMU concordent exactement avec commandes, mémoire et descriptions
PC. Ces résultats locaux ne qualifiaient ni la Pro Dock ni la Neo. Aucun FPS
matériel n’était connu à ce gel ; aucun accès carte n’a été effectué pendant
cette préparation. Le lot a ensuite servi de base à SC1, testé ci-dessous.

Les trois défis supplémentaires restent courts : le conseiller de la tour
termine en 9,783 s simulées, celui du vaisseau en 11,916 s et Simon en 35,4 s.
Ce ne sont pas des durées humaines. Deux récompenses sont des balises/repères ;
la troisième ouvre un vrai raccourci. Le visuel des mini-jeux est encore simple,
le shooter n'a pas encore d'explosion dédiée et aucun son n'est intégré. Le
jeu de plusieurs heures demeure à construire. État, aperçus et plan d'essai :
`candidates/adventure_arcade_world_r1/README.md` et `PLAN_MATERIEL.txt`.

## SC1 — visite complète validée et laissée en boucle

Le paquet `build/showcase_20261026_r3` utilise les moteurs réels et leurs
commandes légales, avec dt positif et attente de présentation. Les quatre
puzzles sur grille gardent chaque commande au moins 400 ms ; les victoires
restent visibles quatre secondes. Aucun état de victoire n’est injecté.
Les sauvegardes utilisateur ne sont ni ouvertes ni modifiées. La visite est
bornée et annulable en mode interactif ; le mode manuel conserve les activités
facultatives et le retour exact dans l’exploration.

Le parcours local passe cinq cadences, deux boucles successives et un rythme
irrégulier avec une pause de 20 s. Les deux profils, 34 captures et 13 contrôles
RV32 sont liés au même ELF. Les 654 entrées des 11 groupes communs étaient
inchangées : leur résultat PASS a été conservé, sans nouvelle exécution.

L’essai matériel SC1 a ensuite terminé un tour complet : 17 étapes, masques
visités/gagnés `ff`, 1 079 commandes de conseillers, boss, checkpoint de tour,
cristaux, trajets physiques et retour en vallée. La durée réelle de 13 min 55 s
inclut des pauses de lisibilité : elle mesure une visite guidée, pas une
campagne de plusieurs heures. Les graphismes des activités restent simples,
particulièrement le shooter ; véhicules 3D et audio matériel restent absents.
Le journal reste accessible en manuel, sans ouverture automatique pendant la
démo. Détails et journaux :
[rapport SC1](tests/hardware/showcase_20261026_sc1_result/README.md).
