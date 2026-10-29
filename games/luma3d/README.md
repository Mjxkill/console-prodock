# LUMA 3D — Le Val des Courriers

Première vallée en véritable 3D pour le GPU G3D1 de la console. Cette tranche
remplace la direction visuelle du prototype en tuiles. Ce n'est pas encore
la campagne de plusieurs heures demandée : elle valide d'abord le paysage,
la caméra, le déplacement, l'animation et le rendu matériel sous Linux.
L'[état du contenu](CONTENT_STATUS.md) distingue les activités présentes,
les limites actuelles et les mécanismes encore nécessaires à cette campagne.

Après l’essai **GM1 du 27 octobre, la nouvelle boucle est visible sur Pro Dock** :
`/tmp/luma3d-gm1 --showcase`, PID **2925**, startticks **26240721**.
Elle intègre les glissements GPU des blocs/1024, Simon natif avec halos et
les mouvements/contacts de la maison présentés à l’arrivée visible, avec l’art R6.
Voir le [rapport GM1](tests/hardware/gpu_motion_20261027_gm1_result/README.md)
et l’[ancre courante](CURRENT_STATE.json).

Huit oracles matériels et dix fenêtres comparatives passent. Sur les fenêtres
initiales de 360 images : blocs 39,72 → 41,32 FPS, 1024 27,77 → 31,12,
Simon 16,01 → 29,22, maison 8,43 → 12,22 et shooter 43,95 → 49,96. Les p99 baissent,
mais ces fenêtres ne représentent pas tous les états ni une cadence constante.
L’entrée dans les nouveaux modes est plus lente (jusqu’à 1,25 s dans ces fixtures).

Le **vrai tour** termine 17 étapes et gagne huit activités par leurs commandes
normales : **783,232 s murales**, 772,622 s simulées, 1079 commandes. Avec entrées
et transitions incluses, la fusion1024 complète mesure 21,61 FPS, la maison 11,83,
l’exploration 10,65, les blocs 38,37, Simon 25,70 et le shooter 43,40. Circuit et
formes restent proches de 20 FPS, avec des pics importants. **Tous les modes ne
sont donc pas encore fluides.** Les coûts détaillés figurent dans
[showcase_costs.json](tests/hardware/gpu_motion_20261027_gm1_result/showcase_costs.json).

La boucle autonome tourne en arrière-plan, stdin `/dev/null` ; les touches
du shell ne commandent pas cette instance. Aucune sauvegarde n’est ouverte.
`/tmp/op2-live.save` V4 est inchangé. CDC/verrou sont libérés ; FPGA G22r0 et
noyau G3D1 restent inchangés, sans écriture SD/flash ni erreur GPU/underflow.
R6 est conservée comme repli exact. Aucune qualification Neo n’est déduite.

Les preuves historiques restent intactes : [MO1 conserve son FAIL de diagnostic](tests/hardware/motion_20261027_mo1_result/README.md),
[PP2 qualifie R6](tests/hardware/polish_20261027_pp2_result/README.md) et
[SC1 conserve son premier tour complet](tests/hardware/showcase_20261026_sc1_result/README.md).

Le [lot arcade](candidates/adventure_arcade_world_r1/README.md) a fourni les
huit activités, leur sauvegarde V5 et le retour exact. Le
[candidat showcase](candidates/adventure_showcase_r1/README.md) ajoute la visite
complète, figée dans `build/showcase_20261026_r3/`. L’ancien essai OP2 conserve
ses propres mesures et limites dans son
[rapport historique](tests/hardware/paths_20261026_op2_prepared_r1/trial/REPORT.txt).

## Répartition CPU / FPGA

Le CPU calcule la simulation, les collisions, la caméra et les matrices des
objets. Les modèles sont stockés une fois dans la DDR réservée au GPU. Les
commandes G3D1 du FPGA transforment leurs sommets, découpent les triangles
contre les six plans de vue, calculent la perspective et l'éclairage plat,
puis alimentent le rasteriseur texturé avec Z-buffer et brouillard.

