# Moteur de jeu commun Pro Dock / Neo — état du 27 octobre 2026

Le développement vise un **moteur de jeu commun aux deux cartes**. LUMA est
son premier jeu et sa vitrine : exploration, personnages, activités et visite
automatique exercent les mêmes règles et le même producteur de commandes.
Ce document décrit les composants réellement présents et leurs couplages.
Il ne crée ni une nouvelle bibliothèque moteur ni une nouvelle qualification
matérielle. Les séparations proposées ci-dessous restent à réaliser.

La règle de propriété reste celle de [COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md)
et de [ownership.json](../tang/boards/ownership.json) : les sources communes
restent uniques, les profils et substitutions de carte sont explicites.
Le nom `prodock-*` d'une interface Linux ne signifie pas « Pro Dock seulement ».
Les copies de sources dans les builds servent à reproduire une expérience ;
elles ne constituent pas deux moteurs de production indépendants.

## Références examinées et état de qualification

L'inventaire se fonde sur le
[snapshot GM1](../games/luma3d/build/maze_events_20261027_r4/source/games/luma3d/)
effectivement testé sur Pro Dock. Dans les tableaux suivants, `src/`, `include/`,
`world/` et `minigames/` désignent les fichiers de ce snapshot, sauf indication
contraire. Le répertoire de développement `games/luma3d/` et les candidats
isolés ne doivent pas être confondus avec le binaire affiché.

| Élément | Identité ou portée |
|---|---|
| GM1, manifeste de sources | `49621170372f7c0ed2d4a6f83552247e6620cebc693442c21acb3020617820ee` |
| GM1, ELF du jeu | `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b` |
| Dernière ancre Pro Dock connue | `/tmp/luma3d-gm1 --showcase`, PID 3158, startticks 27508908, après le retour vérifié de MC1 ; boucle autonome avec stdin `/dev/null` |
| FPGA / Linux Pro Dock | G22r0 conservé ; noyau candidat `6.12.112-prodock-luma3d-g3d1-r1`, distinct de la référence Linux NEBULA R17 |
| MC1 | Essai logiciel terminé sur Pro Dock : fonctionnel PASS, performance refusée ; GM1 restauré, candidat non promu |
| Neo | Profil 1280×720 testé localement ; moteur/jeu GM1 et MC1 **non validés sur le matériel Neo** |

Le [rapport GM1](../games/luma3d/tests/hardware/gpu_motion_20261027_gm1_result/README.md)
conserve le tour réel, les compteurs, les oracles et leurs limites. Il ne prouve
pas 30 ou 60 FPS dans tous les modes : les débits du tour incluent notamment
11,83 FPS dans la maison, 21,61 dans la fusion 1024 et 43,40 dans le shooter.
Les entrées, les images lentes et les percentiles doivent être examinés
séparément. Un succès de parcours ne constitue pas une qualification de fluidité.

## Chaîne de fonctionnement actuelle

```text
Entrées du terminal / contrôleur de visite
                 ↓ L3Input
Simulation du monde ou moteur d'activité → état sauvegardable
                 ↓ vues + traces d'événements après les pas réels
Présentation : interpolation, files de mouvement, lumière et HUD
                 ↓
Rendu 3D G3D1 / quads V1 / couches et sprites
                 ↓ commandes + ressources + scène
Linux : validation ABI, SUBMIT synchrone, PRESENT
                 ↓
GPU et sortie propres au profil matériel
```

La simulation et la présentation sont distinctes. La boucle Linux emploie
un accumulateur à 60 Hz et garde les fronts d'entrée jusqu'au pas qui les
consomme. Le temps de présentation comprend la fraction restante. Une longue
pause murale est bornée à 0,25 s dans `main.c` : le temps simulé n'est donc pas
nécessairement égal au temps mural. Les benchmarks à pose fixe et les fenêtres
à un pas par image sont explicitement des diagnostics différents du jeu réel.

## Inventaire : réutilisable et encore lié à LUMA

