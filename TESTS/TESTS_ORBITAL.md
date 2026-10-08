# Orbital : démo de tir automatique sur Pro Dock

Qualification du 9 octobre : ORBITAL R6 passe sur **C37**, avec 51 références
exactes et 28 546 images en 520,828 s (54,81 images/s), zéro underflow,
erreur ou rejet. [Preuves et corrections](CORRECTIONS_REVUE_20261008.md).
Les mesures antérieures ci-dessous restent historiques.

Développement du 5 octobre 2026. Demande : après Luma, une démo façon Halo,
de bonne qualité, **qui joue toute seule** et montre les possibilités de la
carte vidéo. Présentation et fabrication : `assets/orbital/README.md`.

Suivi du 7 octobre : la reprise de l'ensemble GPU, ORBITAL et SD/USB est
consignée dans [TESTS_REPRISE_20261007.md](TESTS_REPRISE_20261007.md).
Les références à R31 ci-dessous décrivent la validation initiale de la
démo ; ce nouveau suivi identifie séparément le FPGA réellement chargé.

Statut : **R6 validée sur Pro Dock par comparaison de pixels et endurance.**
R3 a remplacé R2 après le retour de l'utilisateur (« un peu léger », « trop
court », « le fusil doit tourner pour viser ») ; R4 y ajoute des images
originales générées sur gx10-1 ; R6 exerce presque tout le catalogue
d'accélérations du GPU et corrige trois défauts vus par l'utilisateur sur
l'écran. L'utilisateur a jugé chaque étape « de mieux en mieux » ; son avis
sur R6 a été reçu le 7 octobre : « Oui, correcte et fluide », alors que
l'ancien FPGA R40 était chargé. La qualification du FPGA corrigé C22 est
consignée dans la fiche de reprise ci-dessus.

## Qualification C22 — 8 octobre 2026

ORBITAL R6 : **51 images de référence exactes**, 520.7 s d'endurance, **28 549 images** (deux boucles complètes), **54.83 images/s**, 3264 octets d'écho USB exacts. Zéro underflow, erreur de dessin ou commande rejetée. Dessin maximal 16.348 ms ; composition maximale 1007/2556 cycles par ligne. Le périphérique USB conserve la même adresse et le mode HS. L'utilisateur confirme C22 : « Oui, correcte et fluide ». ORBITAL reste en lecture automatique.

Preuves : `reprise_20261007/reprise_20261007_c22_orbital_check/`.
Bitstream et sources : [archive C22](../bitstreams/console_gpu_sdusb_800.md).

## Périmètre matériel et mémoire

Pour les essais initiaux décrits dans cette section, le FPGA est exactement
**R31**, `bitstreams/console_gpu_v1_800.fs`, SHA-256
`60806fa2e988641e5b67ddcc5b13873c5b39c87621d5f1a23bbcf5e80b6d6aee`. Aucune
modification RTL, netlist ou contrainte, aucune synthèse. Orbital est une
application téléchargée par J-Link dans l'ILM, données et pile en DLM,
ressources en DDR ; le chargement est volatile et la flash n'est pas touchée.
La console négocie 480 Mbit/s.

| Élément | R3 | R2 |
|---|---|---|
| Programme à `0xa0000000` | 39 544 octets (texte 38 184, données 1 360), BSS 3 104 | 30 960 octets |
| SHA-256 programme | `66169f1871355988d0293e2ad95aaabffb8419415cca2bf5a4a57097a995ed8b` | `859b68b8…29f0538` |
| Ressources à `0x05000000` | 4 315 328 octets, CRC32 `4001c3b5` | 842 688 octets, CRC32 `f3931670` |
| SHA-256 ressources | `a4f4f7d366886dcacec77fdc23abfdaa0e5bf0e6f19622302ef7de1d50a4d760` | `a3645db7…fe8169f8` |
| Chargement complet par J-Link | 7 min 12 s, relecture comprise | 87 s |
| Programme seul | 5 s | 4 s |

R6 (version courante) : programme **45 056 octets** (texte 43 680), SHA-256
`f9b5eaea02651f43648e7585aa61ebebddd311b2b8c7cfa616186f6cd86ddfcb` ;
ressources **5 781 728 octets**, CRC32 `7bf044fa`, SHA-256
`a1e917a4d8b6b393e74f813d487edb5846ca87ca073f53f00f4567b8ac2ac1c5` ;
chargement complet avec `--fast` : **332 s**.