Les coordonnées de la caméra et des personnages ne sont pas précalculées.
L'autopilote utilise les mêmes déplacements, pentes et collisions que les
commandes manuelles. La démo SC1 visite les lieux et résout les activités par
leurs entrées réelles, avec des pauses de lecture et une présentation entre
les commandes. Les bras, jambes, cape, lettres et pales
du moulin sont animés par des matrices calculées pendant l'exécution.

Les huit textures peintes proviennent de ComfyUI sur `gx10-2` : Flux2 Klein
et Qwen, workflows, images originales, seeds et conversions RGB565 conservés
sous `art/comfy/`. Les concepts de personnage ne sont pas des modèles 3D
déjà intégrés. Aucune vidéo ou image de paysage complète ne remplace le relief.

## Construction et utilisation

Le paquet actuellement affiché est le candidat isolé
`build/maze_events_20261027_r4/`, avec ses sources et son manifeste. Les commandes
`make` ci-dessous concernent le socle de développement ; elles ne reconstruisent
pas automatiquement ce candidat figé. Sa recette est dans
`candidates/maze_events_r1/build.py`.

```sh
make -C games/luma3d all riscv
make -C games/luma3d test
python3 games/luma3d/tests/test_render_contract.py \
  --out games/luma3d/build/render_contract_<nouveau-nom>
```

Le binaire natif exige le noyau candidat donnant accès aux commandes G3D1
31–34 et à `PRODOCK_GEOMETRY_INFO`. Le noyau R17 historique ne possède pas
cette extension : le programme la vérifie avant toute soumission.

```sh
# Commande de la boucle GM1 actuellement affichée, lancée en arrière-plan.
/tmp/luma3d-gm1 --showcase

# Pour un lancement interactif ultérieur, après arrêt de l’instance courante.
/tmp/luma3d-gm1 --manual
```

Touches : WASD pour marcher, majuscules pour courir, I/U/K/L pour regarder,
espace pour sauter, E pour interagir, J pour le carnet, T pour basculer l'autopilote, Q pour
quitter. Ce premier frontal utilise le terminal ; l'intégration des manettes
au jeu reste à faire.

Le rendu Pro Dock est en 400×240 RGB565 agrandi matériellement vers 800×480.
Le chemin Neo utilise 640×360 vers 1280×720, testé localement seulement.
La surface réserve le pitch natif nécessaire au gestionnaire Linux et au
changement entre affichage partagé et plein écran. Deux pages couleur, une
page profondeur, les modèles et les textures occupent des régions distinctes.

## Preuves et limites

Le candidat initial est figé dans `build/frozen_20261024_r1/manifest.json` :
ELF dépouillé SHA-256
`216623767b298d0c13e3b35bfccdc088ca042c97d1ebc33beece415cea525951`.
Les images de référence sont obtenues à partir des commandes du véritable
renderer C, rejouées par un modèle entier indépendant du GPU. Ce modèle
est un outil de validation hors carte ; ses temps ne sont pas des FPS FPGA.

`build/render_contract_20261024_r3/result.json` couvre 600 états Pro Dock et
400 états Neo avec ASan/UBSan, le même flux capturé et soumis au périphérique
simulé, les tailles/pitches, les adresses et l'interdiction de présenter après
une erreur. Le parcours de production passe 3 787 pas fixes aller-retour,
sans injection d'état. Vingt mille requêtes de collision sont comparées aux
JSON et 14 624 triangles du relief détaillé à la surface physique.

Le noyau isolé `build-kernel/prodock_g3d1_20261024_r1/` conserve l'initramfs,
le DTB et OpenSBI R17, et ajoute seulement l'interface G3D1. Son démarrage et
le test matériel élémentaire sont consignés dans `tests/hardware/` : raster
384 000 pixels, puis géométrie 294 pixels, profondeur et culling. Ces tests
ne qualifient pas à eux seuls le paysage complet ou ses performances.