| Domaine et fichiers | Déjà présent et réutilisable | Couplage ou limite actuelle |
|---|---|---|
| Commandes GPU : `fw_console/gpu_v1.{c,h}`, `gpu_geometry.{c,h}` ; ABI `linux/drivers/prodock-uapi.h` et validation du noyau candidat | Construction des commandes de cible, copie, matériau, texture, quads, caméra, matrices, lumière et maillages ; interfaces sans règle de mission | Interface d'émission sans pointeur utilisateur ; `render.c` utilise un producteur global `active`. L'ABI, les bornes et les capacités doivent être conservées par profil |
| Rendu : `src/render.c`, `include/luma3d_render.h` | Batches de 64 commandes, validation avant émission, cache exact d'état, double buffering, culling par volumes, LOD, compteurs, arrêt avant PRESENT après erreur | `L3Render` contient directement héros, PNJ, eau, oiseaux, activités et HUD. La boucle reconnaît des identifiants d'objets et des phases de scénario LUMA |
| Ressources : `world/generated.h`, `world/data.c`, headers d'art ; générateurs des candidats | Tables de maillages, sommets/faces, matériaux, textures, instances et colliders ; alignement et limites contrôlés ; publications statiques au chargement | Ressources compilées dans l'ELF ; pas de chargeur générique de paquets ni de streaming de régions. Noms, palettes et atlas sont ceux du jeu |
| Monde et surface : `src/world.c`, `surface.c`, `include/luma3d_surface.h`, `surface_data.h` | Requêtes de hauteur et d'obstacle ; surface canonique extraite des triangles réellement rendus ; index spatial conservateur ; surfaces de pont | `world.c` connaît la séparation vallée/Terrasses, des coordonnées et l'avant-cour de l'atelier. Les listes de collisions restent parcourues directement |
| Déplacement/caméra : `src/game.c`, `include/luma3d_game.h` | Vecteurs, position/vitesse, gravité, saut, tampon de saut, tolérance de départ, déplacement relatif à la caméra, limitation des pentes, caméra amortie et collision caméra ; marche automatique par la même physique | `L3Game` embarque `L3Story` et les activités. `game.c` appelle les règles de l'atelier et les sites des PNJ ; les cadrages de dialogue sont spécifiques |
| Animation : `render.c`, `presentation.c`, `maze_motion.c`, `maze_events.c`, `puzzle_motion.c`, `simon_light.c` | Temps de présentation distinct, suivi avant/après des pas, interpolation sans extrapoler à travers les virages, invalidation d'époque/restart ; transforms calculées en temps réel | Marche à six pièces, arbre/moulin/eau/oiseaux codés pour les assets LUMA ; pas de système générique de squelette, de clips ou de mélange d'animations |
| Entrées : `L3Input`, `src/main.c` | Axes, boutons maintenus et fronts séparés ; logique indépendante de la fréquence de dessin ; reprise manuelle de la visite | Adaptateur concret TTY dans main, maintien des touches approximé par délai ; pas de backend manette validé pour ce jeu. `--host` est une capture de commandes, pas une fenêtre PC interactive complète |
| Moteurs d'activités : `minigames/l3_minigames.{c,h}`, `l3_simon.*`, `l3_shooter.*`, `l3_platform.*` | C déterministe, états bornés, init/step/view, entrées normales, statuts, codecs LE transactionnels ; indépendants du GPU et du monde | Huit règles finies et des cartes/paramètres intégrés, pas un langage universel de mini-jeux. Titres et aides français font encore partie des vues |
| Adaptateur d'activités : `src/arcade_core.c`, `activities.c` | Entrée/reprise/restart/BACK, relâchement des entrées, récompense gagnée une seule fois, validation et regroupement des codecs | `arcade_core` énumère huit moteurs. `activities.c` fixe noms, coordonnées, conditions de région et récompenses spatiales de LUMA |
| Interface : `src/hud.c`, `mini_ui.c`, `shooter_render.c`, `puzzle_gpu.c`, `puzzle_presentation.c`, `simon_native_gpu.c`, `simon_presentation.c` | Texte raster, palettes, ressources immuables, caches de canevas et de pages, publications de rectangles modifiés, quads avec alpha, sprites, composition de couches | Layouts et ressources propres aux activités ; pas de bibliothèque de widgets indépendante. Le header de rendu rassemble encore tous ces états |
| Sauvegarde : `src/progress.c`, `include/luma3d_progress.h` | Schéma explicite, IDs stables, CRC, contrôle sémantique, rejet transactionnel, écriture temporaire/fsync/rename ; chemins choisis explicitement | Champs de scénario, routes et régions encodés pour LUMA. Réutiliser le mécanisme exige un schéma de contenu, pas renommer une sauvegarde existante |
| Scénario/visite : `story.c`, `workshop.c`, `amber.c`, `showcase.c` | La visite utilise les mêmes entrées, collisions et moteurs que le manuel ; elle attend les présentations nécessaires et peut être annulée | Dialogues, énigmes, sites, parcours et séquence de démonstration entièrement LUMA. Ce sont du contenu et un pilote de vitrine, pas le noyau du moteur |

