# L12 — dessin affine dans les pages DDR3

Implémentation du 30 septembre 2026. La validation physique et son statut
sont consignés dans [la fiche L12](../TESTS/TESTS_GPU_L12.md).

## Périmètre

Le blitter dessine une image avec rotation, agrandissement ou réduction
indépendante sur chaque axe, retournement, translation et cisaillement.
Les combinaisons de ces transformations utilisent la même unité matérielle.
La source et la destination sont des pages DDR3 indexées sur huit bits.
L'index zéro conserve le pixel déjà présent à destination.

Le résultat est dessiné dans une page avant sa présentation : le compositeur
16 couches et les 64 sprites matériels gardent leurs contrats L11/G4.
La rotation directe d'un sprite durant la composition, le filtrage bilinéaire,
la perspective et le mélange alpha restent des extensions distinctes.

La taille source est limitée à **128 × 128** pixels ; le rectangle destination
peut couvrir l'écran entier. La source peut être une région d'une page utilisée
aussi comme destination : son contenu est capturé avant la première écriture.
Chaque nouvelle commande recharge la source. Le cache ne persiste pas entre
les dessins, ce qui évite d'introduire une règle d'invalidation supplémentaire.

## Capacité et commandes

Le bit 0 du registre blitter `0xe9001020` indique cette version affine.
Les autres bits sont réservés. L'identifiant `BLT2`, les registres existants,
les commandes de huit mots et les opcodes 1 à 11 sont conservés.

La transformation se transmet avec deux commandes ordonnées. Le contrat
du pilote demeure **un seul producteur** de commandes. Le compteur `DONE`
compte séparément la configuration et chaque dessin.

### Opcode 12 : `GPU_AFFINE_SETUP`

| Mot | Valeur |
|---|---|
| 0 | `0x0c000000` ; bits 23:0 réservés à zéro |
| 1 | `u0`, signé Q16.16 |
| 2 | `v0`, signé Q16.16 |
| 3 | `du_dx`, signé Q16.16 |
| 4 | `dv_dx`, signé Q16.16 |
| 5 | `du_dy`, signé Q16.16 |
| 6 | `dv_dy`, signé Q16.16 |
| 7 | Réservé à zéro |

Les six valeurs sont des entiers signés 32 bits, divisés par 65 536 pour
obtenir leur valeur réelle. Par exemple `65536` vaut 1, `32768` vaut 0,5,
`-65536` vaut −1. La plage est [−32768 ; 32767,9999847].

Une configuration reste active jusqu'à la suivante ou à la remise à zéro.
Au reset, elle est invalide. Une configuration dont un bit réservé est
non nul invalide la matrice ; les dessins suivants ne produisent rien
jusqu'à une nouvelle configuration valide. Aucun accès DDR n'est effectué
par la configuration.

### Opcode 13 : `GPU_AFFINE`

| Mot | Valeur |
|---|---|
| 0 | `{13 sur 8 bits, page destination sur 4 bits, page source sur 4 bits, 16'b0}` |
| 1 | `{x destination, y destination}`, deux signés 16 bits |
| 2 | `{largeur destination, hauteur destination}`, deux valeurs de 1 à 32767 |
| 3 | `{x source, y source}`, deux signés 16 bits |
| 4 | `{largeur source, hauteur source}`, deux valeurs de 1 à 128 |
| 5–7 | Réservés à zéro |

Les pages sont numérotées de 0 à 15 : adresse en octets
`0x00800000 + page × 0x100000`, pas de ligne de 800 octets,
480 lignes utiles. Toute la région source doit tenir dans sa page.
Le rectangle destination est découpé aux bords de l'écran.

Une configuration absente/invalide, une dimension refusée, une source hors
page ou un bit réservé non nul terminent la commande sans écriture.
Comme pour le zoom existant, ce refus n'incrémente pas `BAD` : celui-ci
reste le compteur d'opcodes inconnus. `DONE` progresse même pour un dessin
vide. Le pilote vérifie les dimensions avant de les réduire sur 16 bits.

## Échantillonnage et précision

Pour chaque pixel destination `(x,y)`, avec l'origine destination `(xd,yd)` :

```text
dx = x - xd                 dy = y - yd
U  = u0 + dx*du_dx + dy*du_dy
V  = v0 + dx*dv_dx + dy*dv_dy
u  = floor(U/65536)         v  = floor(V/65536)
```