Le premier cadrage soumet environ 6 700 faces et 250 groupes ; la cible
artistique initiale de 2 500 faces / 90 appels n'est pas encore atteinte.
L'essai matériel R1 a depuis vérifié les 96 000 pixels du cadrage initial
contre le modèle, puis 672 images sur 147,414 s (échauffement et contrôles
compris), soit 4,56 FPS moyens. Tous les compteurs d'erreurs GPU/G3D et les
underflows restent nuls. La qualité des pixels passe, mais cette fluidité
est insuffisante. Le jeu est laissé visible après l'essai. Rapport :
`tests/hardware/valley_20261024_r1/REPORT.txt` et `performance.json`.

R2, `build/frozen_20261024_r2/`, exploite la voie opaque sans brouillard
pour les objets entièrement proches, et génère le ciel au GPU une seule fois
avant de le recopier avec COPY565. Ses quatre vues sont identiques à R1,
y compris après réutilisation du ciel sur la deuxième page. Il ajoute les
mesures de cycles G3D par fenêtres de cinq secondes (compteur modulo 2³²).
Les cycles G3D incluent l'attente du raster dans DRAW, mais pas les commandes
V1 directes comme COPY : ce n'est pas un compteur d'occupation de tout le GPU.
L'essai R2 a vérifié les 96 000 pixels du premier cadrage, puis une fenêtre
de 30 secondes sans commandes UART, sans erreur GPU/G3D ni underflow. Le
rapport est dans `tests/hardware/valley_20261024_r2/REPORT.txt`. Comparer
ses moyennes à celles de R1, sur des parcours de durées différentes, ne
constitue pas un A/B à charge identique.

La comparaison R2/R3 utilise `--benchmark --frames 30 --warmup 3 --advance N` :
caméra, personnage et animations figés à la même pose, trois présentations
de chauffe exclues, puis trente images mesurées. Le journal identifie les
temps SUBMIT/PRESENT et les deltas de compteurs, y compris la dernière
fenêtre partielle. Le mode PC reste explicitement `hardware=0`.

Les deux paquets sont isolés dans `build/benchmark_r2_20261024_v2/` et
`build/frozen_20261024_r3_v2/`. Le premier reprend exactement le renderer
R2 ; le second déduplique les commandes d'état identiques et utilise le
décor compact `art/candidates_r4/budget_r10/`, sans son option OBB. Au
départ : 2 086 faces, 81 draws et 368 commandes, contre 6 687, 252 et
1 171. Les huit vues
R3 sont identiques à celles du candidat artistique sans OBB.

L'essai Pro Dock est terminé : les quatre poses donnent respectivement
3,92 / 4,70 / 6,60 / 4,80 FPS pour R2, et 9,03 / 10,26 / 13,11 / 11,23 FPS
pour R3. Les huit images correspondent exactement à leur référence propre,
sans erreur GPU/G3D ni underflow. La cible de 30 FPS n'est pas atteinte.
Le parcours automatique suivant récupère les quatre lettres ; ses compteurs
signalent un sliver, sans erreur GPU. La fenêtre silencieuse de 75 secondes
est distincte de la durée totale du processus et des mesures à pose fixe.
Rapport et données : `tests/hardware/benchmark_20261024_r3_resume/REPORT.txt`
et `performance.json`. Le banc local C/CLI du snapshot R3 est dans
`build/render_contract_20261024_r8_r3_frozen/result.json` ; son périmètre
n'inclut pas l'oracle indépendant d'accord terrain/collision du candidat.

État matériel laissé à l'utilisateur : R3 v2 en visite automatique,
`/tmp/luma3d-b3v2`, PID 424, journal `/tmp/l3r4_live.log`, après l'essai R4
décrit ci-dessous. L'ancre publiée est `/tmp/luma3d-live.pid`. Le CDC et le verrou
diagnostic sont libérés. Conformément à sa demande, le jeu reste visible
après succès, sans retour automatique à NEBULA. Le R2 exact est conservé
sous `/tmp/luma3d-r2` comme repli. Ces fichiers RAM disparaissent au redémarrage.

