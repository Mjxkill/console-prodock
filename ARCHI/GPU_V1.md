# GPU V1 — finition des sept points

État au 4 octobre 2026 : **les sept points sont réalisés et validés dans
`gpu_v1_r31`**. Simulations, timing, deux rechargements SRAM, USB HS, suite
graphique complète et endurance de 30 minutes passent sur la Pro Dock.
Les trois scènes sont confirmées visuellement par l'utilisateur.
[Image SRAM archivée](../bitstreams/console_gpu_v1_800.md) et
[preuves de qualification](../TESTS/TESTS_GPU_V1.md).

## 1. Périmètre

Cette livraison termine le périmètre vidéo proposé dans la section 3.2 de la
[feuille de route](FEUILLE_DE_ROUTE_CONSOLE.md). Les jeux d'aventure, de FPS et
de course sont les usages visés ; les trois scènes de qualification sont des
charges graphiques représentatives, pas des jeux achevés.

| Point | Réalisation |
|---|---|
| 1. Cibles | Cibles couleur RGB565 et profondeur Z16, dimensions 1…1024 × 1…512, pas indépendants, scissor, viewport logiciel, effacement partiel. |
| 2. Textures | Textures DDR jusqu'à 512 × 512, cache physique de 2 Kio, réutilisation entre dessins et niveaux de mipmap, compteurs de succès/défauts. |
| 3. API 2D RGB565 | Rectangles, texte à atlas ARGB4444, copies DDR avec recouvrement, images/zoom/rotation par quadrilatères réutilisant les triangles. Les primitives indexées existantes sont conservées. |
| 4. Matériaux | Alpha par texel × alpha global, mélange additif saturé, modulation RGB et gains de Gouraud. |
| 5. Distance | Brouillard linéaire selon Z, mipmaps précalculées, choix explicite du niveau. |
| 6. Résolution | 400 × 240 agrandi ×2 au LCD 800 × 480 ; couches/sprites/HUD indexés restent en résolution native. |
| 7. Livraison | ABI documentée, pilote, convertisseur de ressources, références indépendantes, trois scènes, mesures de charge, qualification matérielle et endurance. |

Ce périmètre n'inclut pas l'alpha dans le compositeur des 16 couches, le
filtrage bilinéaire, la transformation des sommets en DSP ni les shaders
programmables. Les transparences évoluées sont dessinées dans la cible RGB565.

## 2. Architecture et compatibilité

Le FIFO de commandes AHB → DDR reste à deux horloges, à producteur unique,
avec huit mots par commande. Les opcodes 1…13 restent dans `blitter.v` et
`gpu_blit_dma.v`, les opcodes 14…21 dans `gpu_raster.v`. Les opcodes 22…30 sont
routés vers `gpu_v1.v` par la même file ordonnée. Il n'existe pas de second
producteur concurrent ni d'accès DDR graphique qui contourne l'arbitre.

Le chemin V1 enregistre une transaction DDR complète (adresse, données,
masque, lecture/écriture), la maintient jusqu'à acceptation, puis renvoie
un acquittement enregistré. Une garde empêche de capturer deux fois la même
demande. Les données et la validité du retour sont également enregistrées
avant le shader et ses caches. Ces registres appartiennent au domaine mémoire ;
le passage AHB/mémoire reste assuré par le FIFO à deux horloges existant.
Les transactions DDR des anciens opcodes conservent leurs cycles. VALID et
WRITE utilisent les demandes enregistrées des moteurs, mutuellement exclusifs
par la file ordonnée ; le multiplexeur de propriétaire reste sur les données
et les retours de lecture. Le contrôle ne traverse plus ce multiplexeur large
puis l'arbitre avant de revenir aux états des moteurs. Cette modification est
comparée au parent complet de référence à chaque cycle AHB et DDR.
La qualification r13 compare aussi tous ses modules vidéo enfants à leur
instantané précédent. Le rasteriseur historique prédécode les mots durant
le cycle déjà disponible avant START : le blitter doit donc terminer la
commande au moins un cycle avant START et la maintenir jusqu'à DONE. Cette
condition interne est vérifiée dans le banc d'équivalence ; l'ABI MMIO reste
inchangée.

Le nouveau moteur réutilise `gpu_triangle.v` pour les spans selon la règle
top-left et deux instances de `gpu_perspective.v` pour les divisions exactes
floor(UQ/Q), floor(VQ/Q), anticipées sur deux pixels. Il ajoute :