Si `u` ou `v` est hors de la région source, le pixel est transparent.
Sinon il lit `(xs+u,ys+v)`. L'index zéro est également transparent.
Il n'y a ni interpolation des couleurs, ni division par pixel, ni
répétition automatique de la source.

Il s'agit d'une transformation **inverse**, allant du pixel destination
vers la source. Par exemple `du_dx=0,5` agrandit deux fois horizontalement.
Les positions sont mesurées aux coordonnées entières ; aucune correction
implicite d'un demi-pixel n'est ajoutée. Pour tourner autour d'un pivot,
le logiciel inclut son décalage dans `u0` et `v0`.

Les sommes et accumulateurs sont signés sur **48 bits**, y compris le
décalage dû au clipping. Les coordonnées extrêmes et les pas négatifs
ne sont donc pas ramenés artificiellement dans la source par un débordement
32 bits. Les comparaisons vérifient le signe et les bits de poids fort
avant d'autoriser l'écriture ; un échantillon hors région ne déclenche
jamais une lecture DDR hors page.

## Chemin matériel

1. Chargement ligne par ligne de toute la région source par le port S
   existant ; au maximum 65 demi-mots pour une ligne commençant à une
   adresse impaire.
2. Réalignement dans un cache de **8192 mots de 16 bits**, soit **16 Kio**,
   avec un pas normalisé de 128 octets. Les dernières lignes/colonnes
   non utilisées sont ignorées, sans initialisation nécessaire du cache.
3. Préparation de l'origine découpée par des multiplications enregistrées.
4. Lecture synchrone du cache et addition des incréments horizontaux :
   après amorçage, **un pixel destination par cycle GPU** dans la mémoire
   de ligne, avec un masque indépendant pour chaque octet.
5. Écriture par le port W et le DMA DDR3 natif existant, puis addition des
   incréments verticaux pour la ligne suivante.

Le débit d'un pixel par cycle décrit l'étape d'échantillonnage. Le temps
complet inclut le chargement de source, les écritures et l'arbitrage DDR.
Il ne constitue pas une promesse de débit global sur n'importe quelle scène.
Les horloges restent CPU 800 MHz, bus 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz.

## API C

```c
gpu_affine_transform t = {
    .u0=127*65536, .v0=0,
    .du_dx=0, .dv_dx=65536,
    .du_dy=-65536, .dv_dy=0
};
gpu_command setup = gpu_make_affine_setup(&t);
gpu_command draw = gpu_make_affine(6,15,100,120,128,128,17,19,128,128);
gpu_submit(&setup);
gpu_submit(&draw);
gpu_wait();
```

Cet exemple échange les axes et inverse l'un d'eux. Il suppose que la source
est publiée par `gpu_publish_surface()` et que la capacité a été vérifiée
par `gpu_affine_supported()`. Pour relire les pixels au CPU, attendre la
fin puis invalider son cache. Pour afficher sans déchirure, dessiner dans
la page arrière et valider sa couche au retour vertical.

## Démonstration et contrôles

- `I` prépare quatre poses, compare chaque pixel et 64 octets de garde à
  une référence CPU indépendante, puis vérifie l'empreinte LCD composée.
- `Z` affiche six images transformées : deux tournent, les quatre autres
  montrent des transformations fixes (zoom X/Y, retournement et cisaillement).
  Deux pages DDR alternent et le texte utilise une couche séparée.
  Un bilan est émis toutes les 240 images.
  Le champ `gpu_cycles` des poses et `gpu_avg`/`gpu_max` du bilan incluent
  la préparation des commandes, leur soumission et l'attente de fin ;
  ils mesurent le budget de dessin vu par le CPU, en cycles à 800 MHz.
- `Q` arrête cette animation. `?`, `S`, `E`, `M` restent disponibles pendant
  l'animation ; les autres démonstrations arrêtent et invalident cette scène.
- `python3 tools/render_gpu_affine.py --pose 0` produit l'image attendue.
  Les poses vont de 0 à 3. `--hardware-log` compare aussi les empreintes.

Les commandes et l'image source de la référence hôte sont celles du firmware.
L'échantillonnage Python est indépendant du RTL et du rasteriseur de référence
CPU. Les calculs C de préparation de scène sont contrôlés avec UBSan sur
les 256 positions angulaires.
