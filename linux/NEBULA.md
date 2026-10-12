# NEBULA — Rift Raiders

Jeu d'arcade spatial original, natif Linux, pour la Tang Mega 138K Pro Dock.
Le processeur calcule les déplacements, l'intelligence des ennemis et les
collisions pendant la partie. Le FPGA compose l'image : ce n'est pas une vidéo.

## Jouer

Depuis le PC :

```sh
ssh -t michael@ax15 'python3 -m serial.tools.miniterm /dev/ttyACM1 115200 --raw --eol LF'
```

Le réglage `--eol LF` évite les deux commandes vides envoyées par Entrée en
mode CRLF. Quitter miniterm avec **Ctrl+]**. Le numéro ACM peut changer après
un rebranchement ; le lien stable est
`/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00`.

Les essais ont aussi relevé occasionnellement des caractères doublés dans
la sortie CDC. Cette anomalie distincte du réglage Entrée reste consignée dans
les tests ; NEBULA n'apporte pas de correction au transport USB.

Dans le shell `prodock#`, si la démonstration de validation tourne encore :

```sh
kill "$(cat /tmp/nebula.pid)"
nebula
```

Un seul jeu peut posséder le GPU. Arrêter le jeu précédent avant d'en lancer
un autre. Sans démonstration en cours, lancer simplement `nebula`.

| Touche | Action |
|---|---|
| Flèches ou W/A/S/D | Déplacement avec inertie ; Z fonctionne aussi pour monter |
| Espace | Nova : onde lumineuse, destruction des tirs et dégâts aux ennemis |
| P | Pause / reprise |
| F | Jeu plein écran / disposition partagée avec terminal et tableau de bord |
| Q ou Ctrl+C | Quitter et rendre le GPU au système |
| R ou Entrée | Rejouer après victoire ou défaite |

Le vaisseau tire automatiquement. Le clavier série transmet des événements,
pas l'état physique des touches : les frappes déplacent une cible que le
vaisseau rejoint progressivement ; la répétition du clavier permet un mouvement
continu. Le terminal utilisé doit transmettre les flèches comme des séquences ANSI.

```sh
nebula --split                    # jouer avec les consoles visibles
nebula --demo                     # pilote automatique au premier plan
nebula --demo --boss              # commencer directement face au premier boss
nebula --demo --frames 600        # essai fini avec mesure du débit réel
```

Le mode `--demo` ne lit pas le clavier. Au premier plan, **Ctrl+C** l'arrête.
Au second plan, conserver son PID et utiliser `kill` :

```sh
nebula --demo > /tmp/nebula.log &
echo $! > /tmp/nebula.pid
```

## La partie

Trois secteurs, chacun comprenant des vagues d'intercepteurs et de bombardiers,
puis un croiseur de fin de secteur. Les trajectoires se courbent, les adversaires
tirent et les boss alternent leurs attaques. Le joueur dispose de cinq points
de coque et de trois novas au départ. Les combos augmentent le score ; huit
ennemis détruits améliorent le tir. Les bonus de réparation apparaissent au
fil des destructions, avec quatre bonus présents au maximum. Une nova peut
être récupérée après douze destructions, sans dépasser trois charges.

La démo joue avec ces mêmes règles et recommence après l'écran de fin. Son
pilote anticipe les tirs et vise les réparations. Il ne suit pas une vidéo ni
une liste de coordonnées précalculées.

## Accélérations utilisées

| Élément | Travail du FPGA |
|---|---|
| Fond et panneaux | Copie RGB565 et remplissages matériels |
| Profondeur du champ d'étoiles | Deux couches indexées qui défilent à des vitesses différentes |
| Ennemis, tirs, bonus, explosions | Sprites matériels en cache, jusqu'à 64 descripteurs |
| Vaisseau, bouclier, croiseur, titre | Couches indexées avec transparence par couleur clé |
| Score, coque, secteur et messages | Cartes de tuiles et atlas de glyphes matériels |
| Lueurs et moteurs | Triangles texturés ARGB4444 avec mélange additif |
| Nova | Anneau composé de 40 triangles additifs |
| Présentation | Double tampon, échange au retour vertical, agrandissement matériel ×2 |

