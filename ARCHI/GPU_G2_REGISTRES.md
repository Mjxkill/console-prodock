# G2 — dessin 2D en DDR3

Le lecteur d'affichage G1 reste à `0xE9000000`. L'accélérateur G2 est à
`0xE9001000`, sur le même bus AHB 80 MHz. Rasteriseur, DMA et arbitre DDR3
fonctionnent à 75 MHz. Le cœur AE350 reste à 800 MHz.

## Registres, accès 32 bits

| Offset | Lecture | Écriture |
|---|---|---|
| `00` | `424C5432` (`BLT2`) | — |
| `04` | bit 0 occupé, bit 1 FIFO AHB pleine | — |
| `08` | commandes terminées, compteur 16 bits | — |
| `0C` | commandes inconnues en 31:16, mots perdus en 15:0 | — |
| `10` | 0 | prochain mot de commande |
| `14` | adresse de police 12 bits | adresse de police |
| `18` | 0 | octet de police, adresse incrémentée |
| `1C` | mots perdus dans la FIFO entre horloges | — |

La FIFO AHB contient 128 mots, suivie de la FIFO du rasteriseur de
16 commandes. Une écriture à `CMD` attend lorsque la FIFO AHB est pleine.
Les mots d'une commande doivent venir d'un seul producteur, sans mélange
avec ceux d'une autre commande. Chaque commande contient **huit mots** :

| Mot | Contenu |
|---|---|
| 0 | opcode 31:24, page destination 23:20, page source 19:16, couleur 15:8, couleur 2 7:0 |
| 1 | x signé 16 bits, y signé 16 bits |
| 2 | largeur / x final / rayon / nombre de caractères, hauteur / y final / échelle |
| 3 | x source signé 16 bits, y source signé 16 bits |
| 4–7 | texte : 16 octets, premier caractère dans les bits 7:0 du mot 4 ; zéro sinon |

| Opcode | Primitive |
|---|---|
| 1 | Rectangle plein ; un pixel est un rectangle 1×1 |
| 2, 3, 4 | Dégradé d'indices horizontal, vertical, diagonal |
| 5 | Ligne, extrémités incluses |
| 6, 7 | Cercle / disque, rayon positif ou nul |
| 8 | Copie de rectangle, dimensions dans le mot 2 |
| 9 | Texte, 0 à 16 caractères, échelle 1 ou 2 |

Les pages ont 800×480 octets indexés. Page `p` :
`0x00800000 + p × 0x00100000`, `p` de 0 à 15, pas de ligne 800 octets.
Ces **16 emplacements mémoire sont distincts des 16 couches** de
[G3](GPU_G3_REGISTRES.md) : chaque couche peut référencer une surface DDR.
Les pages 0 et 1 servent aux échanges d'affichage du diagnostic, la page 2
à sa référence CPU et la page 3 aux pixels source de ses copies.

Les primitives sont découpées aux limites de la surface. Les rectangles
de largeur/hauteur non positive et les cercles de rayon négatif ne dessinent
rien. Une copie est aussi découpée aux limites de la source ; les pixels
sans source valide restent inchangés. Les copies entre zones superposées
d'une même page suivent la sémantique `memmove`, verticalement et horizontalement.

Le dégradé utilise le pas entier `floor(65536/n)`, `n=largeur−1`,
`hauteur−1` ou `largeur+hauteur−2`. Une dimension de gradient réduite à un
pixel prend la couleur initiale. Le texte utilise 256 glyphes 8×16,
bit 7 à gauche ; couleur 2 nulle = fond transparent, sinon fond opaque.
Le fond opaque d'index 0 n'est pas un mode distinct dans cette interface.

## Ordre et cohérence

Le compteur `DONE` est la barrière logicielle : mémoriser sa valeur initiale,
ajouter le nombre de commandes envoyées modulo 65536, attendre cette valeur.
`BUSY` traverse les horloges et peut rester nul juste après l'envoi ; il ne
remplace pas cette attente. Les commandes invalides terminent aussi et
incrémentent le compteur d'erreurs.

Avant de donner une surface modifiée par le CPU au GPU, utiliser
`gpu_publish_surface` : vidage/invalidation du cache, barrière, relecture
du dernier octet en DDR3 et barrière. La relecture vide le chemin des écritures
CPU différées avant que le GPU puisse lire la surface.
Après `DONE`, invalider les lignes de cache d'une surface écrite par le GPU
avant de la lire sur CPU. Ne pas laisser de lignes sales CPU sur cette
surface pendant le dessin. Attendre les commandes de texte avant de modifier
la police. Le pilote `fw_console/gpu.h` expose commandes, attente, texte par
blocs de 16 caractères, écriture de police et publication des surfaces.
L'application choisit explicitement les surfaces à publier et à invalider.

Les écritures sont regroupées en rafales natives de 32 octets, avec masques
par octet. Les pixels isolés utilisent une rafale masquée. Les lectures ont
des étiquettes CPU/affichage/blitter pour retourner chaque réponse au client
demandeur. L'affichage a priorité, CPU et blitter alternent les occasions
d'accès restantes. Un compteur de débordements d'affichage doit rester nul.

La commande USB `B` dessine une démonstration en page 1, compare les 384000
pixels et 64 octets de garde avec une image calculée sur CPU, puis échange
la page au retour vertical. `V`, `F`, `S`, `M`, `D`, `E`, `?` conservent
leurs fonctions de diagnostic G0/G1. `D` est destructif : lancer avant `V`.