### Contrats à préserver

`L3World` expose des callbacks `height(context,x,z)` et
`blocked(context,x,y,z,radius,height)`, un domaine, une arrivée, une route et
des objectifs. Ce contrat permet de remplacer la source du terrain sans changer
les mathématiques du déplacement. L'implémentation actuelle du monde reste
cependant liée aux tables et règles de LUMA.

La collision utilise la surface canonique. Dans les 3,05 m autour du joueur,
le rendu sélectionne les mêmes triangles ; les LOD lointains restent des
approximations visuelles, jamais une surface de déplacement. Le découpage des
régions exclut de la soumission les instances de l'autre région, puis le frustum
élimine les objets invisibles. Il ne libère pas leurs ressources déjà chargées.

Les moteurs d'activités n'appellent pas le renderer. `activity_observer.c`
transmet vues et traces vers la présentation, sans ajouter les files d'animation
aux codecs. Son binding est encore global et filtré par l'adresse de `L3Game` :
une seule partie observée à la fois, pas un bus d'événements multi-mondes.
L'adaptateur bloque l'entrée E résiduelle et conserve les récompenses au restart.
Pendant l'activité, la pose et la mission du monde sont suspendues ; le retour
normal les conserve. Une reprise de sauvegarde effectue séparément les contrôles
de position sûre et peut remettre la vitesse à zéro.

## Rendu réellement utilisé

| Mode | Chemin actuel |
|---|---|
| Exploration | Géométrie G3D1, perspective, textures, Z16, éclairage/brume, ciel Gouraud mis en cache puis COPY, CLEAR Z, UI indexée |
| Maison et tour | Maillages G3D1 ; acteurs/obstacles dynamiques sur deux banques ; HUD séparé |
| Blocs et fusion **1024** | Fenêtre RGB565 permanente, fond par COPY, quads V1 et ARGB4444 pour ombres/transparence ; positions de présentation interpolées ; chrome indexé hors plateau |
| Simon | Instrument 2D natif, fond immuable et quads de lumière/appui ; caches par page, texte séparé |
| Shooter | Fond/atlas publiés au chargement, couches et sprites bornés, projectiles et effets ; aucune vallée 3D dessinée derrière l'activité |
| Circuit et formes | Canevas indexé avec caches et publications limitées aux changements ; logique indépendante du rendu |

KEY_ZERO des couches indexées est une découpe binaire ; ce n'est pas un mélange
alpha. Les quads ARGB4444 utilisent le raster matériel lorsqu'une transparence
partielle est nécessaire. Remplir davantage de couches n'accélère pas un rendu
3D. Le nombre utilisé dépend de la scène, des limites du pilote et du budget.
Les 16 couches matérielles ne sont pas toutes disponibles à l'application :
le terminal réserve notamment les couches 12–15 dans ce noyau.

Le cache de commandes conserve matrices, matériau, texture et lumière quand
les octets sont identiques. TARGET invalide ce cache ; CAMERA reste envoyé
après TARGET. SUBMIT attend la fin du lot ; la durée de cet ioctl contient
publication/cache, alimentation et attente, et ne doit pas être appelée en
bloc « coût du raster ». La capture hôte utilise le même producteur puis un
modèle indépendant des commandes ; elle ne précalcule pas une vidéo du jeu.

## Profils et mémoire : commun ne signifie pas identique

| Contrat | Profil 800×480 | Profil 1280×720 |
|---|---|---|
| Monde 3D | 400×240 puis affichage agrandi ×2 | 640×360 puis affichage agrandi ×2 |
| UI / plateaux natifs | Coordonnées 800×480 | Coordonnées 1280×720 |
| Taille d'une page réservée | 1 MiB | 2 MiB |
| Pitch RGB565 natif | 1600 octets | 2560 octets |
| Sélection | `PRODOCK_INFO` sur carte | `PRODOCK_INFO` sur carte ; `--720p` pour les tests hôte |