- `gpu_texture_cache.v` : cache DDR en lecture, 64 lignes de 32 octets ;
- `gpu_copy565.v` : copie par blocs DDR, alignement de demi-mots et memmove ;
- calculs par pixel : profondeur, échantillonnage, alpha, gain, brouillard,
  mélange et écriture masquée des couleurs/profondeurs.

Les validations de descripteurs produisent des prédicats enregistrés avant
leur application. Le chemin texture sépare la sélection des coordonnées, le
décalage de mipmap, leur limitation, la multiplication par le pas et
l'addition de l'adresse. Le découpage des spans et des copies est également
réparti sur plusieurs étapes. Ces registres raccourcissent les chemins
combinatoires ; leur coût est inclus dans les mesures de dessin.

Les fréquences restent AE350 800 MHz, AHB 80 MHz, GPU/DDR UI 75 MHz et LCD
35 MHz. Aucune nouvelle horloge globale. Les contraintes `gpu.sdc` gardent
le SHA-256 `c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.
L'USB reste la variante HS 480 Mbit/s avec les corrections de reprise validées.

## 3. Contrat mémoire

Toutes les adresses de l'ABI V1 sont des **adresses d'octets** dans le premier
Gio de DDR3. Les bases et les pas sont des multiples de 32 octets. Les
couleurs, profondeurs et texels occupent deux octets, en petit-boutiste.
Le pas doit couvrir la largeur utile ; le padding appartient à l'application.

Une cible lie simultanément une couleur et un Z16. Leurs plages allouées,
calculées sur `pas × hauteur`, doivent être disjointes. Le Z est obligatoire
dans la description, même lorsque le matériau ne le lit ni ne l'écrit.
Une texture ne peut recouvrir la cible couleur ; le recouvrement du Z est
également refusé lorsque le matériau accède à la profondeur.

Publication CPU : terminer les dessins précédents, écrire la ressource,
`gpu_publish_surface(adresse, octets)`, puis soumettre
`gpu_v1_invalidate(&contexte)` avant le premier dessin qui doit la relire.
Changer de texture ne force pas le vidage du cache. La commande d'invalidation
est ordonnée avec les dessins. Il n'y a pas de cohérence automatique avec
les caches CPU ni de surveillance des écritures CPU.

Une texture produite par le GPU suit aussi cette règle d'invalidation : terminer
le dessin, lier une autre cible disjointe, puis invalider le cache avant de
relire l'ancienne cible comme texture. Une liaison seule ne vide pas le cache.
Ne pas vider un cache CPU contenant une vieille copie sale par-dessus une
surface fraîchement écrite par le GPU.

Lecture CPU : `gpu_wait()` puis `ae350_dcache_invalidate_range()` avant de
consulter une surface produite par le GPU. La présentation reste double
tampon ; ne pas dessiner dans la surface actuellement affichée.

## 4. Registres

Base accélérateur `0xe9001000`. Les anciens registres, y compris leurs bits
de capacités et compteurs, sont inchangés.

| Offset | Lecture V1 |
|---|---|
| `0x30` | Capacités ABI V1 : `0x000001ff`. |
| `0x34` | Nombre cumulatif de commandes V1 refusées. |
| `0x38` | Fragments visités par le rasteriseur V1. |
| `0x3c` | Fragments effectivement écrits par le shader. Effacements/copies exclus. |
| `0x40` | Succès du cache de textures. |
| `0x44` | Défauts du cache, chacun chargeant une ligne de 32 octets. |

Les compteurs sont transférés par `cdc_word` ; leur publication peut suivre
la clôture de la commande de quelques cycles. `DONE` 16 bits reste la clôture
commune à tous les opcodes, à traiter modulo 65536. Une commande invalide se
termine, incrémente le compteur de refus et n'écrit pas la DDR.

Base affichage `0xe9000000` :

| Offset | Extension |
|---|---|
| `0x08` | bit 0 activation, bit 1 RGB565, bit 2 agrandissement ×2 ; bit 2 ignoré hors RGB565. |
| `0x68` | Capacités : bit 0 overlays RGB565, bit 1 ×2, bit 2 pas RGB565. |
| `0x6c` | Pas RGB565 en octets sur 16 bits, multiple de 32. Zéro sélectionne le pas usuel : 1600 en natif, 800 en ×2. |

Format, base, pas, agrandissement et tables de composition sont engagés
ensemble au vblank par `0x0c`. Le pas personnalisé n'affecte pas le retour au
mode indexé. Le pilote `gpu_rgb565_surface_submit` vérifie que les dimensions
sont exactement 800 × 480 ou 400 × 240 et que la plage tient dans le premier Gio.
Comme pour les anciens registres d'affichage, les écritures MMIO brutes
incohérentes ne constituent pas une API de présentation valide.

Le calcul d'adresse des lignes à pas variable utilise un pointeur incrémental
dans le domaine pixel. Il ne multiplie pas une valeur de mailbox AHB par un
compteur pixel dans un DSP. Le contrôle de synthèse existant reste obligatoire.
Chaque ligne LCD lit 50 blocs en natif, 25 blocs en ×2 ; la ligne source est
relue pour les deux lignes LCD. La composition des overlays utilise toujours
les coordonnées natives du LCD et son bit de couverture par pixel.

## 5. Commandes binaires, ABI 1

Chaque commande contient `w0…w7`. L'opcode est `w0[31:24]` ; les autres bits
de `w0` sont nuls, sauf l'index du plan pour l'opcode 26. Tout mot réservé
doit être nul. `XY(x,y)` place x dans les 16 bits forts et y dans les faibles.
Les sommets et origines de rectangles/copies sont signés sur 16 bits.
Les dimensions sont non signées.

| Opcode | Contenu |
|---|---|
| 22 TARGET | w1 couleur, w2 Z, w3 XY(largeur,hauteur), w4 XY(pas couleur,pas Z), w5…7=0. Remet le scissor à toute la cible. |
| 23 SCISSOR | w1 XY(gauche,haut), w2 XY(droite exclusive,bas exclusif), w3…7=0. Bornes dans la cible ; région vide autorisée. |
| 24 TEXTURE | w1 base du niveau choisi, w2 XY(largeur,hauteur), w3 pas[15:0] et format[16], w4 modes U[1:0], V[3:2], LOD[7:4], w5…7=0. |
| 25 MATERIAL | w1 flags, w2 alpha global, w3 couleur solide, w4 gains R[8:0]/G[17:9]/B[26:18], w5 Z début brouillard[31:16] et couleur brouillard[15:0], w6 pente Q16, w7=0. |
| 26 PLANE | w0[2:0] index 0…6, w1 origine faible32, w2 dx signé32, w3 dy signé32, w4 origine forte16, w5…7=0. |
| 27 TRIANGLE | w1, w2, w3 les trois XY ; w4…7=0. |
| 28 CLEAR | w1 bits couleur=1/Z=2, w2 couleur, w3 Z, w4 XY(x,y), w5 XY(largeur,hauteur), w6…7=0. |
| 29 COPY | w1 base source, w2 XY(dimensions source), w3 pas source, w4 XY(source x,y), w5 XY(destination x,y), w6 XY(largeur,hauteur), w7=0. |
| 30 INVALIDATE | w1…7=0 ; invalide les 64 lignes de cache sans effacer les compteurs. |

Une description TARGET/MATERIAL/TEXTURE invalide invalide l'état concerné.
Un plan invalide invalide son index lorsqu'il est dans 0…6. Les dessins qui
en dépendent sont refusés. Le reset invalide ces états et le cache.

### Plans et coordonnées

Les indices 0…6 représentent U, V, Q, Z, gain R, gain G, gain B. L'origine
est signée sur 48 bits, les gradients sur 32 ; l'évaluation est signée sur
49 bits. Le pilote extrapole à (0,0) et tient compte du centre des pixels.

Sans perspective : U/V sont en Q16.16, échantillonnés par floor(valeur/65536).
Avec perspective : les plans sont UQ/VQ/Q et l'échantillon est leur quotient
entier arrondi vers moins l'infini ; Q≤0 rejette le fragment. Le LOD divise
ensuite les coordonnées par 2^LOD, toujours avec floor. Les coordonnées de
sommets restent exprimées en texels du niveau de base.

Z utilise Q16.16. Une profondeur hors 0…65535 est rejetée lorsque Z ou
brouillard sont actifs. Le test est strictement LESS, profondeur égale refusée.
Les gains Gouraud sont Q16.16 puis bornés à 0…256. Le pilote de haut niveau
accepte des coordonnées de sommet signées16, UV entiers signés16, Z 0…65535,
Q 0…`0xffffff` et gains 0…256 ; ces bornes évitent les débordements du calcul
64 bits de plans. L'ABI brute des plans conserve sa précision décrite ci-dessus.

Modes d'adresse U/V : 0 rejette l'échantillon hors texture, 1 répète une
dimension obligatoirement puissance de deux, 2 borne au bord. Dimensions de
texture 1…512. Format 0 RGB565 opaque, format 1 ARGB4444, bits A/R/G/B de
poids fort à faible. Le filtrage reste au plus proche voisin.

### Matériau, ordre et arrondis

Flags : texture=1, test Z=2, écriture Z=4, clé zéro=8, perspective=16,
additif=32, Gouraud=64, brouillard=128. Perspective exige texture.

1. Profondeur et validité des coordonnées déterminent la visibilité.
2. Lecture du texel, ou couleur solide. Clé zéro examine le mot entier.
3. ARGB4444 : R/B 4→5 bits et G 4→6 bits par répétition des bits hauts.
   Alpha A=15 devient 256 ; sinon A×17. RGB565/solide donne 256.
4. Alpha effectif = `(alpha_global × alpha_texel + 128) >> 8`.
5. Chaque canal est modulé par `(canal × gain + 128) >> 8`. Gains uniformes
   0…256, remplacés par les gains interpolés lorsque Gouraud est actif.
6. Brouillard : `f = clamp((Z - début) × pente_Q16 >> 16, 0, 256)` ; pente
   0…`0x01000000`. La couleur devient `(couleur × (256-f) + brouillard × f + 128) >> 8`.
7. Mélange normal : `(source × alpha + destination × (256-alpha) + 128) >> 8`.
   Additif : `min(max_canal, (source × alpha + destination × 256 + 128) >> 8)`.
8. Alpha effectif nul n'écrit ni couleur ni profondeur. Sinon Z est écrit
   uniquement si le flag d'écriture est actif, même pour un pixel translucide.

Pour des objets translucides, dessiner généralement les opaques d'abord,
puis les transparents triés du fond vers l'avant, avec test Z mais sans
écriture Z. Le GPU n'effectue pas ce tri automatiquement.

### Copies et effacements

L'effacement est une écriture DDR masquée, sans lecture de destination.
Il s'applique au scissor et peut traiter couleur, profondeur ou les deux.
La copie est RGB565 vers RGB565, sans mélange. Le découpage tient compte du
scissor destination **et** des dimensions source. Le Z destination est conservé.

Un recouvrement est permis avec la même base et le même pas ; le parcours
s'inverse si nécessaire, assurant une sémantique memmove. Des descriptions
partiellement superposées avec bases ou pas différents sont refusées.
Chaque fragment de ligne est lu entièrement, éventuellement sur deux blocs,
avant son écriture masquée. La fin d'une copie invalide le cache texture.

## 6. Pilote et ressources

`fw_console/gpu_v1.h` / `.c` exposent un contexte avec un callback d'émission.
Sur carte : `gpu_v1_init(&ctx, gpu_submit)`. Sur hôte, le même préparateur de
scène émet des commandes vers un fichier, traité par une référence Python
indépendante du RTL. Un contexte ne rend pas la file multiproducteur : la
sérialisation reste à la charge du programme.

Le viewport est une transformation logicielle du rectangle de projection ;
`gpu_v1_project` convertit des coordonnées NDC Q16 dans ce rectangle. Le
scissor est une commande matérielle distincte. Les transformations caméra,
le découpage des polygones et la sélection du LOD restent du côté CPU.

`gpu_v1_text` construit des quadrilatères à partir d'un atlas ARGB4444 de
128 × 256, organisé en 16 colonnes de glyphes 8 × 16. `gpu_v1_font` convertit
la police de 4096 octets. Couleur, alpha et échelle 1…16 sont configurables.
Texte et images modifient le matériau, la texture et les plans courants :
relier le matériau suivant avant d'autres dessins. `gpu_v1_quad` réutilise
le moteur de triangles ; fournir les quatre coins transformés réalise le
zoom, la rotation et les images affines.

### Exemple de présentation

Après initialisation du GPU et publication de l'atlas de police, une image
RGB565 réduite peut être présentée ainsi. `page` doit être le tampon arrière,
`atlas` l'adresse d'un atlas ARGB4444 128 × 256 disjoint des cibles. Les tables
`layers` et `sprites` décrivent les superpositions dans les coordonnées natives
800 × 480 ; leurs images doivent déjà être publiées en DDR.

```c
#include "gpu_v1.h"