R4 : programme **39 944 octets** (texte 38 584), SHA-256
`b9e8f5696ec469a2ea23db377c9d1956994bf71ddf035828e68fa94681f5a321` ;
ressources **5 005 408 octets**, CRC32 `93979610`, SHA-256
`a94575de57a8801e0a12357273775dbffc59c29b84e6b42b1a18d2afb8c388b9` ;
chargement complet avec `--fast` (sans relecture J-Link) : **288 s**.

Pendant le chargement complet le processeur est arrêté : l'écran reste figé
sur la dernière image, éventuellement abîmée par les ressources en cours de
remplacement. Ce n'est pas un plantage. Débit observé : environ 20 ko/s ;
`load_orbital.py --fast` supprime la relecture J-Link ; le programme vérifie
de toute façon le CRC32 des ressources avant d'afficher.

## Historique : r1, puis R2 (boucle de 69 s, remplacée par R3)

### r1 (premier jet, entièrement en triangles)

Chargé et démarré sur carte (`board_r2/load_r1`), jamais vérifié par poses.
Deux défauts ont été trouvés en reprenant le travail :

1. **Table de sinus tronquée** : 64 valeurs dans un tableau de 65, la valeur
   15791 manquait. Les indices 53 à 63 étaient décalés et `cos(0)` valait 0.
   À lacet nul toute la station était rejetée par le plan proche : les
   références d'origine `preview/expected.json` montrent 5 commandes, 0
   fragment et le même CRC `aca0b732` (ciel seul) aux phases 40, 1100 et 2100.
   Ces références et images sont **conservées telles quelles comme témoin**.
   Le balayage UBSan ne pouvait pas le voir (aucun comportement indéfini).
   `render_orbital.py --sweep` compare désormais la table à `sin()` et exige
   la présence de la station à chaque phase.
2. **Cadence** : état lu sur la carte après plusieurs heures de marche,
   `fps_x100=3695`, `fx_max=25955202` : 36,9 images/s en moyenne et jusqu'à
   **32,4 ms** par image, soit 27,5 images/s dans le couloir.

### Mesures qui ont guidé R2

Le compteur est celui du **CPU à 800 MHz** (1 M cycles = 1,25 ms ; une
période LCD de 18,17 ms = 14,53 M cycles). Commandes `B` (une image, étapes
désactivables) et `M` (micro-banc) ajoutées au programme.

Phase 250 de r1 : 19,05 M cycles, dont préparation CPU 0,62 M, copie du ciel
5,2 M, effacement Z 0,5 M, surfaces unies Gouraud+Z 11,3 M, panneaux texturés
1,4 M. Coût d'un plein écran 400 × 240 selon l'opération :

| Opération | M cycles | cycles/pixel |
|---|---:|---:|
| Effacement rectangle, couleur ou Z | 0,53 | 5,5 |
| Effacement rectangle, couleur et Z | 0,84 | 8,8 |
| Copie RGB565 | 5,26 | 55 |
| Triangle uni | 8,96 | 93 |
| Triangle Gouraud | 9,98 | 104 |
| Triangle Gouraud + Z | 12,9 | 134 |
| Triangle Gouraud + brouillard + Z | 13,96 | 145 |
| Triangle additif | 11,3 | 118 |
| Triangle texturé | 14,3 | 149 |
| Texture perspective + Gouraud + Z | 18,2 | 190 |
| ARGB4444 + Z (texels transparents compris) | 17,8 | 186 |

Un effacement d'une ligne coûte 1,2 à 1,4 k cycles quelle que soit sa largeur
(3 k en couleur + Z sur 200 pixels) ; une colonne d'un pixel coûte environ
100 cycles par ligne ; un triangle ajoute environ 300 cycles par ligne
balayée. Ces chiffres valent pour les séquences mesurées.

### R2

- Sol et plafond tracés **par lignes** (couleur + profondeur exactes de la
  ligne), murs unis en **barres verticales** de 2 à 16 pixels, par l'opcode 28.
  Les barres débordent de leurs bords inclinés ; les lignes de sol, de plafond
  et de ciel dessinées ensuite recoupent ces bords.
- Ciel copié seulement où il se voit : baies vitrées ligne par ligne,
  ouverture de la cloison, bande au-dessus de l'horizon dans la baie, et
  compléments par ligne là où la plate-forme ne couvre pas.
