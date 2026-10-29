# Revue indépendante LUMA3D art3 — 25 octobre 2026

Priorités proposées : alléger les calculs CPU statiques et les requêtes de
collision de caméra, puis essayer des mips éloignées des nouvelles textures
256². Aucun gain de FPS n'est mesuré par cette revue. Le tri du terrain opaque
et le retrait de SCISSOR restent le travail distinct de l'agent jeu.

Périmètre exact : [snapshot art3](../../build/valley_living_20261024_art3/manifest.json),
ELF `7fa1062373664d977c26bf6df2a4a5075d64061b967fc3d6d9b831a841302882`,
GPU G22r0 et [pilote figé](../../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c).
Sources lues seulement, aucun build, accès carte, changement de noyau/FPGA
ou génération d'image. [Empreintes et calculs](evidence.json).

## Ce que les mesures permettent de viser

Les [mesures vl2 existantes](../hardware/living_20261024_vl2/trial/result.json)
portent sur 30 images fixes après 3 de chauffe. Les temps ci-dessous sont
les mesures utilisateur, en ms/image ; le résidu n'est pas un profil exclusif
du renderer CPU. La simulation est désactivée dans ce benchmark.

| Pose | Image | Ioctls SUBMIT | Ioctl PRESENT | Hors ces deux API | Commandes / lots |
|---|---:|---:|---:|---:|---:|
| Arrivée 0 | 136,80 | 105,93 | 15,20 | 15,67 | 419 / 7 |
| Maëlle 90 | 96,67 | 71,00 | 16,17 | 9,50 | 182 / 3 |
| Village 1450 | 93,87 | 66,67 | 16,03 | 11,17 | 167 / 3 |
| Lac 2330 | 83,53 | 61,00 | 13,50 | 9,03 | 133 / 3 |
| Ruine 3200 | 78,03 | 57,73 | 12,27 | 8,03 | 95 / 2 |
| Retour 3800 | 134,43 | 107,80 | 14,47 | 12,17 | 375 / 6 |

Optimiser seulement la préparation CPU ne peut supprimer le temps des ioctls.
`feed` pilote contient la contre-pression FIFO ; `wait` contient GPU et attente
d'ordonnancement. Ne pas additionner ces compteurs imbriqués aux temps API.
Le compteur G3D comprend les attentes raster des DRAW mais pas tout le coût
du ciel/COPY/CLEAR. L'ELF annonce RV32IMAFDC : aucun diagnostic de « tout le
float en logiciel » n'est retenu.

## Pistes classées

| Priorité et preuve | Changement possible, risque | Mesure/contrôle nécessaire |
|---|---|---|
| **1 — CPU, répétitions présentes dans le code** | Pré-calculer centre/rayon monde, sin/cos et orientation/lumière locale des instances statiques ; constantes des plans de frustum et fog calculées une fois. Réutiliser le résultat du premier test de visibilité lorsque la borne du LOD choisi est incluse dans la borne testée. Les arbres animés, personnages et rotor gardent leur calcul dynamique. Risque faible avec mêmes opérations ; ne pas remplacer les bornes par une approximation plus petite. | Temps de construction des commandes séparé du SUBMIT, puis flux/pixels identiques sur les poses et les bords de frustum. Les effets du compilateur empêchent de déduire un nombre réel d'appels trigonométriques du seul C. |
| **1 — simulation, coût absent des poses fixes** | Préparer l'accès direct au pont et un index spatial conservateur des 71 cercles de collision ; calculer une fois la rotation du pont. Actuellement chaque requête de hauteur reparcourt 72 colliders pour trouver le pont, et la caméra répète hauteur/collision le long de plusieurs segments à chaque tick 60 Hz. Aucun collider box dans art3 : optimiser ses rotations ne ferait rien ici. | Compteurs de requêtes/candidats et temps simulation pendant le parcours réel. Même résultat des collisions, positions et caméra, y compris hors route et au bord du pont ; ne pas réduire le nombre de pas de caméra pour obtenir le gain. |
| **2 — CPU/publication, petit volume** | Dans l'eau dédiée, pré-calculer les mots UV invariants et éviter de réécrire une banque lorsque sa phase entière est identique. Parcourir une liste de groupes eau au lieu des 158 groupes. Les oiseaux restent dynamiques. Aujourd'hui 2 880 octets sont écrits/image, dont 576 pour les oiseaux. | Comparer les banques et images après alternance des deux pages, phase modulo 128 et retour de caméra. Gain CPU à mesurer ; cela ne supprime aucun appel de publication du pilote figé. |
| **2 — cache texture, candidat visuel distinct** | Ajouter un niveau 128² des patches terrain 256² éloignés : 25 niveaux représentent 819 200 octets supplémentaires. TEXTURE sélectionne explicitement base/dimensions/mip=1 ; le GPU décale déjà les UV, donc ne pas aussi les diviser dans les faces. Risque de perte de détail, popping et joints entre voisins de LOD différent. | Captures en mouvement, arêtes communes cohérentes à chaque mip, seuils/hystérésis ; mêmes géométries puis cycles/FPS à six poses. Le cache 32 KiB peut contenir une texture 128² entière, contre 128 KiB pour une 256². Ce rapport de tailles ne prouve pas un rapport de misses. |
| **3 — HUD, changements sémantiques seulement** | Conserver le bitmap composé pour une révision commune, puis copier vers chaque banque sans refaire les glyphes deux fois. Limiter l'effacement CPU aux lignes utilisées. Le HUD possède déjà un cache par page ; aucun transfert texte systématique par frame n'est à retirer. | Mesurer transitions dialogue/journal/toast, vérifier les deux banques, ouverture/fermeture et absence de pixels périmés. Aucun gain attendu sur un benchmark fixe chauffé. |
| **3 — parcours mineurs** | Résoudre `rock_far_budget` une fois au chargement et pré-classer les instances arbre/moulin plutôt que répéter `strcmp`/`strncmp`. | Flux inchangé ; faible priorité sans profil. |