Les cibles V1 sont limitées à 1024×512. Les plateaux natifs 720p utilisent une
fenêtre locale dans une page de pitch 2560, pas une cible V1 1280×720 illégale.
Le producteur, les règles et les codecs sont communs ; tailles, dispositions,
sorties, intégration FPGA et pilotes d'entrée sont des contrats de profil.

Un futur validateur de profil devra réserver une page pour la hauteur native
effectivement écrite : `page_bytes >= pitch * screen_h` dans ces deux profils,
avec calcul sans débordement. La condition limitée à `pitch * render_h` ne
protège pas les fonds Simon et les pages natives. La validité d'une page mémoire
ne dispense pas de contrôler séparément les dimensions de chaque cible V1.

La fenêtre du jeu est de 32 MiB à partir de l'adresse physique `0x00800000`.
Les affectations suivantes sont des **réservations de ce runtime**, pas un
allocateur universel déjà extrait :

| Décalage relatif | Usage actuel |
|---|---|
| 0 et `page_bytes` | Deux pages couleur ; profondeur à `2 * page_bytes` |
| 6 MiB | Cache du ciel |
| 8 à moins de 14 MiB | Géométrie/textures du monde, PNJ et petites banques d'animation |
| 14 à moins de 15 MiB | Ressources puzzles/Simon, mutuellement exclusives |
| 15–17 MiB | Framebuffer console du noyau : **réservé, pas disponible au jeu** |
| 18 / 19 MiB | Atlas d'activité / héros |
| 20–24 MiB | Pages HUD et interface d'activités |
| 24–28 MiB | Géométrie statique d'activité puis banques dynamiques 26/27 |
| 28–32 MiB | Ressources shooter |

La réservation 14–15 MiB correspond à l'absolu `[0x01600000,0x01700000)`.
Son absence de chevauchement avec la console a été vérifiée contre les sources
du noyau **réellement compilé**, dans
[la provenance mémoire](../games/luma3d/candidates/arcade_motion_r1/provenance/root_memory_review_01.json).
L'ancien projet 14–18 MiB a été corrigé avant qualification. Une adresse libre
dans une capture hôte n'autorise pas à s'en servir sur une carte.

## MC1 : optimisation commune mesurée et non retenue

MC1 part de GM1 ; il ne change ni contenus, ni règles, ni commandes GPU.
Le [candidat de cache](../games/luma3d/candidates/maze_publish_cache_r1/README.md)
ajoute `src/mesh_cache.c` / `include/l3_mesh_cache.h` et un raccord de publication
dans `maze_render.c`. Deux ombres CPU comparent les blocs de 32 octets déjà
publiés dans les banques 26/27 MiB. Les blocs identiques ne sont pas réécrits.
La mémoire GPU n'est pas lue pour comparer. Le cache est privé à l'ouverture
du renderer et invalidé lors d'un changement de mapping ou d'activité.

Les deux profils ont passé localement 80 images sélectionnées, avec commandes,
codecs et 32 MiB exactement identiques à GM1. Les 16 fixtures RV32/QEMU et
quatre fenêtres de simulation concordent également. Ce sont des preuves
logicielles ; elles ne mesurent ni la fluidité Pro Dock de MC1 ni le GPU Neo.

Le [plan MC1 R3](../games/luma3d/tests/hardware/mesh_cache_20261027_mc1_prepared_r3/PLAN_MC1.md)
a exécuté maison puis exploration A/B/B/A, avec GM1 comme témoin et comme repli,
mesures séparées entrée/repos/mouvement, copies, cache/feed/wait/PRESENT et pics.
Le repli GM1 est prévu aussi en succès. Le refus de revue R2 est conservé ;
R3 ajoute un nettoyage protégé contre les signaux répétés et contrôle aussi les
régressions d'entrée/repos ainsi que la dérive des témoins. La revue indépendante
R3 et les huit oracles matériels passent ; les huit fenêtres de mesure sont
conservées dans le [rapport MC1](../games/luma3d/tests/hardware/mesh_cache_20261027_mc1_result/README.md).

Le cache n'est **pas retenu**. Dans la maison, les deux paires donnent
12,47→11,70 et 12,14→11,22 FPS : les écritures diminuent de 66,49 %, mais le
temps de publication avec comparaison augmente. L'entrée ralentit de 14,10 %
et 10,79 %, au-delà de la garde fixée. Le témoin au repos dérive également de
3,83 %, au-delà de la garde de 3 %. En exploration, où ce cache n'est pas
sollicité, le débit reste entre 9,65 et 9,77 FPS. Ces fenêtres déterministes
ne constituent pas un nouveau tour réel de campagne.