- Triangles conservés pour les panneaux texturés en perspective, montants,
  rails, drones, lumières ; tampon Z conservé.
- Drones émis en suites de cellules 16 × 16 occupées (40 à 46 cellules sur 64
  selon la pose).
- Ajouts : brume de profondeur (formule du brouillard matériel, mêmes
  constantes pour le CPU et pour `GPU_V1_FOG`), éclair de tir et lueur
  d'explosion sur le décor, dix drones au lieu de cinq avec apparition en
  fondu, ondes de choc additives, final avec trois explosions lointaines et
  halo croissant.

Le dégradé du sol et des murs est calculé par ligne et par barre : il n'est
pas identique au pixel près à celui de r1, qui n'avait été ni validé ni archivé.

Étapes mesurées (pire image d'un échantillonnage de la boucle) :

| Version | Phase 250 | Pire image | Cadence sur une boucle |
|---|---:|---:|---:|
| r1, triangles | 19,05 M (23,8 ms) | 25,96 M (32,4 ms) | 36,9 images/s |
| Lignes sol/plafond, ciel limité | 11,17 M (14,0 ms) | 17,7 M (22,1 ms) | 49,6 |
| + murs en barres | 5,87 M (7,3 ms) | 11,64 M (14,6 ms) | 55,03 |
| R2 avec tous les effets | — | 12,39 M (15,5 ms) sur 950 phases | 55,04 |

Un premier réglage des effets atteignait 14,43 M cycles quand cinq drones se
chevauchaient dans la baie ; les apparitions ont été étalées (phases 2770 et
2890). Le plafond retenu pour le contrôle est 13,5 M cycles (16,9 ms).

## Validation sur hôte

```sh
python3 tools/render_orbital.py --sweep --prove --animation
```

- **3 800 phases sous UBSan** : au plus **1 786 commandes GPU** et
  **24 sprites** par image, table de sinus exacte, station présente partout.
- **Preuve de couverture** : chacune des 3 800 phases est identique, sur les
  192 000 octets de la page, à la même phase rendue avec une copie de ciel
  plein écran, en partant d'une mémoire empoisonnée. Cette preuve a révélé
  puis permis de fermer trois défauts de jointure (pied de mur, débord des
  barres au-dessus de l'horizon, ciel sous l'horizon vu par la cloison).
- **31 poses** rendues par le modèle Python indépendant de
  `TESTS/test_gpu_v1.py`, non modifié : titre, couloir, apparition, éclair de
  tir, deux drones, lueur et onde de choc, cloison, passage, vagues de la
  baie, phases les plus lourdes, explosions lointaines et halo final.

Preuves : `orbital_20261005/host_validation_r2.txt`, `reference_r2/`
(images, `expected.json`, `orbital.mp4` calculé, **pas une capture du LCD**),
`build_r2.txt`, `sources_r2.tar.gz`.

## Validation sur carte (ax15, Pro Dock)

Base sans les effets (`board_r2/check_base_endurance`) : 22/22 poses exactes,
17 362 images en 316,5 s, temps de dessin maximal 11,66 M cycles.

**R2** (`board_r2/load_r2`, `board_r2/check_r2`), `check_orbital.py` :

- **PASS, 31/31 poses** : somme LCD RGB666 et CRC32 des 192 000 octets RGB565
  égaux aux références.
- Puis **372,69 s** d'animation, **20 439 images** (54,84 images/s, contrôles
  USB compris), soit plus de cinq boucles.
- Temps de dessin maximal **12 375 156 cycles (15,47 ms)**, pour une période
  LCD de 18,17 ms.
- Composition maximale **751/2 556 cycles par ligne**, 14 sprites au plus par
  ligne, rechargement maximal du cache de sprites 2 754 cycles.
- **2 336 octets d'écho binaire** exacts ; erreurs, sous-alimentations LCD,
  couches ou sprites invalides et commandes refusées : zéro. USB 480 Mbit/s.

L'écart entre 54,84 et 55,04 images/s vient des échanges de diagnostic, qui
occupent la boucle du processeur ; sans eux le programme mesure 55,04.

## R3 : sept chapitres, quatre minutes

### Contenu