R4, qui remplace les arbres éloignés par des billboards, a été testée sur
les mêmes quatre poses, trente images après trois images de chauffe.
R3 donne 8,97 / 10,20 / 13,12 / 10,87 FPS et R4 8,68 / 10,07 / 13,32 /
10,58 FPS. R4 n'est pas retenue : son débit moyen géométrique recule de
1,42 %, malgré moins de triangles. Les huit comparaisons de 96 000 pixels
passent contre les références propres à chaque version ; aucun défaut
GPU/G3D ni underflow. Le parcours automatique R4 récupère les quatre lettres
avec un sliver signalé. Le critère de gain n'a pas été assoupli et aucun
essai supplémentaire n'a été lancé pour chercher un meilleur résultat.
Le rapport, les compteurs par image et les journaux sont conservés dans
`tests/hardware/benchmark_20261024_r4_prepared/REPORT.txt`. Le contrôleur figé
exige l'ancien PID 302 : il ne doit pas être relancé avec l'état actuel.

**Limite de ce décor expérimental :** le sol est exact sous le parcours
automatique contrôlé, mais approximatif hors chemin, jusqu'à 2,08 m de
décalage avec la collision. Il ne qualifie donc pas l'exploration libre.
Une autre triangulation bornée et une révision des billboards sont étudiées
séparément ; elles ne sont pas incluses dans le binaire R3 mesuré.

L'[audit des fonctions du FPGA réellement chargé](tests/G22R0_FEATURE_AUDIT.md)
répertorie les accélérations utilisées, disponibles, non exposées et absentes.
Les mesures matérielles de la vallée sont distinctes des rendus de référence.
La durée de la visite automatique ne mesure pas la durée d'un futur jeu.

Les références Pro Dock G22r0 / NEBULA R17 restent protégées. Aucun nouveau
bitstream Pro Dock n'est nécessaire pour cette extension Linux. La Neo
reste un chantier matériel distinct ; aucun résultat Pro Dock ne qualifie
son framebuffer ou son timing.

## État visible du 25 octobre : surface et sauvegarde

Le lot `terrain_surface_20261025_r2` est maintenant testé sur Pro Dock et laissé
visible sous `/tmp/luma3d-sf2` (PID 1193, startticks 7812193). Il garde les contenus
et textures d’art3, corrige le sol physique et ajoute la sauvegarde explicite.
Les cinq scènes, la mission et la reprise de sauvegarde RAM passent ; le parcours
reste autour de 7,8 FPS, sans qualification de fluidité à 30 FPS. Rapport exact :
`tests/hardware/surface_save_20261025_sf2/trial/REPORT.txt`.

Conformément à la préférence utilisateur, LUMA reste animé après succès, sans
retour à NEBULA. Art3 demeure disponible comme repli. La sauvegarde de la visite
est `/tmp/sf2-live.save`, volatile ; aucun stockage SD n’a été changé. Les anciens
rapports d’art3 et de ses restaurations décrivent leurs états historiques.


## État visible suivant : atelier ws1

Le lot `adventure_workshop_20261025_r8` a passé l’essai Pro Dock ws1 et remplace
sf2 à l’écran : `/tmp/luma3d-ws1`, PID 1331, startticks 8373701. La visite
automatique commence près de l’atelier grâce à 6 280 vrais pas de simulation
préalables. Elle reste en marche après succès, conformément au choix utilisateur.
Le courrier puis le trajet au-delà du pont, les ailettes, la réserve et le retour
avec la cloche ont été accomplis depuis une nouvelle partie lors de l’essai.

Cinq scènes exactes, sauvegarde V2 et reprise PASS, aucune erreur GPU. Le parcours
mesure 8,26 FPS sur 285,847 s de processus (contrôles compris) ; ce n’est ni un
objectif 30 FPS atteint ni une campagne de plusieurs heures. Rapport :
`tests/hardware/workshop_20261025_ws1/trial/REPORT.txt`.
Sf2 et sa sauvegarde V1 `/tmp/sf2-live.save` sont conservés sans modification ;
la nouvelle visite utilise `/tmp/ws1-live.save`, volatile. Ne pas fournir une V2
à sf2. FPGA, noyau, SD et flash inchangés ; aucun NEBULA relancé.
