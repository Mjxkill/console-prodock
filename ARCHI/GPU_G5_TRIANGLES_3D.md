# G5 — triangles matériels et première 3D

Le cœur reste à 800 MHz, l'AHB à 80 MHz, le GPU/DDR UI à 75 MHz et
le LCD à 35 MHz. G5 étend la FIFO de dessin [G2](GPU_G2_REGISTRES.md) ;
les interfaces d'affichage, des 16 couches et des 64 sprites sont conservées.

## Nouvelle commande : TRIANGLE, opcode 10

Toujours huit mots, envoyés à `0xe9001010`. Le compteur `DONE` et les
règles de publication/invalidation des caches restent ceux de G2.

| Mot | Contenu |
|---|---|
| 0 | `10 << 24`, page destination en 23:20, couleur indexée en 15:8 ; autres champs ignorés |
| 1 | Sommet 0 : X signé 16 bits en haut, Y signé 16 bits en bas |
| 2 | Sommet 1 : même format |
| 3 | Sommet 2 : même format |
| 4..7 | Réservés, écrire zéro |

La surface cible est une page 800×480 indexée, de base
`0x00800000 + page * 0x00100000`. Les coordonnées acceptent toute la plage
−32768..32767, quel que soit l'ordre des sommets. Un triangle d'aire nulle
n'écrit rien et termine normalement. La couleur zéro est écrite comme les
autres : la transparence relève ensuite des couches, pas du dessin.

Le rasteriseur teste les centres `(x+0,5, y+0,5)`. Après normalisation vers
une aire orientée positive dans le repère écran (Y vers le bas), chaque arête
A→B utilise `E = (Bx−Ax)*(2*y+1−2*Ay) − (By−Ay)*(2*x+1−2*Ax)`.
Le pixel est couvert si les trois E sont positifs ; à E nul, l'arête est
incluse seulement si `dy < 0` ou `dy == 0 && dx > 0` (règle haut/gauche).
Deux triangles voisins possèdent ainsi chacun leurs arêtes, sans double
couverture. Le contour en lignes conserve les extrémités incluses de G2.

`gpu_triangle(page,x0,y0,x1,y1,x2,y2,color,filled)` émet une commande
TRIANGLE pour le remplissage, ou trois lignes matérielles pour le contour.
Les arguments de coordonnées doivent tenir dans des entiers signés 16 bits.

## Chemin matériel

Le fonctionnement décrit ci-dessous correspond au bitstream G5 conservé.
Le GPU courant utilise le [rasteriseur par lignes et les aplats DDR natifs](GPU_SPANS_DDR256.md),
avec la même couverture et les mêmes commandes.


`gpu_triangle.v` réduit d'abord la boîte englobante à l'écran, puis calcule
les équations d'arêtes avec des accumulateurs signés de 36 bits. Le balayage
emploie ensuite des additions, sans division ni multiplication par pixel.
Il produit des segments horizontaux conservés jusqu'à leur acceptation.
Le blitter réutilise son tampon de ligne et son DMA de 32 octets, avec masques
aux extrémités. Un triangle très éloigné de l'écran ne provoque pas un
balayage de coordonnées hors écran. L'aire nulle et les boîtes vides sont
rejetées avant le balayage.

Il ne s'agit pas d'un débit d'un triangle par cycle : un triangle peut
nécessiter le parcours de sa boîte englobante, puis les écritures de ses
pixels. Le coût du dessin et celui de l'affichage sont mesurés séparément.

## Démonstration 3D

Le CPU travaille en arithmétique entière : rotations avec sinus/cosinus
Q14, test des faces arrière, découpage contre le plan proche, projection
perspective et tri des faces de la plus éloignée à la plus proche.
Un polygone découpé est triangulé en éventail. Le cube de gauche est en fil
de fer ; celui de droite utilise des faces de couleur uniforme.

Les pages 6/7 alternent pour la scène 3D, affichée sur la couche 0.
Le texte est dans la page 5, sur la couche 15 avec transparence zéro.
La page 4 sert uniquement à la référence CPU. Le GPU dessine la page arrière,
le CPU attend `DONE`, puis soumet le changement de couche au retour vertical.
L'ancienne page n'est réutilisée qu'après acquittement du commit.

| Commande USB | Effet |
|---|---|
| `T` | Prépare puis compare quatre poses pixel par pixel, avec 64 octets de garde ; termine sur la pose 0 |
| `J` | Pose suivante, avec comparaison ; la pose 3 teste le plan proche |
| `A` | Animation continue, deux rotations à des vitesses différentes ; bilan toutes les 120 images |
| `X` | Pause de l'animation ; le LCD continue à afficher la dernière image |
| `S` | État d'affichage et compteurs de défauts habituels |

Les commandes de diagnostic restent accessibles pendant l'animation.
Les autres démonstrations arrêtent l'animation et celles qui réutilisent ses
pages invalident sa préparation. G3/G4 reconstruisent leurs surfaces après
G5. La palette est globale et est préparée avec l'affichage désactivé.

Le bilan sépare la préparation CPU, le temps soumission/attente GPU, et la
trame complète incluant l'attente du retour vertical. Les sommes de cycles
sont sur 64 bits ; les lectures individuelles de MCYCLE sont sur 32 bits.
Les vérifications CPU des pixels sont exclues de la mesure d'animation.

Pas de Z-buffer, textures, éclairage interpolé ni correction perspective de
textures à ce jalon. Le tri des faces convient à ces cubes convexes ; il ne
résout pas les intersections arbitraires. Résultats dans
[TESTS_GPU_G5.md](../TESTS/TESTS_GPU_G5.md).
