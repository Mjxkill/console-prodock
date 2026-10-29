# Inventaire ciblé des dépassements Luma — 28 octobre 2026

La dette principale est constituée de **ressources générées en C**, pas de
fonctions de jeu de dizaines de milliers de lignes. Les nouvelles règles
incluent néanmoins ce code produit sous notre contrôle : son origine générée
ne l'exempte pas. Aucune suppression, réécriture d'archive ou modification du
jeu n'a été effectuée.

Le relevé reproductible `inventory_luma.py` a examiné 11 455 fichiers portant
les extensions listées dans `luma_inventory.json`, sans suivre les liens.
Il relève **841 occurrences au-delà de 1 000 lignes, correspondant à
64 contenus SHA-256 distincts**. Les nombreuses copies ne représentent donc
pas 841 modules indépendants à réécrire.

| Emplacement | Fichiers examinés | Dépassements | Nature |
|---|---:|---:|---|
| Arbre de travail hors candidats/builds | 862 | 1 | `world/data.c`, ressource générée |
| Candidats et sources artistiques | 1 254 | 56 | 54 ressources, 2 bancs de tests |
| Copies de builds et sorties générées | 9 339 | 784 | 783 ressources, 1 copie de banc de tests |

Ces catégories décrivent **l'emplacement**, pas une exemption d'ownership.
Un candidat n'est pas automatiquement une archive ; une copie figée conserve
son statut et ses preuves, mais toute future reprise doit traiter la dette.
Les extensions non-code et le paquet `build-kernel` sont explicitement exclus
de ce mini-inventaire : il contient Linux/OpenSBI, des copies et des produits
de build, qui demandent une revue fournisseur/archive séparée. Ce rapport ne
déclare pas tous les fichiers de ce paquet exempts ni tout Luma conforme.

## Dettes à traiter lors des prochains changements de ces composants

| Source représentative | Lignes physiques | Action cohérente proposée |
|---|---:|---|
| `world/data.c` | 63 624 | Faire évoluer `world/export_c.py` : ressources identifiées par matériau/mesh/atlas, en conservant index, alignement et octets exacts. |
| `candidates/table_games_20261027_r1/art/festival_art.h` | 65 769 | Séparer les atlas de cartes et les fonds par responsabilité/profil, avec un manifeste de ressources et une interface unique. |
| `candidates/arcade_polish_r1/include/puzzle_art.h` | 57 548 | Séparer glyphes, polices et fonds ; vérifier la reconstruction exacte des données, pas seulement la compilation. |
| `candidates/arcade_polish_r1/include/shooter_art.h` | 30 093 | Réorganiser les données de décor/sprites via le générateur, sans dupliquer le moteur par plateforme. |
| `candidates/arcade_gpu_motion_r1/include/l3_simon_art.h` | 28 410 | Distinguer fonds 800/1280 et touches RLE derrière un contrat partagé. |
| `candidates/memory_constellations_20261028_r1/art/memory_art.h` | 5 065 | Ressources de cartes séparées du contrat de rendu ; préserver index et palette. |
| `candidates/adventure_showcase_r1/tests/test_render_contract.py` | 1 034 | Extraire le vrai banc C embarqué de la chaîne Python dans un fichier de fixture C, garder les scénarios et assertions. |
| `candidates/arcade_polish_r1/tests/test_render_contract.py` | 1 077 | Même séparation fixture C / pilote Python ; harmoniser les contrats plutôt que maintenir deux copies presque identiques. |

Les autres familles visibles sont `surface_data.h` (5 024),
`hero_polish.h` (2 070), `activity_art.h` (2 738), et les ressources ciel/plantes.
Les versions exactes, nombres de lignes et empreintes de **chaque occurrence**
figurent dans `luma_inventory.json`. Les sorties `world/data.c` expérimentales
atteignent 131 304 lignes ; ce sont des données de scène, pas une routine
algorithmique de cette longueur.

Les générateurs et moteurs examinés hors copies de build ne dépassent pas
1 000 lignes, à l'exception des deux bancs ci-dessus. Cela ne prouve pas leur
bonne modularité ou lisibilité : le comptage ne remplace pas la revue. Il
serait notamment incorrect de minifier davantage leurs lignes pour respecter
artificiellement le seuil.

## Ordre de traitement et preuves attendues

1. À la prochaine édition d'un asset, corriger son générateur et l'interface
   ressource, en laissant intactes les références et les builds gelés.
2. Prouver égalité des données décompressées, dimensions, index, alpha et
   alignements ; comparer captures et commandes sur les deux profils.
3. Extraire les fixtures des deux bancs lors de leur prochaine reprise, puis
   rejouer exactement leurs scénarios et leur contrôle de régression.
4. Établir les manifestes d'ownership des sorties réutilisées avant promotion.
   Ne supprimer une copie qu'après vérification de ses références et de la
   nécessité de conserver la preuve : aucun nettoyage n'est autorisé par ce relevé.

Le dernier lot Grove R5 a déjà séparé son **nouvel** atlas de plantes sans
changer son binaire par rapport à Grove R4. Cela ne régularise pas les grandes
ressources historiques héritées dans ses snapshots, ni les lots gelés Memory.