Sources exactes : [bornes et matrices](../../build/valley_living_20261024_art3/source/games/luma3d/src/render.c:140),
[double test de visibilité et recherches](../../build/valley_living_20261024_art3/source/games/luma3d/src/render.c:291),
[eau/oiseaux](../../build/valley_living_20261024_art3/source/games/luma3d/src/render.c:223),
[collisions](../../build/valley_living_20261024_art3/source/games/luma3d/src/world.c:12),
[échantillonnage caméra](../../build/valley_living_20261024_art3/source/games/luma3d/src/game.c:34),
[HUD](../../build/valley_living_20261024_art3/source/games/luma3d/src/hud.c:50).

## Contraintes à préserver

- **CAMERA ne peut pas être omise après TARGET** : G22r0 invalide explicitement
  `camera_valid` à chaque TARGET ([gpu_geometry.v:208](../../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_geometry.v:208)).
  Le cache des matrices/lumière existant évite déjà certaines commandes ;
  supprimer aveuglément les réémissions d'état serait incorrect. Aucun bug
  de correction confirmé dans le snapshot examiné.
- Le pilote publie le cache avant **et** après chaque lot synchrone, puis à
  PRESENT ([submit:127](../../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c:127),
  [present:189](../../build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c:189)).
  L'ABI reste limitée à 64 commandes ; diminuer les octets animés ne supprime
  pas ces publications. Les barrières ne sont pas des opérations facultatives
  à enlever côté jeu. Les descripteurs de couches sont déjà mis en cache.
- Le ciel COPY remplit réellement le framebuffer et invalide le cache texture
  à chaque image ([gpu_v1.v:403](../../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v:403)).
  Un cache chaud conservé entre images ne peut donc être présumé. Réduire la
  zone copiée exigerait une preuve de couverture pour toute caméra ; aucune
  n'est fournie ici. Retourner au ciel Gouraud coûteux n'est pas recommandé.
- Les tags physiques du cache survivent aux changements de matériau/texture,
  avec index direct haché ([cache](../../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_texture_cache.v:1)).
  Les compteurs de misses existent en RTL mais ne sont pas exposés par ce
  noyau : ils restent **indisponibles**, et non supposés nuls.
- Les [billboards R4 mesurés](../hardware/benchmark_20261024_r4_prepared/REPORT.txt)
  ont baissé sommets/triangles sans gain global : pose 0, cycles G3D +5,8 %,
  DRAW/lots inchangés. La couleur-clé est testée **après** lecture texture
  ([gpu_v1.v:489](../../../../tang/impl/gpu_geometry_g22r0/source/tang/rtl/video/gpu_v1.v:489)).
  Un rectangle vide n'est pas gratuit. Une nouvelle tentative devrait réduire
  à la fois couverture vide et commandes ; le contour seul avait déjà créé
  un lot supplémentaire au moulin ([revue contour70](../../build/review_contour70_20261024/REPORT.txt)).
- Les sprites/couches de composition n'ont pas la profondeur ni la perspective
  du paysage. Ils conviennent au HUD déjà composé ; remplir les 16 couches
  n'est pas un objectif d'optimisation. Pas de changement alpha recommandé.

Prochain profil utile : chronométrer séparément simulation, préparation des
commandes hors flush, animation mémoire, HUD, SUBMIT et PRESENT dans un
candidat logiciel isolé. Comparer d'abord les pixels et la physique, puis le
même parcours silencieux sur carte par son opérateur. Éviter `fast-math` ou
des tables trigonométriques approximatives avant cette mesure : les arrondis
Q16.16 et le culling rendent leur effet visuel non neutre.
