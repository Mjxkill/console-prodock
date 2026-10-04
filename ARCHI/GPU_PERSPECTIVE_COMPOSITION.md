# Textures en perspective et composition 2D sur RGB565

3 octobre 2026. Extension de L14 et de l'affichage L13–L15.
Validé en simulation, au timing et par les tests automatiques sur Pro Dock :
**`gpu_perspective_r10`**. La démonstration combinée est laissée en animation.
Les résultats physiques sont consignés dans
[TESTS_GPU_PERSPECTIVE.md](../TESTS/TESTS_GPU_PERSPECTIVE.md).

## Composition de l'image

Le registre d'activation `0xe9000008` conserve ses bits : 0 = activation,
1 = RGB565. Le mode couches `0xe9000030` n'annule plus le bit RGB565.

| RGB565 | Couches | Affichage |
|---:|---:|---|
| 0 | 0 | Framebuffer indexé historique |
| 0 | 1 | Compositeur indexé : 16 couches, sprites et tuiles |
| 1 | 0 | Framebuffer RGB565 direct historique |
| 1 | 1 | Framebuffer RGB565 en fond, compositeur indexé superposé |

Les priorités entre les 16 couches et 64 sprites restent celles de G3/G4.
Le fond RGB565 est derrière toutes ces couches. Il n'occupe aucun des
16 descripteurs. L'adresse du fond, le format et les tables sont appliqués
ensemble au retour vertical, quand les anciennes lectures sont terminées.

Le compositeur conserve un bit de couverture par pixel. Une couche opaque
peut ainsi afficher l'index zéro, quelle que soit sa couleur dans la palette.
Une couche avec clé zéro laisse le contenu inférieur ; un pixel jamais
couvert laisse apparaître le framebuffer RGB565. Les sprites gardent leur
clé zéro. Ce bit de couverture n'est pas un canal alpha.

Les lignes indexées et leur couverture sont stockées dans deux banques
séparées des lignes RGB565. Au pixel, la palette est sélectionnée uniquement
si un élément de la composition couvre cette position. La conversion du fond
RGB565 en RGB666 conserve l'expansion des composantes R/B de L13–L15.

L'affichage composé effectue les lectures RGB565 avec plusieurs requêtes
DDR en vol, bornées par les 16 tags de l'arbitre existant. La ligne est
acquittée après la composition et la réception de tout son fond. Le mode
RGB565 sans couches conserve son séquencement de lecture précédent.

Les 16 couches et 64 sprites sont des capacités de tables. Leur charge
cumulée reste limitée par les quelque 2 556 cycles mémoire disponibles
par ligne à 75 MHz. Une surcharge incrémente le compteur de lignes manquantes.

## Textures corrigées en perspective

Le bit 4 de `RASTER_STATE.flags` (`GPU_PERSPECTIVE`, valeur 16) active la
correction. Il exige aussi `GPU_RASTER_TEXTURE`. Les modes affines et les
opcodes 1–20 gardent leurs contrats précédents.

Le nouvel **opcode 21, PLANE_Q**, utilise le même format que PLANE_U/V :
origine signée étendue sur 48 bits, dérivées signées sur 32 bits, ou ancien
format signé 32 bits quand le mot 4 est nul. Le préparateur logiciel fournit :

- U : un plan interpolant `u × Q` ;
- V : un plan interpolant `v × Q` ;
- Q : un plan interpolant une valeur proportionnelle à `1 / profondeur caméra` ;
- Z : le plan de profondeur écran destiné au Z16, indépendant des trois autres.

U, V et Q doivent avoir la même échelle. Pour chaque fragment, le moteur
calcule exactement `floor(U / Q)` et `floor(V / Q)` sur les entiers interpolés.
Il applique ensuite rejet, répétition ou limitation au bord de la texture.
Les coordonnées négatives suivent un arrondi vers moins l'infini, y compris
en répétition. Les valeurs extrêmes conservent le chemin exact, sans troncature
du quotient avant le calcul de l'adresse répétée.

Un Q nul ou négatif rejette le fragment sans écrire couleur ni profondeur.
Un plan Q absent ou invalide fait refuser la commande de triangle. Le logiciel
reste responsable du découpage géométrique au plan proche et de la préparation
de plans cohérents. Les origines extrapolées ne sont pas limitées au domaine
des coordonnées visibles ; les accumulateurs restent signés sur 49 bits.

`gpu_perspective.v` produit deux bits de quotient par cycle en base quatre,
pour U et V ensemble. Les soustractions de Q, 2Q et 3Q sont parallèles.
La sélection des restes est exclusive ; le chemin général traite 50 bits
avec un zéro de tête, en 25 pas, pour éviter un dernier pas impair.
La capture des coordonnées et leur valeur absolue sont séparées par un registre. Quand les quotients absolus sont inférieurs à 256,
les bits supérieurs connus nuls sont sautés. Deux instances préparent
alternativement deux pixels en avance, pendant le traitement des fragments.
Les coordonnées lointaines peuvent demander davantage de cycles ; la
contre-pression attend alors le résultat exact. Aucune horloge n'est ajoutée.

La texture reste RGB565, au plus proche voisin, au maximum 128 × 128.
Cette extension n'ajoute ni filtrage bilinéaire, ni alpha par texel.

## API et observation

- Capacités raster `0xe9001020` : bit 4 = perspective ; valeur actuelle `0x1f`.
- `0xe9000068`, bit 0 : composition indexée sur framebuffer RGB565.
- `0xe9000060` : somme modulo 2^32 des pixels RGB666 effectivement présentés
  pendant la dernière image complète, publiée au début de VS. Elle inclut
  la palette, les couvertures et le fond ; chaque pixel vaut `R<<12 | G<<6 | B`.
- `0xe9000064` : maximum du temps mémoire total d'une ligne, composition et
  fond inclus, hors ligne zéro qui bénéficie du blanking et charge les sprites.
  L'écriture dans `0xe900002c` remet aussi ce maximum à zéro.
- La somme historique `0xe9000020` reste celle du fond en RGB565, y compris
  avec superposition ; elle ne représente pas l'image composée.

`gpu_rgb565_scene_submit(page, layers, sprites)` soumet le fond et les tables
ensemble. Comme `gpu_scene_submit`, elle lance la transaction ; utiliser
`gpu_display_wait()` avant de réutiliser le tampon présenté précédemment.
`gpu_rgb565_present()` conserve son rôle d'affichage RGB565 sans couches.

## Démonstration commune

- `a` : quatre poses affines historiques, vérification couleur/Z/gardes.
- `b` : animation affine historique.
- `d` : quatre poses en perspective, vérification couleur/Z/gardes et de
  l'empreinte LCD composée, avec texte, sprite et décor en tuiles.
- `e` : animation en perspective avec les mêmes superpositions 2D.
- `c` : pause de l'animation courante.

Le texte reste fixe ; le petit sprite et le ruban de tuiles se déplacent par
modification des descripteurs. Un rectangle noir opaque, en bas à gauche,
teste l'index zéro d'une couche sans clé. Les noirs des cubes appartiennent
à leur texture. Les trois panneaux translucides du bas restent fixes.

Le firmware passe de `-O2` à `-Os` pour conserver toutes les démonstrations
et références dans l'ITCM de 64 Kio. Sa taille est de 54 552 octets pour ce
lot ; les performances des anciennes et nouvelles scènes doivent être
revérifiées sur carte. Le cœur reste à 800 MHz.