GM1 exact est restauré, sa progression et son identité vérifiées, la sauvegarde
V4 inchangée et le verrou/CDC libérés. Aucun FPGA, noyau, fichier SD ou flash
n'a été modifié. Le code commun envisagé doit donc encore être distingué du
runtime effectivement conservé : une optimisation correcte en pixels peut
rester plus lente et être écartée.

## Séparations utiles suivantes, sans refonte engagée

1. **Contrat de profil et plan mémoire** : regrouper les tailles, réservations,
   capacités et limites aujourd'hui dispersées ; faire vérifier chaque plage
   contre le profil et le noyau retenus. Conserver le producteur commun.
2. **Contexte de rendu indépendant** : sortir progressivement de `L3Render`
   les états héros/PNJ/activités et lui fournir des vues de scène et des handles
   de ressources. Remplacer à terme les bindings globaux par des contextes
   explicites, sans changer les octets de commande pendant cette séparation.
3. **Scène et contenu déclaratifs** : remplacer les comparaisons de noms et
   coordonnées dans le renderer/monde par propriétés d'instance, composants
   d'animation et actions de scénario. Garder les identifiants sauvegardés.
4. **Entrées et horloges** : isoler l'adaptateur TTY de la simulation ; ajouter
   ensuite un adaptateur manette à qualifier par carte. Conserver fronts,
   maintien, annulation de visite et sémantique des pauses.
5. **Bibliothèque d'activités et présentation** : garder `init/step/view/codec`
   sans GPU, séparer les règles des thèmes et dispositions graphiques ; fournir
   des événements de présentation explicites et bornés plutôt que relire une
   logique de jeu depuis le renderer.
6. **Persistance du moteur et schéma du jeu** : réutiliser contrôle transactionnel
   et écriture atomique, mais maintenir des migrations déclarées pour les
   scénarios LUMA. Ne pas transformer une extraction de code en changement
   silencieux de format ou de sens des anciens IDs.

Chaque extraction doit conserver ses témoins déterministes, les deux profils,
les limites mémoire et les captures pertinentes avant une mesure matérielle.
Ces tâches ne sont pas incluses dans MC1. Le contenu actuel ne constitue pas
encore une campagne de plusieurs heures ; la visite autonome couvre les
systèmes déjà implémentés. Véhicules, son matériel et jeux de cartes demandés
ne doivent pas être annoncés comme des capacités terminées de ce moteur.

## Complément : Festival R9 et activités de plateau

Un candidat logiciel séparé ajoute un jardin 3D et quatre moteurs de règles :
Othello, solitaire Klondike, Chroma (cartes de couleurs) et pendu français.
Le jardin contient quatre stands accessibles par plusieurs allées, une
fontaine, des arbres, des toitures et un héros articulé. Le panorama texturé
montre montagnes, forêt et lunes. Il s'agit d'une disposition avec deux
ambiances, pas de deux nouvelles cartes. Les coordonnées et la caméra sont
calculées pendant l'exécution, via le producteur G3D1 existant.

Les plateaux utilisent des quads ARGB4444 pour ombres, transparence et
glissements. Les zones modifiées sont restaurées par copie GPU du fond mis
en cache ; les pages et le texte ont des invalidations distinctes. La nouvelle
progression se sauvegarde séparément et ne remplace pas la campagne existante.
Les règles, le rendu et la persistance restent des composants distincts.

Identité figée : `games/luma3d/build/festival_20261027_r9/`, manifeste
`77b831d700a42ebdd69c8c0417cabbf49d48263291ebfea507f976c63f03def9`, ELF RV32
`6cdac82bb1b517c9d61680bf6542baec4b5fc586b2b202e8c3cf463615530f50`.
Les 208 images temporelles des deux profils concordent avec le modèle de
restauration complète ; les tests de logique, entrées, sauvegarde et la
campagne locale des deux cartes passent. Ce sont des résultats hors carte.

