# G6 — Mega Coast, premier jeu de course

Le GPU courant ajoute les [triangles par lignes et aplats DDR natifs](GPU_SPANS_DDR256.md) ;
le jeu démarre maintenant avec son rendu original pour mesurer cette accélération.
Bitstream courant : [console_gpu_fast_800.fs](../bitstreams/console_gpu_fast_800.fs).

Prototype jouable sur le LCD 800×480 de la Tang Mega 138K Pro Dock.
Le cœur AE350 reste à 800 MHz ; AHB 80 MHz, GPU/DDR UI 75 MHz, LCD 35 MHz.

## Jouer

Le bitstream du jeu doit être chargé, puis lancer depuis la racine du dépôt :

```sh
python3 tools/racer_web.py
```

Ouvrir <http://localhost:8765> sur le même ordinateur. Le jeu est affiché
sur le LCD ; la page sert de manette et affiche vitesse, distance et cadence.
Le serveur écoute uniquement sur l'interface locale. Un seul programme doit
posséder le port USB CDC `359f:2011` à la fois. `--port /dev/ttyACM…` permet
une sélection explicite ; `--http-port` change le port de la page.

| Touche | Action |
|---|---|
| Entrée | Démarrer ou recommencer le parcours |
| Gauche / droite | Direction, simultanément avec accélération/freinage |
| Haut | Accélérer |
| Bas / espace | Freiner |
| ZQSD / WASD | Autres touches de conduite |

Les boutons de la page fonctionnent aussi à la souris et au toucher.
La perte de focus relâche les touches ; un arrêt des messages de contrôle
pendant 350 ms relâche les commandes dans le firmware. La voiture continue
sur son inertie puis ralentit. Fermer le serveur avec Ctrl-C arrête l'animation.

Alternative avec une fenêtre native, si Tkinter et un bureau graphique sont
présents : `python3 tools/play_racer.py`. Échap ferme cette fenêtre.
Les deux outils utilisent pyserial, déjà utilisé par les diagnostics USB.

## Ce que fait ce prototype

- Route à deux voies en perspective, virages et bordures alternées.
- Cinq voitures venant en face dans la voie gauche, avec réapparition au loin.
- Voiture du joueur, agrandissement des véhicules à l'approche, arbres et
  balises ; montagnes en arrière-plan avec défilement horizontal.
- Accélération jusqu'à 180 km/h, freinage, dérive dans les virages,
  ralentissement sur l'herbe et collisions avec temporisation de protection.
- Parcours de 6 km, chronomètre, distance, nombre de chocs, arrivée et reprise.
- Simulation à pas fixe de 20 ms, indépendante du débit d'affichage.

C'est une première perspective de type jeu d'arcade : route plane, objets
2D projetés et triés selon la distance. Relief, ponts, croisements 3D,
textures de polygones, Z-buffer, audio, boutons physiques, ADS1115 et manettes
matérielles restent à développer. Les 16 couches et les 64 sprites matériels
G3/G4 sont toujours disponibles ; ce jeu utilise une couche composée.

## Rendu et mémoire

`fw_console/racer_scene.h` contient le modèle, la projection et les dessins
pixel art procéduraux originaux. Il est compilé également sur le PC pour les
tests avec UBSan et le rendu de référence. Aucun gros tableau d'images ne
consomme l'ITCM : l'atlas est produit une fois en DDR3.

| Page DDR | Utilisation |
|---|---|
| 4 | Référence CPU, uniquement lors des comparaisons |
| 6 et 7 | Images alternées, 800×480 indexées |
| 8 | Atlas des voitures, arbres et balises, pas de ligne 800 octets |
| 9 | Panorama précalculé, utilisé par le mode avec cache |

Les triangles matériels dessinent la route. Le mode original recalcule
le paysage et dessine les grandes surfaces de bordure avant la chaussée.
Le mode avec cache copie le panorama et limite les bordures à des bandes
étroites. Les objets sont triés du plus éloigné au plus proche, puis dessinés
par ZOOM. Le texte utilise l'accélérateur existant. Le changement de page
attend la fin de toutes les écritures, puis le retour vertical. Aucun dessin
n'est effectué sur la page affichée. Le cache CPU est publié/invalidé lors
des transferts de propriété des surfaces.

## Commande GPU ZOOM, opcode 11

Huit mots de 32 bits, comme les autres commandes du blitter à `0xe9001010`.

| Mot | Contenu |
|---|---|
| 0 | Opcode 11 en 31:24 ; page cible 23:20 ; page source 19:16 |
| 1 | X puis Y destination, chacun signé 16 bits |
| 2 | Largeur puis hauteur destination, 1..32767 |
| 3 | X puis Y du rectangle source, chacun signé 16 bits |
| 4 | Largeur puis hauteur source, chacune 1..128 |
| 5 | Pas U non signé 8.16, bits 31:24 nuls |
| 6 | Pas V non signé 8.16, bits 31:24 nuls |
| 7 | Réservé, écrire zéro |

Le pilote `gpu_make_zoom()` calcule `pas = (taille_source * 65536) /
taille_destination`. L'échantillon est
`floor((coordonnée_destination - origine_destination) * pas / 65536)`.
C'est du plus proche voisin avec un pas tronqué à 16 bits de fraction.
La couleur indexée zéro est transparente. Les échantillons au-delà du
rectangle source ne modifient pas la destination, même pour des pas forgés.
La destination est découpée aux quatre bords sans décaler la texture.

Le rectangle source doit être entièrement dans sa page 800×480, et les pages
source et cible doivent être différentes. Un rectangle source invalide,
une dimension destination non positive ou un pas hors format produit une
commande vide qui termine normalement ; il n'incrémente pas BAD. Le pilote
rejette aussi les tailles hors contrat en générant une commande vide.
Pas de filtrage bilinéaire, rotation ou copie avec chevauchement dans ZOOM.

Une mémoire de ligne de 128 demi-mots reçoit la source DDR (65 demi-mots au
maximum pour 128 pixels à origine impaire). Elle est relue synchroniquement
et réutilisée lorsque plusieurs lignes cibles échantillonnent la même ligne
source. Le tampon de sortie et ses masques d'octets réutilisent le DMA G2.
Le compteur DONE n'avance qu'après acceptation des dernières écritures DDR.

## Protocole USB du jeu

| Octet | Action |
|---|---|
| `R` | Initialiser le jeu et afficher l'écran de départ |
| `G` | Comparer quatre scènes avec le CPU et le checksum LCD ; animation arrêtée |
| `H` | État du jeu et des commandes |
| `C` | Bascule original / cache et recommence |
| `K` | Benchmark déterministe de 240 images par mode, puis retour au jeu original |
| `X` | Arrêt de l'animation, conserve l'image |
| `0x80 OR masque` | État complet des touches : gauche 1, droite 2, accélérer 4, freiner 8, départ 16 |

Le masque est envoyé régulièrement, même si aucune touche ne change. Le
protocole tient dans un octet, donc un paquet interrompu ne bloque pas le
CPU dans une attente d'octets suivants. `?`, `S`, `H`, `E`, `M` restent
accessibles pendant la course. Les commandes des autres démonstrations
arrêtent le jeu avant de réutiliser les pages et la palette.

Voir [les tests et mesures](../TESTS/TESTS_RACER.md).
