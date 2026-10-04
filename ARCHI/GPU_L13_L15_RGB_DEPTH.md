# L13–L15 — alpha RGB565, textures et profondeur

Contrat d'implémentation, 3 octobre 2026. **R3 validé sur carte et visuellement**,
avec correction des origines de plans et de la boucle d'animation ;
[résultats, mesures et limites](../TESTS/TESTS_GPU_L13_L15.md).

Cette fiche décrit le jalon r3. L'extension suivante ajoute la correction de
perspective et les couches indexées sur fond RGB565 : voir
[son contrat et son statut de validation](GPU_PERSPECTIVE_COMPOSITION.md).
Les limites « affine uniquement » et « RGB565 direct sans couches » ci-dessous
concernent le jalon initial.

## Formats et compatibilité

Les commandes indexées 1 à 13 restent inchangées. Le nouveau moteur écrit
des pages **RGB565 little-endian**, 800 × 480, pas de 1600 octets, dans les
mêmes emplacements DDR de 1 Mio (base 0x00800000). Une page de profondeur
distincte contient un entier non signé de 16 bits par pixel au même pas.
Le logiciel choisit le format d'une page ; aucune conversion implicite.

Le mélange alpha se fait dans le moteur de dessin, sur les composantes
R5/G6/B5, et non sur des indices de palette. Alpha uniforme par commande,
de 0 à 256 inclus : `(source*a + fond*(256-a) + 128) >> 8` par composante.
Alpha zéro et texel transparent n'écrivent ni couleur ni profondeur.
Les objets translucides sont dessinés après les opaques, du fond vers
l'avant, avec test Z mais généralement sans écriture Z.

La première version L14 utilise une interpolation affine et le plus proche
voisin. La correction de perspective et le filtrage bilinéaire ne sont pas
annoncés comme implémentés. Textures RGB565, région source 1 à 128 pixels
par axe, capturée dans un cache avant le dessin. Noir zéro est transparent
uniquement si KEY_ZERO est activé. Modes d'adressage par axe : rejet hors
texture, répétition (dimension puissance de deux), clamp aux bords.

La profondeur est interpolée à partir d'un plan en coordonnées écran.
Test strict `nouvelle < ancienne` ; égalité rejetée. 65535 sert de fond
lointain. Le choix de projection doit fournir une profondeur cohérente
(par exemple profondeur normalisée après projection). L'initialisation
de la couleur et de la profondeur est accélérée par rafales DDR de 32 octets.

## Commandes (huit mots chacune)

Le mot 0 vaut `opcode << 24` ; ses autres bits et tous les mots non décrits
sont réservés à zéro. Les commandes, y compris les configurations, restent
ordonnées dans la FIFO existante et incrémentent DONE après achèvement.

| Opcode | Fonction | Mots 1 à 7 |
|---|---|---|
| 14 | RASTER_STATE | w1=page couleur bits3:0, page Z bits7:4 ; w2=flags ; w3=alpha 0..256 ; w4=couleur RGB565 |
| 15 | TEXTURE | w1=page source ; w2={x,y} ; w3={largeur,hauteur} ; w4=modes U bits1:0 / V bits3:2 |
| 16 | PLANE_U | w1=origine basse ; w2=dU/dx Q16.16 signé ; w3=dU/dy ; w4=format/extension ci-dessous |
| 17 | PLANE_V | même format |
| 18 | PLANE_Z | même format étendu ; format initial w4=0 : w1 Q16.16 non signé |
| 19 | RASTER_TRIANGLE | w1={x0,y0}, w2={x1,y1}, w3={x2,y2}, coordonnées signées 16 bits |
| 20 | RASTER_CLEAR | w1=bit0 couleur / bit1 profondeur ; w2=RGB565 ; w3=profondeur |

Flags : TEXTURE=1, Z_TEST=2, Z_WRITE=4, KEY_ZERO=8.
Modes de texture : 0=rejet, 1=répétition, 2=clamp ; 3=invalide.
Les plans évaluent `origine + x*dx + y*dy` au pixel entier `(x,y)`.
Depuis r3, **w4[16]=1** sélectionne une origine signée de **48 bits**
Q32.16 : concaténation `{w4[15:0],w1}`. Les bits 31:17 restent à zéro.
L'origine extrapolée à (0,0) peut être négative ou dépasser 65535, même si
les profondeurs sur le triangle sont toutes valides. Elle n'est donc jamais
limitée à la plage du Z16 stocké. Les dérivées restent signées sur 32 bits.
Les accumulateurs de 49 bits conservent un bit de garde pour les deux
produits écran. Seul le résultat interpolé au pixel est limité à 0..65535.

Le format **w4=0** reste accepté : origine U/V signée sur 32 bits et
origine Z non signée sur 32 bits. Toute autre combinaison sans bit 16 est
refusée. Les triangles gardent leur mot 4 réservé à zéro. Le constructeur
C `gpu_make_plane` utilise le format étendu, avec une origine `int64_t`
bornée à la plage signée de 48 bits ; il exige le moteur r3 ou ultérieur.

Le préparateur logiciel inclut le décalage du centre du pixel dans l'origine.
La couverture est celle de G5 : centres des pixels et règle haut/gauche.
Les accumulateurs élargis empêchent les débordements aux coordonnées découpées.

Un état invalide est invalidé explicitement. Une commande refusée termine
sans écriture et incrémente le compteur de refus du moteur, accessible
séparément du compteur historique d'opcodes inconnus. Les réglages ne
survivent pas au reset. Les pages couleur et Z doivent être distinctes.

## Registres et pilote

Les nouveaux registres du bloc d'accélération sont accessibles sur AHB :

| Adresse | Lecture |
|---|---|
| `0xe9001020` | Capacités : bit0 affine indexé, bit1 alpha RGB565, bit2 texture, bit3 Z16 ; valeur actuelle `0x0f` |
| `0xe9001024` | Nombre de commandes refusées par le moteur RGB565 |
| `0xe9001028` | Nombre de fragments couverts examinés |
| `0xe900102c` | Nombre de fragments écrits après texture, transparence et test Z |

Les compteurs sont transférés par poignée de main, avec un délai de quelques
cycles. Les commandes nouvelles utilisent les mêmes soumissions et la même
barrière `gpu_wait()` que les commandes historiques. `gpu_errors()` inclut
les refus du moteur. Le pilote expose les constructeurs
`gpu_make_raster_state`, `gpu_make_texture`, `gpu_make_plane`,
`gpu_make_raster_clear`, et `gpu_rgb565_present` pour présenter une page.

## Affichage

Le bit 1 du registre d'activation 0xe9000008 sélectionne le framebuffer
RGB565 (bit 0 = activation). Le format, l'adresse et l'activation sont
appliqués ensemble au retour vertical. Le mode RGB565 direct est utilisé
avec la composition indexée désactivée ; le mode historique conserve
les 16 couches, sprites et tilemaps. Ce lot ne transforme pas le compositeur
indexé en mélangeur alpha de 16 couches.

## Preuves requises

- Comparaison indépendante de tous les pixels couleur et Z, gardes incluses.
- Alpha 0, 1, intermédiaire, 255, 256 et extrêmes RGB.
- Textures non carrées, retournées par plans négatifs, bords et transparence.
- Triangles croisés dans les deux ordres, égalités Z, clipping, attentes DDR.
- Retour au rendu indexé sans changer ses pixels ni ses commandes.
- Timing, occupation, tests sur carte et performances mesurées avant livraison.