Boucle de **13 200 phases** (240 s) : sas d'amarrage, baie d'observation,
monte-charge à paroi vitrée (descente de 900 unités), salle du réacteur,
Gardien, alerte et évacuation, pont extérieur. 32 ennemis de trois sortes,
fusil en 17 images pré-tournées qui se tourne vers la cible, tirs qui
voyagent, détecteur de mouvement, compteurs, jauge du Gardien.

Le niveau est une suite de sept salles convexes reliées par des portes
(`orb_cells`). Ordre de dessin : ciel des salles ouvertes ; salles de la plus
lointaine à la plus proche, chacune limitée par le ciseau au rectangle d'écran
que laissent les portes ; blocs isolés (piliers, caisses) après le sol de leur
salle ; ennemis et effets avec test de profondeur.

Aucune image nouvelle n'a pu être générée (quota de l'outil épuisé jusqu'au
9 octobre) : l'élite et le Gardien sont composés par
`build_orbital_assets.py` à partir de la feuille de drones existante.

### Budget de dessin

Mesuré avec la commande `B`, une phase sur dix puis une sur quatre ou cinq.
Premier jet : 235 points sur 1 320 au-dessus de 13,0 M cycles, pire image
18,7 M (salle du réacteur). Allègements successifs, sans retirer d'élément :

- taille à l'écran des ennemis plafonnée (100, 116 et 140 pixels) ;
- halo du cœur plafonné, ondes de choc en 12 segments ;
- largeur des barres à bord exact adaptée à la pente réelle du bord ;
- blocs d'une seule teinte, tolérance de 3 pixels à leurs extrémités ;
- bandes d'ombrage de 90 unités sur les murs de plus de 240 ;
- ciel non copié derrière le mur du fond d'une salle ouverte ;
- arène en hangar vitré plutôt qu'à ciel ouvert (3,3 M cycles de ciel) ;
- apparitions d'ennemis étalées aux trois pics.

Résultat : **pire image 13,20 M cycles (16,5 ms)** sur 3 300 phases mesurées,
pour une période LCD de 14,53 M (18,17 ms).

### Validation sur hôte

- **13 200 phases sous UBSan** : au plus **2 024 commandes GPU** et
  **28 sprites** par image.
- **Preuve de couverture** sur les 13 200 phases : identité avec la copie de
  ciel plein écran. Elle a révélé quatre défauts, tous corrigés : jambage de
  porte passant devant le plan proche (jusqu'à 30 777 pixels non couverts au
  franchissement du sas), jonction du linteau et des vantaux, seuil de porte
  entre deux salles, pied de la paroi vitrée du monte-charge.
- **51 poses** de référence par le modèle Python indépendant non modifié.
- Écart par rapport au plan : pas de comparaison pixel à pixel avec R2, le
  niveau ayant changé (tour de la baie, éclairage, ennemis).

Preuves : `orbital_20261005/host_validation_r3.txt`, `reference_r3/`
(images, `expected.json`, `orbital.mp4` calculé, **pas une capture du LCD**),
`build_r3.txt`, `sources_r3.tar.gz`.

### Validation sur carte

`board_r3/load_r3a` (ressources), `board_r3/load_r3` (programme),
`board_r3/check_r3` :

- **PASS, 51/51 poses** : somme LCD RGB666 et CRC32 des 192 000 octets égaux
  aux références.
- Puis **520,73 s**, **28 551 images** (54,83 images/s, contrôles USB
  compris), plus de deux boucles ; en marche libre le programme mesure
  55,04 images/s sur une boucle.
- Temps de dessin maximal **13 290 508 cycles (16,61 ms)**.
- Composition maximale **850/2 556 cycles par ligne**, 24 sprites au plus par
  ligne, rechargement maximal du cache de sprites 3 093 cycles.
- **3 264 octets d'écho** exacts ; erreurs, sous-alimentations LCD, couches ou
  sprites invalides et commandes refusées : zéro. USB 480 Mbit/s.

### Revue externe

Le critique externe était indisponible quand le plan R3 lui a été soumis, et
sa revue de code finale est revenue vide (modèles sans réponse). R3 repose
donc sur les preuves automatiques ci-dessus, sans revue indépendante.

## R4 : images originales générées sur gx10-1