**R9 n'a pas encore tourné sur Pro Dock.** Le premier essai a échoué pendant
son transfert USB, avant l'arrêt de GM1. Le terminal a été récupéré et le même
GM1 PID3158/start27508908 vérifié actif, sans erreur GPU et avec la sauvegarde
inchangée. Le
[rapport d'essai](../games/luma3d/tests/hardware/festival_20261027_r9_board_r1/README.md)
conserve cet échec. Aucun FPS matériel R9 n'est déduit des captures hôte.

Le tour automatique de 450 images ne couvre pas les quatre tables aux cadences
simulées de 10, 30 et 60 FPS : il atteint seulement le jardin et Othello. Un
[candidat de mesure séparé](../games/luma3d/candidates/festival_animation_probe_20261027_r1/README.md)
effectue quatre actions par jeu, attend leurs transitions puis deux images
stabilisées. Il distingue les intervalles réellement animés des périodes au
repos. Ses 24 fenêtres comparées à R9 passent hors carte ; sa qualification
matérielle reste à réaliser.

Les prochaines retouches esthétiques et corrections de transport sont isolées
de R9. Ce complément ne change ni le FPGA G22r0 ni le noyau retenu et ne qualifie
pas le jeu sur la Neo. La campagne de plusieurs heures, les véhicules et le
son restent des travaux ouverts.

### 28 octobre : candidat visuel intégré et transfert encore bloqué

Le candidat `festival_integrated_20261028_r1` rassemble les retouches du jardin,
des panneaux et des halos, les lettres animées du pendu et les mesures séparées
d'actions animées. Les tests locaux, comparaisons de pixels et les onze groupes
des deux profils passent ; il n'a pas été essayé sur carte.

Le tmpfs de la Pro Dock était plein. Quatre anciens exécutables temporaires,
conservés et identifiés localement, ont été retirés après vérification ; 35,6 Mio
ont été libérés et GM1/sauvegarde recontrôlés. Le nouvel essai R6 de transfert de
R9 échoue toutefois après 116 paquets acquittés, sans réponse au paquet suivant.
Aucun arrêt de GM1 ni lancement de R9 n'a eu lieu. L'écoute passive supplémentaire
reste silencieuse : l'état du receiver est inconnu, sa récupération reste à faire.
Le dernier état GM1 vérifié est celui d'avant cet essai, pas une revalidation
après échec. Voir le
[rapport R6](../games/luma3d/tests/hardware/festival_20261028_r9_board_r6/README.md).

La récupération R6 est ensuite confirmée : sortie du receiver code1, terminal
utilisable, même GM1/sauvegarde, +68 présentations sans erreur GPU. Le contrôle
final est `festival_20261028_r6_health_resume_r3/result.json`. Les échecs
intermédiaires d’outils absents du rootfs sont conservés. Le delta incomplet
reste inutilisable ; aucun nouveau jeu n’a été lancé. Les ajouts visuels R2
et le cinquième stand Memory restent des candidats logiciels hors carte.

### 28 octobre : RX2 validé sur Pro Dock, mesures du jeu préparées

Le nouveau récepteur temporaire RX2 a passé six sessions sur la Pro Dock :
0, 513 et 16 384 octets, rejet/reprise d'un paquet volontairement corrompu,
arrêt après 512 octets puis reprise jusqu'à 1 024 octets. L'exécutable du
récepteur a été relu intégralement et identifié par SHA avant exécution ;
les données finales de chaque essai ont également été relues et comparées.
Le résultat est
`games/luma3d/tests/hardware/rx2_20261028_board_r3/result.json`, SHA
`e9a7712588e2ebcdfff3d04a15c1cc43526bf8fb3aa776d0a4f878df437156cb`.

Le même GM1 PID3158/start27508908 est resté actif : +2 390 présentations,
aucune erreur GPU et sauvegarde inchangée. Aucun FPGA, noyau ou contenu SD
n'a été modifié. Les tests ne qualifient pas encore le transfert d'un jeu
complet ; le récepteur historique n'a pas été remplacé.

Le candidat `festival_memory_metrics_20261028_r4` inclut le jardin enrichi,
les quatre tables et le cinquième stand Memory, avec instrumentation séparant
entrée, chargement des ressources, animations et repos. Les copies CPU de
Festival/Memory étaient absentes des anciens compteurs : elles sont désormais
comptées explicitement. Les 5 844 productions comparées restent identiques
au candidat visuel de référence. Ces preuves hors carte ne donnent aucun FPS
matériel. Ce nouveau jeu n'a pas encore été lancé sur Pro Dock.