int dessiner_image(unsigned page, uint32_t atlas,
                   const gpu_layer layers[16],
                   const gpu_sprite sprites[64])
{
    gpu_v1_context ctx;
    gpu_v1_init(&ctx, gpu_submit);
    gpu_target cible = {
        GPU_PAGE_ADDR(page), GPU_PAGE_ADDR(2), 400, 240, 832, 832
    };
    if (!gpu_v1_target(&ctx, &cible) ||
        !gpu_v1_clear(&ctx, 3, 0x0841, 65535, 0, 0, 400, 240) ||
        !gpu_v1_text(&ctx, atlas, 16, 24, 0xffff, 256, 1, "Bonjour"))
        return 0;
    if (!gpu_wait()) return 0;
    return gpu_rgb565_surface_submit(&cible, 1, layers, sprites) &&
           gpu_display_wait();
}
```

Utiliser alternativement les pages 0 et 1 pour `page`, la page 2 restant le Z.
Après modification de l'atlas, attendre la fin des dessins précédents, publier
les nouvelles données, puis émettre `gpu_v1_invalidate` avant cet exemple.
La bibliothèque ne réserve pas les pages à la place du runtime : l'application
garde la responsabilité de leur allocation et de leur durée de vie.

### Format `.gtex`

```
python3 tools/gpu_assets.py image.png ressources/image.gtex --format argb4444
```

Le convertisseur produit le conteneur binaire et son manifeste JSON avec
SHA-256, dimensions, offsets et pas. Les mipmaps sont générées jusqu'à 1 × 1,
sauf `--no-mipmaps`. Le filtre de boîte 2 × 2 utilise une couleur prémultipliée
par alpha puis stocke une couleur droite ; un pixel invisible ne colore
pas les voisins visibles. Les dimensions impaires utilisent les pixels
réellement présents au bord et sont arrondies au supérieur au niveau suivant.

En-tête petit-boutiste de huit u32 : magic `0x31545647` (« GVT1 »), ABI=1,
format, nombre de niveaux 1…10, largeur de base, hauteur de base, taille
complète en octets, réservé=0. Il est suivi de quatre u32 par niveau : offset
aligné32, XY(largeur,hauteur), pas aligné32, LOD. Les données commencent après
la table arrondie à 32 octets. Le LOD est explicite ; pas de calcul de dérivées
ni de transition trilinéaire dans le shader.

`gpu_v1_asset_level` valide le conteneur et prépare le descripteur du niveau
souhaité. Le fichier est chargé dans une région DDR alignée32, publié puis
invalidé côté cache texture avant son utilisation. Le manifeste documente
les ressources ; aucun chargeur USB de jeux n'est ajouté dans ce lot vidéo.

## 7. Démonstrations et mesures

`f` commence par un test mémoire de 2 496 octets, gardes et padding compris :
changement de cible Z d'une page supérieure à une page inférieure, copie
entre pages avec décalage de demi-mots, effacement Z partiel. Il utilise les
pages 4…6 et exige le marqueur `V1 MEMORY PASS` avant les scènes.
Il vérifie ensuite trois scènes × quatre positions : empreintes FNV-1a couleur et Z,
y compris padding et 64 octets de garde, puis somme des pixels RGB666 du LCD.
`g` anime les trois scènes à tour de rôle, 120 images chacune ; `c` met en pause.
Les commandes historiques restent disponibles.

Le mode des scènes est 400 × 240, pas 832, agrandissement ×2. Le HUD natif est
une couche indexée 800 × 20. Les images source et leurs mipmaps occupent la
page 15, l'alpha 64 × 64 est à l'offset `0xb0000`, la police à `0xc0000`.
Les pages 0/1 sont les tampons couleur, la page 2 le Z, la page 9 le HUD.

Charge de la pose 0 (texte et effets compris) :

| Scène | Commandes de dessin/configuration | Triangles | Fragments écrits par le shader |
|---|---:|---:|---:|
| [Aventure : image attendue](../TESTS/gpu_v1_20261004/scene0_expected.png) | 273 | 70 | 55 780 |
| [Couloir FPS : image attendue](../TESTS/gpu_v1_20261004/scene1_expected.png) | 98 | 20 | 80 770 |
| [Route : image attendue](../TESTS/gpu_v1_20261004/scene2_expected.png) | 90 | 28 | 38 206 |

Chaque scène comporte aussi une copie RGB565 ; les effacements et copies
ne sont pas comptés dans les fragments du shader. Le banc hôte ajoute une
commande d'invalidation préalable, d'où un total de commandes supérieur de
un dans ses journaux. Ces nombres décrivent les poses de qualification,
pas une limite d'objets pour les jeux. Le détail par pose et opcode figure
dans `TESTS/gpu_v1_20261004/scene_workloads.json`.

Les lignes `V1 BENCH` donnent les cycles CPU moyens/maximaux du dessin et de
l'intervalle entre deux présentations, fps×100, accès au cache, maximum de composition par ligne,
sous-alimentations LCD et refus de commandes. La cadence du panneau reste
~55,04 Hz. Une scène peut exiger plusieurs périodes de rafraîchissement ;
les chiffres mesurés, et non le seul taux de cache, déterminent son budget.
Les gardes mémoire sont contrôlées à chaque fenêtre de 120 images. Les échos
USB du diagnostic occupent momentanément la boucle CPU ; leur coût apparaît
dans les intervalles de présentation, tandis que le temps de dessin GPU est
mesuré séparément. `f` mesure aussi le même dessin texturé en 400 × 240 et
800 × 480 pour quantifier le gain du mode réduit.

L'endurance synchronise chaque bloc d'écho avec la boucle de diagnostic :
commande, longueur et premier octet sont envoyés, puis le reste du bloc après
réception du premier écho. Le processeur sonde son UART entre les images ;
cette synchronisation évite de remplir son petit FIFO RX pendant l'attente GPU.
Elle conserve le protocole `E` ; l'affichage continue et la préparation des
images reprend à la fin du bloc. Le transport
USB reste HS, tandis que le pont de diagnostic vers UART2 fonctionne à 115200
bauds. Le chargement rapide de ressources relève du futur protocole L08.

La limite de composition reste environ 2556 cycles DDR par ligne. L'ajout
d'overlays a un coût : 16 couches désigne la capacité de description, pas une
promesse que toutes les combinaisons plein écran plus sprites respecteront
le budget. Les dépassements restent signalés dans le compteur de sous-alimentation.

### Mesures R31 sur Pro Dock

La suite complète du 4 octobre vérifie 12 poses et 720 images animées
(240 par scène). Aucun underflow ni refus ; composition maximale 496/2556
cycles par ligne. Les cycles de diagnostic utilisent le compteur CPU à
800 MHz ; le temps de dessin inclut la préparation, la soumission et
l'attente d'achèvement du GPU.

| Scène | Cadence | Dessin moyen | Dessin maximal | Intervalle maximal de présentation |
|---|---:|---:|---:|---:|
| Aventure | 27,40–27,51 images/s | 19,93 ms | 19,995 ms | 54,504 ms |
| Couloir | 27,40 images/s | 29,60 ms | 30,524 ms | 54,503 ms |
| Route | 54,58 images/s | 13,31 ms | 13,370 ms | 36,336 ms |

Le même dessin de comparaison coûte 28,464 ms en 400 × 240 et 102,228 ms
en 800 × 480, soit un facteur 3,59. Il ne s'agit pas d'une garantie pour
tous les contenus. Les mesures brutes sont dans
[`r31_board_metrics.json`](../TESTS/gpu_v1_20261004/r31_board_metrics.json).
L'endurance dure 1 802,141 s : 58 680 images, soit 19 560 par scène,
191 552 octets d'écho USB exacts, zéro underflow/refus et aucune réénumération.
Dessin maximal 30,534 ms ; composition maximale 504/2556 cycles par ligne.
Les douze poses et le test mémoire passent à nouveau après cette charge.
Le plus grand intervalle de présentation est 381,522 ms pendant un écho de
diagnostic, dont le traitement occupe la boucle CPU à 115200 bauds ; le LCD
continue de rafraîchir. Ce temps est distinct du temps de dessin indiqué
ci-dessus. [Bilan final](../TESTS/gpu_v1_20261004/r31_validation.json).