Le fond est rendu à **400×240**. En plein écran, il est agrandi à **800×480**,
avec des ressources de composition adaptées à la résolution native. En mode
partagé, le jeu occupe les 400×240 pixels supérieurs gauches. Le terminal et
les diagnostics conservent les couches 12 à 15 et les couleurs 240 à 255.

Les scènes utilisent jusqu'à huit couches du jeu dans la campagne testée.
Le budget de sprites donne priorité aux objets ayant un effet sur le jeu :
12 ennemis, 16 tirs amis, 22 tirs ennemis et 4 bonus. Seuls les effets décoratifs
peuvent être omis lorsque les 64 emplacements sont occupés ; ce nombre est
comptabilisé. L'essai de saturation vérifie ce comportement.

Cette version exploite le GPU 2D et sa rasterisation. Elle n'ajoute pas
d'interface Linux G3D1, de pilote OpenGL ou de son ; l'audio Linux reste un
chantier distinct.

## Ressources et mémoire

Les deux illustrations originales proviennent de l'outil intégré `image_gen`.
Les [prompts complets](../assets/nebula/source/PROMPTS.md) et les PNG sources
sont conservés. Le convertisseur produit les images RGB565, les sprites
indexés, les versions de taille différente, la palette et les effets ARGB4444.

Le paquet contient **55 ressources, 435 584 octets**, CRC32 `856b56d9`.
Le programme vérifie l'en-tête, la taille exacte, le CRC et les limites de
chaque ressource avant de les transmettre. Il réserve une fenêtre de 14 Mio
dont **10 334 592 octets** sont utilisés, hors mémoire des consoles Linux.

## Construction et vérification

```sh
python3 tools/build_nebula_assets.py
make -C linux all JOBS=4
python3 linux/tests/test_nebula.py
python3 linux/tests/test_nebula_scanout.py --out /tmp/nebula-rtl-results
python3 linux/tests/test_atomic_code.py
```

Le test natif utilise AddressSanitizer et UndefinedBehaviorSanitizer, exerce
les règles du jeu et soumet les commandes et scènes aux validateurs réels du
pilote. Le modèle hôte et `tools/preview_nebula.py` servent à produire des
images de référence ; leur vitesse n'est pas une mesure de celle du FPGA.
Le second test, qui nécessite Verilator et un compilateur C++, compare tous
les pixels de trois scènes au RTL réel du scanout. Pour un diagnostic ciblé,
`--pose N --snapshot /tmp/scene.bin` exporte les descripteurs de la cible et
leur CRC. `tools/read_nebula_scene.py` relit ce fichier avec contrôle du CRC.

`tools/check_nebula.py` est réservé à une carte déjà démarrée sous Linux,
sans autre utilisateur du port CDC ni du GPU. Il compare les empreintes de
scènes fixes, exerce le clavier et les dispositions, puis mesure une partie.
Il ne programme pas le FPGA et n'écrit pas sur la SD physique.

Les [résultats et limites des essais](../TESTS/NEBULA_20261012.md) distinguent
les tests du modèle, les mesures physiques et les anomalies rencontrées.
Sur la carte, R17 mesure **47,80 FPS** sur 600 images en plein écran et
**45,31 FPS** sur 600 images en disposition partagée. L'endurance de
**10 000 images atteint 43,97 FPS de moyenne**, avec les compteurs GPU
recoupés et sans erreur ni underflow. Ce sont des moyennes mesurées sur ces
séquences, pas une garantie de débit constant pour toutes les situations.
Le chargement courant est volatile ; il ne remplace pas encore le démarrage
SD permanent.
