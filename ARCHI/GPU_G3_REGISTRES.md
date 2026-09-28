# G3 — composition de 16 couches en DDR3

G3 étend le lecteur `0xE9000000` et conserve le framebuffer G1 ainsi que
le [blitter G2](GPU_G2_REGISTRES.md). Le cœur reste à 800 MHz, le bus AHB
à 80 MHz, le lecteur DDR3 à 75 MHz et le LCD à 35 MHz (800×480, environ 55 Hz).

Les 16 couches sont des surfaces indexées sur 8 bits, composées dans l'ordre
de la table : 0 au fond, 15 devant. Chaque couche possède sa position signée,
sa fenêtre visible, son origine de lecture et son pas de ligne. Le lecteur
découpe les surfaces aux limites de l'écran et de leur mémoire source.
L'index zéro peut laisser voir les couches inférieures. La palette globale
contient 256 couleurs RGB666. Il n'y a pas encore de mélange alpha, de
rotation, de zoom ni de répétition automatique des surfaces.

## Registres ajoutés

Les offsets suivants s'ajoutent aux registres G1. L'identifiant reste `GPU1`
(`0x47505531`) ; le registre de capacité identifie l'extension.

| Offset | Accès | Signification |
|---|---|---|
| `0x028` | R | Nombre de couches matérielles : 16 |
| `0x02c` | R | Maximum des cycles DDR nécessaires à une ligne depuis le reset |
| `0x030` | R/W | Mode demandé : 0 framebuffer G1, 1 couches |
| `0x034` | R | Mode effectivement appliqué |
| `0x038` | R | Nombre de couches rejetées pour adresse/pas invalide, cumulé par ligne |
| `0x800..0x9ff` | W | Banque inactive de 16 descripteurs de 32 octets |

Le registre `0x00c` conserve son rôle de commit/BUSY. Le commit capture le
mode, l'activation, la base G1 et la banque de descripteurs. Il devient effectif
au début de la zone verticale invisible, après achèvement du travail mémoire
précédent. Les écritures de la table et du commit attendent tant que BUSY vaut 1.
La banque suivante doit être **entièrement réécrite** : elle n'hérite pas des
modifications de la table active. Le pilote `gpu_layers_submit` assure cette
écriture des 16 entrées ; `gpu_display_wait` attend l'application du commit.

La palette à `0x400..0x7ff` reste globale et directement modifiable : elle ne
participe pas au changement atomique des descripteurs. Pour remplacer toute
la palette sans changement visible intermédiaire, désactiver l'affichage.

## Descripteur d'une couche

| Mot | Bits | Contenu |
|---|---|---|
| 0 | 31:0 | Adresse en octets du premier pixel source |
| 1 | 31:16 / 15:0 | Hauteur / largeur de la surface source |
| 2 | 31:16 / 15:0 | Position Y / X signée sur 16 bits |
| 3 | 31:16 / 15:0 | Hauteur / largeur de la fenêtre visible |
| 4 | 31:16 / 15:0 | Origine source Y / X non signée (défilement) |
| 5 | 15:0 | Pas de ligne en octets, au moins la largeur source |
| 6 | 0 / 1 | Activation / transparence de l'index zéro |
| 7 | — | Réservé, écrire zéro |

Une adresse ou un pas non multiple de 32 est accepté. Les octets visibles
doivent rester dans le premier Gio de DDR3. Les lectures natives portent sur
des blocs alignés de 32 octets : réserver aussi les octets de bord de ces blocs.
Une fenêtre vide, hors écran ou hors surface est ignorée. Les dimensions sont
sur 16 bits ; le pilote doit fournir des valeurs représentables.

Les données CPU doivent être publiées avant le commit avec
`gpu_publish_surface`. Les surfaces actives ne sont pas copiées : les modifier
pendant leur lecture peut produire une déchirure. Pour animer, préparer une
autre surface puis changer le descripteur au commit.

## Vérification et coût mémoire

Le compositeur lit une ligne de chaque couche visible, fusionne 32 pixels par
cycle et transmet la ligne complète à deux tampons d'affichage alternés.
Les requêtes DDR sont limitées à seize lectures simultanées. Même les pixels
transparents consomment des lectures ; limiter les fenêtres réduit ce coût.
Seize surfaces couvrant tout l'écran représentent 6 144 000 octets lus par
trame, soit environ 338 Mo/s à 55 Hz, hors alignement et autres clients DDR.
Le débit disponible et le délai maximal d'une ligne limitent les scènes.
Sur la démonstration validée, le maximum mesuré avec les accès CPU concurrents
est de 2 477 cycles sur environ 2 556 disponibles par ligne. Cette marge est
étroite au maximum de charge : surveiller les compteurs lors de l'ajout de
clients mémoire ou de nouveaux effets, et réduire les fenêtres inutiles.

En mode couches, `0x020` fournit une empreinte ordonnée des pixels composés.
Pour chaque bloc de 32 octets, interpréter les huit mots comme little-endian,
effectuer le XOR de chaque mot tourné à gauche de `4 * index`, puis calculer
`hash = rol32(hash, 5) XOR bloc`, en parcourant l'image ligne par ligne.
L'empreinte commence à zéro et est publiée après la dernière ligne.
En mode G1, ce registre conserve la somme des mots 32 bits.

Le diagnostic `L` prépare 16 surfaces numérotées, vérifie trois configurations
par comparaison CPU/GPU et affiche la première. `P` passe à la configuration
suivante. `V` revient à la démonstration framebuffer et `B` à celle du blitter.
Le rapport de validation est dans [TESTS_GPU_G3.md](../TESTS/TESTS_GPU_G3.md).