L'utilisateur a ouvert l'accès au ComfyUI de gx10-1 et gx10-2. Dix-neuf
images ont été produites par `tools/orbital_art.py` (Qwen-Image 2512 et
Qwen-Image-Edit 2509, 4 étapes, 6 à 30 s chacune) : Gardien, élite et
éclaireur en quatre poses, ciel d'aube, illustration d'ouverture, cinq
textures de décor. Description et graines dans `assets/orbital/art.json`,
prompts dans `assets/orbital/prompts.md`, images dans `source/gen/`.

Changements par rapport à R3 :

- Gardien et élite remplacés par des dessins originaux ; quatrième sorte
  d'ennemi, l'éclaireur (9 des 32 ennemis) ; fond vert détouré par l'outil
  de ressources, quatre poses recadrées ensemble.
- Textures de décor en 128 × 128 (écrans, trappes, piliers, caisses, portes).
- Ciel d'aube pour le niveau inférieur et le final ; ciel de nuit au niveau
  supérieur. Les deux ne sont jamais visibles en même temps (la salle du
  réacteur, sans ciel, les sépare).
- Illustration d'ouverture copiée dans la fenêtre 3D pendant les 150
  premières phases, sous le titre.

Les nouvelles poses occupent 86 à 94 % de leurs cellules de texture, contre
62 à 72 % pour les drones : premier essai à **16,4 M cycles** pendant le
combat du Gardien, 182 points sur 1 650 au-dessus de 12,8 M. Réglages : taille
maximale à l'écran 100, 92, 116 et 88 pixels (drone, élite, Gardien,
éclaireur), brouillard retiré des ennemis, trappes, plaques de porte et faces
de caisses texturées un peu plus petites, piliers habillés à moins de 400
unités. Résultat : **pire image 13,05 M cycles (16,3 ms)** sur 2 640 phases.

Validation sur hôte (`host_validation_r4.txt`, `reference_r4/`,
`build_r4.txt`, `sources_r4.tar.gz`) : 13 200 phases sous UBSan, au plus
2 016 commandes et 28 sprites ; preuve de couverture sur les 13 200 phases ;
51 poses de référence.

Validation sur carte (`board_r4/load_r4a`, `board_r4/load_r4`,
`board_r4/check_r4`) :

- **PASS, 51/51 poses** exactes (somme LCD et CRC32 des 192 000 octets).
- **520,74 s**, **28 550 images** (54,83 images/s, contrôles USB compris).
- Temps de dessin maximal **13 169 477 cycles (16,46 ms)**.
- Composition maximale 855/2 556 cycles par ligne, 24 sprites au plus par
  ligne, cache de sprites 3 037 cycles.
- 3 264 octets d'écho exacts ; erreurs, sous-alimentations, éléments
  invalides et commandes refusées : zéro. USB 480 Mbit/s.

R4 n'a pas eu de revue externe non plus (voir R3).

## R6 : catalogue d'accélérations et fluidité

### Contrôle demandé par l'utilisateur

« Je ne suis pas sûr qu'on utilise toutes les accélérations de la carte
graphique. » Comptage des commandes réellement émises par R4 sur 1 886
phases : effacements rectangle, copies, triangles texturés en perspective,
Gouraud, brouillard, Z, additif, couches et sprites étaient utilisés ; en
revanche aucun mipmap, aucune répétition ni clé de texture, une seule cible
de rendu, aucun texte GPU, aucune rotation, aucun décor en tuiles, aucune
animation de palette, aucun retournement de sprite et aucune commande des
opcodes 2D indexés 1 à 13.

Ajouts de R6, avec le comptage sur 1 886 phases de la version R5 qui les a
introduits :

| Accélération | Emploi | Mesure |
|---|---|---|
| Rendu dans une texture, invalidation du cache | écrans muraux du sas et du couloir d'alerte : cible 128 × 128 redessinée à chaque image | 468 phases |
| Texte GPU V1 (atlas ARGB4444) | libellés de ces écrans | idem |
| Mipmaps | emblème 512 × 512 au sol de la baie, niveaux 1 à 3 selon la distance | 191 liaisons |
| Répétition de texture et clé de couleur zéro | poutrelles ajourées devant la verrière du monte-charge | 471 matériaux |
| Rotation de quads texturés | éclaireurs qui s'inclinent | — |
| 2D indexé : aplat, disque, cercle, ligne, texte, dégradé | page d'interface redessinée par le moteur 2D : détecteur de mouvement avec balayage, compteurs, horloge, bouclier | 32 185 commandes |
| Décor en tuiles, défilement matériel, tuiles retournées | bandeau d'alerte | 271 phases |
| Animation de palette | accents de l'interface virant au rouge pendant l'alerte | 270 phases |
| Retournement de sprites | éclats | — |

Non exercés : le niveau 0 de la texture 512 (dans une fenêtre 400 × 240 elle
est toujours réduite, le bon niveau est 1 à 3), le zoom et les transformations
affines du moteur indexé (pas de référence logicielle réutilisable dans
`reference_draw` ; la rotation est montrée par le moteur RGB), les dégradés
verticaux et diagonaux, la copie indexée et le mode RGB natif 800 × 480.

Deux mesures utiles pour la suite :

- Un quad tourné coûte environ le double d'un quad droit, et un quad étroit
  et très haut coûte bien plus que sa surface. Le rasteriseur travaille par
  segments exacts (`gpu_triangle.v`), mais chaque segment a un coût fixe
  (environ 300 cycles CPU pour un aplat, davantage quand plusieurs plans
  sont interpolés, car ils partagent une paire de multiplieurs) : beaucoup de
  segments courts coûtent cher. La vrille des ennemis détruits (16 M cycles)
  a été retirée, les poutrelles affinées.
- L'image affichée n'influe pas sur le temps de dessin (13,69 à 13,73 M
  cycles pour la même image, quel que soit le nombre de couches à l'écran).

La page d'interface est redessinée de façon incrémentale : détecteur à chaque
image, compteurs, horloge et bouclier seulement quand leur valeur change.
`render_orbital.py --sweep` vérifie une phase sur trois que ce redessin, parti
de la page d'il y a deux images ou d'une phase quelconque, donne exactement la
page d'un redessin complet. Son oracle est `reference_draw` de
`fw_console/gpu_demo.h`, la référence logicielle des jalons G2 à L12.

### Défauts signalés à l'écran et corrigés

- Ennemis traversant les piliers du réacteur : trajectoires recentrées.
- Plaques des portes disparaissant d'un coup : fixées au vantail, elles
  coulissent et rentrent dans le mur.
- Caméra saccadée : position et angle étaient entiers (un cran d'angle =
  1,4°). Caméra en 1/16 d'unité et 1/65536 de tour dans tout le moteur.

### Validation

Hôte : preuve complète avant la dernière correction
(`host_validation_r6.txt` : 13 200 phases sous UBSan, couverture sur les
13 200 phases) ; après elle (`host_validation_r6_final.txt`) : balayage UBSan
des 13 200 phases, au plus 2 000 commandes et 24 sprites, couverture
revérifiée sur la zone modifiée, 51 poses dans `reference_r6/`.

La comparaison de pixels sur carte a trouvé un défaut que l'hôte seul ne
pouvait pas voir : à la pose 10450, les écrans du couloir d'alerte, vus depuis
l'arène par la porte ouverte, n'étaient pas recalculés (contenu périmé sur la
carte, mémoire vierge sur l'hôte). L'image est maintenant recalculée dès
qu'une salle à écrans est en vue.

Carte (`board_r6/load_r5a` ressources, `board_r6/load_r6d` programme,
`board_r6/check_r6`) :

- **PASS, 51/51 poses** exactes.
- **520,73 s**, **28 549 images** (54,83 images/s, contrôles USB compris) ;
  55,04 images/s en marche libre.
- Temps de dessin maximal **13 176 729 cycles (16,47 ms)**, interface 2D
  comprise ; seuil du contrôle 13,7 M.
- Composition maximale 990/2 556 cycles par ligne, 24 sprites au plus par
  ligne, cache de sprites 2 631 cycles.
- 3 264 octets d'écho exacts ; erreurs, sous-alimentations, éléments
  invalides et commandes refusées : zéro. USB 480 Mbit/s.

Pas de revue externe (voir R3).

## Limites connues

- Mise en scène automatique : ni jouable, ni sonore.
- La caméra ne tourne que de ±17° et avance toujours dans le même sens : pas
  de virage ni de retour en arrière (les salles sont alignées).
- Marge au pire cas de R6 : 1,7 ms.
- Les barres donnent aux murs proches un dégradé par paliers d'un niveau de
  couleur, visible comme un léger quadrillage.
- Les bancs `B` et `M` restent dans le programme ; ils ne s'exécutent que sur
  commande et mettent la démo en pause.
- Tout nouvel effet se mesure avec `B` avant d'être gardé.
