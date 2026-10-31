# Le projet : console de jeux sur FPGA GW5AST-138

Vue d’ensemble du projet. Il décrit **ce qui existe**, **ce qui est
qualifié**, et **ce qui ne l'est pas**. Les états sont datés : ils valent au
**31 octobre 2026** et pour les builds cités.

> Règle de lecture : une capacité présente dans le RTL, un test local qui
> passe et une qualification matérielle sur une carte donnée sont **trois
> choses différentes**. Ce document les distingue systématiquement.
> Pour l'état détaillé carte par carte, [ARCHI/COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md)
> fait autorité.

## Sommaire

1. [Objectif et périmètre](#1-objectif-et-périmètre)
2. [Matériel cible](#2-matériel-cible)
3. [Architecture système](#3-architecture-système)
4. [Le CPU](#4-le-cpu)
5. [La carte graphique](#5-la-carte-graphique)
6. [Ce qui est accéléré par le matériel, ce qui reste au CPU](#6-ce-qui-est-accéléré-par-le-matériel-ce-qui-reste-au-cpu)
7. [Mémoire et profils](#7-mémoire-et-profils)
8. [Périphériques](#8-périphériques)
9. [Logiciels : Linux et bare-metal](#9-logiciels--linux-et-bare-metal)
10. [Jeux, démos et applications](#10-jeux-démos-et-applications)
11. [Profils de rendu](#11-profils-de-rendu)
12. [Chaîne de construction et outillage](#12-chaîne-de-construction-et-outillage)
13. [Limites et problèmes ouverts](#13-limites-et-problèmes-ouverts)
14. [Documents de référence](#14-documents-de-référence)

## 1. Objectif et périmètre

Réaliser une **console de jeux matérielle** sur un FPGA Gowin GW5AST-138 :

- un cœur **RISC-V AE350/A25 à 800 MHz** exécutant soit Linux, soit du code
  bare-metal ;
- un **GPU programmable** partagé entre le CPU et l'affichage ;
- une **DDR3 commune** pour le CPU, le rendu et le scanout ;
- une **interface de jeu** (affichage, entrées, son, stockage) ;
- un **portage progressif** vers une seconde carte, la Neo, sans dégrader le
  profil fonctionnel.

Objectifs encore ouverts : une campagne de plusieurs heures, un démarrage
autonome après coupure et la qualification complète du profil Neo. Le
présent document ne vaut pas qualification d’un produit commercial.

## 2. Matériel cible

| | **Pro Dock** | **Neo / Console** |
|---|---|---|
| Rôle | profil fonctionnel de référence | portage en diagnostic |
| Sortie | LCD 800 × 480, cadence nominale 55,04 Hz | HDMI 1280 × 720 (720p) |
| Référence conservée | G22r0 / NEBULA R17 | aucune référence qualifiée |
| Cible de rendu réduite | 400 × 240 agrandie ×2 | 640 × 360 agrandie vers 1280 × 720 |
| Statut | fonctionnel, limites de timing historiques documentées | **pas une console validée** |

Inventaire détaillé des cartes, entrées et différences :
[ARCHI/INVENTAIRE_CARTES.md](INVENTAIRE_CARTES.md),
[ARCHI/CARTES/README.md](CARTES/README.md),
[ARCHI/CARTES/prodock/README.md](CARTES/prodock/README.md),
[ARCHI/CARTES/neo/README.md](CARTES/neo/README.md).

Le partage des sources est explicite : un **jeu de sources commun unique**,
des adaptations par carte (horloges, broches, contraintes) inventoriées dans
`tang/boards/ownership.json`, et une autorité documentaire unique :
[ARCHI/COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md).

## 3. Architecture système

```text
   ┌───────────────┐  commandes GPU   ┌────────────────────────────┐
   │  CPU AE350/A25│ ───────────────► │  GPU                       │
   │  RV32 800 MHz │   registres/     │  layers 16, sprites 64,    │
   │  Linux / bare │ ◄─────────────── │  tiles, blitter, affine,   │
   │  -metal       │   compteurs      │  raster RGB565 + Z16,     │
   └───────┬───────┘                  │  G3D1 (mesh/matrix/clip)   │
           │                          └───────┬────────────────────┘
           │  DDR3 partagée IP 5.9 / 300 MHz  │ bus 256 bits
           │            ┌─────────────────────┴──────────────┐
           └───────────► │  DDR3 : CPU + dessin + scanout    │
                          └─────────────────────┬──────────────┘
                                               │ scanout
                                 ┌─────────────┴─────────────┐
                                 │  LCD 800×480  ou  HDMI 720p│
                                 └───────────────────────────┘
```

Le flux graphique est un **aller-retour CPU → GPU → DDR3 → affichage** :
le CPU prépare les données (pages, palettes, maillages, textures, commandes),
le GPU rend dans la DDR3 et le compositeur produit les pixels pendant le
balayage. Les changements de descripteurs sont appliqués au retour vertical.
Le CPU peut aussi préparer ou transférer des pixels ; l’optimisation des jeux
de plateau réduit justement le coût de comparaison des lignes à publier.

## 4. Le CPU

- **Cœur** : AE350/A25, RISC-V RV32, fréquence configurée **800 MHz**.
- **Horloges** du port Pro Dock : bus 80 MHz, GPU 75 MHz, LCD 35 MHz.
- **Systèmes** : Linux (avec OpenSBI) ou code bare-metal, **exclusifs** — les
  applications bare-metal ne tournent pas en parallèle du noyau.
- **Compteurs** : `CYCLE` et `INSTRET` accessibles **en mode U** ; seule la
  progression de `CYCLE` a été vérifiée. La lecture de `TIME` en mode U
  déclenche `SIGILL` dans le test considéré. Il n'existe **pas de conversion
  cycles → Hz** validée : aucune fréquence CPU n'est déduite de ces compteurs.
  Les durées mesurées incluent la boucle et le lecteur logiciel ; elles ne
  mesurent ni le coût intrinsèque d’une instruction CSR ni son éventuelle
  émulation par OpenSBI.
- **Pile logicielle de référence** : portage expérimental Linux 6.12.112, OpenSBI 1.6,
  BusyBox 1.37.0, musl 1.2.5.

## 5. La carte graphique

### 5.1 Capacités

| Domaine | Capacité |
|---|---|
| Couches | 16 plans, tables de composition appliquées au retour vertical |
| Sprites | 64 sprites 2D, dimensions 1 à 32 pixels par axe, retournements X/Y |
| Texte / tuiles | rendu tuilé (tuilemap), terminal à tuiles, texte matériel |
| Blitter | remplissage, copie, transparence, additive |
| Transformation | affine (rotation, échelle), texture |
| Raster | rastérisation texturée RGB565, profondeur Z16 disjointe |
| Éclairage | éclairage et brouillard |
| Géométrie | G3D1 : maillages, matrices, clipping, projection, culling |
| Formats | 256 couleurs indexées (palette RGB666) ; RGB565 direct converti vers le LCD RGB666 |
| Cibles de dessin | 1…1024 × 1…512, bases et pas alignés sur 32 octets |
| Présentation | double tampon, échange au retour vertical pour éviter les déchirures |

Références : [ARCHI/GPU_V1.md](GPU_V1.md) (contrat, mémoire, composition),
[ARCHI/GPU_GEOMETRY.md](GPU_GEOMETRY.md) (géométrie 3D),
[ARCHI/FONCTIONNALITES_ACTUELLES.md](FONCTIONNALITES_ACTUELLES.md) (état
détaillé). Les registres sont détaillés séparément :
[GPU_G2](GPU_G2_REGISTRES.md), [GPU_G3](GPU_G3_REGISTRES.md),
[GPU_G4](GPU_G4_REGISTRES.md), [GPU_G5 triangles](GPU_G5_TRIANGLES_3D.md),
[tuiles L11](GPU_L11_TILEMAPS.md), [affine L12](GPU_L12_AFFINE.md),
[RGB/profondeur L13-L15](GPU_L13_L15_RGB_DEPTH.md),
[spans DDR 256](GPU_SPANS_DDR256.md),
[composition en perspective](GPU_PERSPECTIVE_COMPOSITION.md).

Les couches indexées utilisent la clé de couleur zéro ; le mélange alpha
et additif est effectué pendant le dessin dans la cible RGB565. Le budget
mémoire par ligne limite les combinaisons effectives de couches et sprites.
Il n’y a pas de shaders programmables, ni de filtrage bilinéaire ; les niveaux
de mipmap sont préparés et sélectionnés explicitement.

### 5.2 Géométrie 3D (G3D1)

La géométrie est **matérielle** : transformation des sommets par matrices,
clipping, projection, élimination des faces arrière, puis rastérisation.
Le Z-buffer résout l’occultation des surfaces opaques. Les
« sprites 3D » du projet sont des **quads texturés** dans ce pipeline, pas
des sprites 2D replaqués. Les buffers de sommets et d'indices, ainsi que
l'ABI des commandes, sont décrits dans [ARCHI/GPU_GEOMETRY.md](GPU_GEOMETRY.md).

### 5.3 Mesures datées

| Mesure | Build / carte | Résultat |
|---|---|---|
| ORBITAL R6 | `gpu_sdusb_c37`, C37 | 51 références exactes, 28 546 images en 520,828 s réelles, **54,81 images/s**, zéro erreur, underflow ou rejet |
| Endurance GPU V1 | `gpu_v1_r31` | **30 minutes, 58 680 images, zéro erreur détectée** |
| Affichage Linux | R12 sur G22r0 | 51,92 FPS sur 180 images ; 131 s d'endurance à 51,09 FPS sans erreur |

Ces valeurs sont **historiques et datées** : elles qualifient le build et la
carte cités, pas le code actuel.

## 6. Ce qui est accéléré par le matériel, ce qui reste au CPU

| Tâche | Exécution | Précision |
|---|---|---|
| Composition des couches | **matériel** | tables de couches appliquées au retour vertical |
| Sprites 2D | **matériel** | 64 sprites avec retournements ; l’affine dessine séparément dans une surface |
| Tuiles et texte | **matériel** | glyphes composés par le FPGA (terminal fbcon tuilé) |
| Blitter | **matériel** | remplissage, copie, transparence, additive |
| Raster texturé | **matériel** | RGB565, profondeur Z16 |
| Éclairage / brouillard | **matériel** | paramètres par sommet |
| Géométrie 3D | **matériel** | matrices, clipping, projection, culling |
| Simulation de jeu | **CPU** | logique, physique, IA, machine à états |
| Collisions | **CPU** | pas d’accélération matérielle dédiée |
| Caméra et matrices de scène | **CPU** | le GPU applique les matrices, il ne décide pas du cadrage |
| Génération des assets | **hôte** | ressources produites via ComfyUI puis empaquetées |
| Rendu 3D final | **matériel, en direct** | calculé image par image, **ce n'est pas une vidéo** |

Le GPU calcule l’image courante à partir des maillages et des commandes.
Les ressources peuvent être précalculées ; l’affichage ne rejoue pas une vidéo.

## 7. Mémoire et profils

- **DDR3 IP 5.9 à 300 MHz**, partagée CPU / dessin / affichage, transferts GPU
  de 256 bits. Il s’agit de la version **5.9 de l’IP Gowin DDR3** ; les essais avec
  l’IP 6.0 ont été abandonnés. Ces numéros ne désignent pas une génération
  de mémoire DDR5 ou DDR6.
- **Convention historique : 16 pages** espacées de 1 Mio ; **384 000 octets** utiles en indexé,
  **768 000 octets** en RGB565 ou Z16. L’ABI V1 utilise aussi des surfaces
  allouées par adresse ; ces 16 pages ne sont pas une limite de l’allocateur.
- **Cible réduite** 400 × 240 agrandie ×2 par le matériel ; les couches,
  sprites et HUD restent en 800 × 480.
- **Sous Linux, profil Pro Dock** : la fenêtre GPU réserve **2 Mio à
  l'affichage** et expose **86 Mio aux applications graphiques**. Ce n'est
  pas la quantité totale de RAM disponible pour les processus Linux.
- **Cible de dessin** : dimensions 1…1024 × 1…512, chemins couleur et Z16
  disjoints, pas indépendants, bases et pas alignés sur 32 octets.

Profils mémoire et contraintes : [ARCHI/GPU_V1.md](GPU_V1.md),
[ARCHI/GPU_SPANS_DDR256.md](GPU_SPANS_DDR256.md).

## 8. Périphériques

| Périphérique | État | Détail |
|---|---|---|
| LCD 800 × 480 | qualifié Pro Dock | cadence nominale 55,04 Hz, conversion RGB565 → RGB666 |
| HDMI 720p | non qualifié | mire interne confirmée sur N56r8 ; framebuffer non établi |
| USB 2 HS | selon build et logiciel | CDC pour la console ; firmware bare-metal CDC/MSC pour exposer un disque. Les validations MSC ne qualifient pas automatiquement le périphérique Linux |
| SD en SPI | campagne actuelle en lecture seule | pilote Linux de bloc ; débit anormalement faible, 27 dernières lectures CRC/volume correctes sans timeout |
| Entrées de jeu | intégration partielle | clavier série utilisable ; intégration des manettes à LUMA3D inachevée ; deux ports USB 2 host prévus sur Neo |

Détails : [ARCHI/SD_USB_DISQUE.md](SD_USB_DISQUE.md),
[ARCHI/LINUX_AFFICHAGE_PARTAGE.md](LINUX_AFFICHAGE_PARTAGE.md).

## 9. Logiciels : Linux et bare-metal

### 9.1 Sous Linux

- **Pilote GPU** (`/dev/prodock-gpu`) : un propriétaire, accès root ou
  `CAP_SYS_RAWIO`, ioctl et mmap.
- **Terminal à tuiles** (`/dev/tty1`, fbcon `tileblit`) : glyphes composés par
  le FPGA, `fb0` réservé au noyau.
- **Dispositions** (`/dev/prodock-display`) : jeu, console, debug, plein
  écran ; `prodockctl selftest|info|demo|display|layout`.
- **Applications** : `prodock-game` (casse-briques GPU), `nebula` (jeu spatial
  à trois secteurs), `prodock-runtime` (threads, mutex, fork, mmap,
  `mprotect`, copie à l'écriture).
- **Console série** `/dev/ttyS0` : UART2 via CDC FPGA HS 480 Mbit/s, UART à
  115200.
- **SD** `/dev/mmcblk0` : pilote `mmc_spi` amont, mode SPI 0, jusqu'à 20 MHz.
- **Deux modes conservés** : Linux et applications bare-metal séparées.
  Sur la seconde Pro Dock R6, le premier étage charge U-Boot depuis la SD,
  puis le paquet Linux ; la chaîne a été observée avec le FPGA en SRAM.
  Cela ne prouve pas le démarrage autonome depuis la flash après coupure.

### 9.2 Bare-metal

Applications sans noyau : LUMA, ORBITAL, ASTRILLA, démos GPU (couches,
sprites, tuiles, affine, raster), utilitaires SD/USB, sondes de diagnostic. Le
code est partagé avec Linux au niveau des commandes GPU.

### 9.3 Moteur commun

Le moteur de jeu commun Pro Dock / Neo, ses réutilisations, ses séparations
et ses profils mémoire sont documentés dans
[ARCHI/MOTEUR_JEU_ETAT_20261027.md](MOTEUR_JEU_ETAT_20261027.md).

## 10. Jeux, démos et applications

| Projet | Nature | Support |
|---|---|---|
| **NEBULA** | tir spatial, trois secteurs, boss, novas | exécutable Linux ; [guide](../linux/NEBULA.md) |
| **LUMA** | aventure automatique en forêt, caméra mobile, héros animé | bare-metal ; [guide](../assets/luma/README.md) |
| **ORBITAL** | tir à la première personne, textures en perspective, brouillard, mipmaps | bare-metal ; [guide](../assets/orbital/README.md) |
| **ASTRILLA** | vol 3D | bare-metal ; [ARCHI/ASTRILLA.md](ASTRILLA.md) |
| **LUMA3D** | monde d'exploration avec activités et énigmes | hôte puis RISC-V ; [README](../games/luma3d/README.md), [état du contenu](../games/luma3d/CONTENT_STATUS.md) |
| **LUMA Adventure** | aventure plus légère | [README](../games/luma_adventure/README.txt) |
| **Jeux de plateau** | Solitaire, Chroma, Othello, Pendu | hôte puis carte ; optimisation « dirty rows » mesurée |
| **Démos GPU** | couches, sprites, tuiles, affine, raster, géométrie | `fw_console` ; voir [Makefile](../fw_console/Makefile) |

### 10.1 Optimisation « dirty rows » (31 octobre 2026)

Optimisation testée en **A/B/A** sur la 2ᵉ Pro Dock, **même FPGA, même
noyau** : Solitaire **+255,7 %**, Chroma **+204,7 %**, Othello **+123,4 %**,
Pendu **+141,2 %** de FPS. Résultat **fonctionnel** sur une campagne unique :
ce n'est pas un intervalle de confiance, ni une qualification de fluidité
(les pointes mesurées vont de 217 à 275 ms).

### 10.2 LUMA3D : état du contenu

Campagne de référence du 27 octobre 2026 (GM1) : 8 oracles, 10 fenêtres A/B,
tour complet de 17 étapes et 8 activités, 1 079 commandes, 772,622 s simulées
et 783,232 s réelles. FPS du tour complet : exploration 10,65 ; circuit 19,95 ;
blocs 38,37 ; formes 20,65 ; 1024 21,61 ; maison 11,83 ; Simon 25,70 ;
tireur 43,40 ; tour 19,72. Les p99 atteignent 420 ms (circuit, formes) et
384 ms (maison).

Le monde publié historiquement comprend deux petites régions. Les nouveaux
jeux de plateau existent dans des candidats distincts ; leur intégration
globale n’est pas qualifiée. La campagne de plusieurs heures, les véhicules
3D, l’audio et les sauvegardes persistantes restent à terminer. Le monde « Serres » et son optimisation ont été
compilés et testés localement (26 étapes d'autoplay, ~15 min simulées) mais
**n'ont pas été chargés sur carte**.

## 11. Profils de rendu

| Profil | Cible interne | Sortie | Statut |
|---|---|---|---|
| Pro Dock jeu | 400 × 240 | 800 × 480 (agrandissement ×2) | **qualifié** |
| Pro Dock Linux | 800 × 480 (fb0) | 800 × 480 | **qualifié sur G22r0** (R12) |
| Neo | 640 × 360 | 1280 × 720 HDMI | **non validé matériellement** |

Le portage Neo et ses conditions sont décrits dans
[ARCHI/PORT_NEO_720P.md](PORT_NEO_720P.md) et
[ARCHI/FEUILLE_DE_ROUTE_CONSOLE.md](FEUILLE_DE_ROUTE_CONSOLE.md).

## 12. Chaîne de construction et outillage

- **Synthèse et routage de la console complète : Gowin**. Le Workbench
  analyse les résultats et prépare des essais de placement. Yosys /
  nextpnr / Apicula sont disponibles pour des sous-ensembles ; leur support
  de la console complète avec AE350, DDR et PHY USB n’est pas établi.
- **Candidats** : les constructeurs Pro Dock **refusent par défaut** les
  entrées modifiées ; un build expérimental exige `--candidate`. Côté Neo,
  tous les builds restent candidats. Le marquage n'est jamais une
  qualification matérielle.
- **Garde de référence** : chaque nouveau dossier de build reçoit un
  `board_contract.json` distinct des sources synthétisées, qui conserve les
  écarts et les preuves locales. La garde ne met jamais à jour la
  référence automatiquement.
- **Campagne locale** : `python3 tools/run_board_regressions.py --out
  TESTS/dual_board/<nom-unique>` après toute modification.
- **Optimisation de placement** : [optimizer/README.md](../optimizer/README.md)
  (bootstrap, `open`, `place`, `plan`, `report`, `search`).

## 13. Limites et problèmes ouverts

1. **Neo non qualifiée** : R19 accepte TARGET puis SCISSOR, mais rejette COPY
   même par débogueur AHB, CPU volontairement arrêté ; **cause non établie** — aucune
   conclusion DDR, FIFO ou timing. Un observateur S400 a été préparé et
   synthétisé séparément (assemblage préservant 148 modules applicatifs,
   4 simulations de transport mappé PASS). Son routage
   `console_neo_s400_20261031_r1` est lancé ; **aucun essai sur carte**
   de cet observateur n’a encore eu lieu.
2. **Boot flash autonome non qualifié** sur la 2ᵉ Pro Dock : U-Boot, Linux et
   AUTOSTART ont été observés **en SRAM** ; après coupure d'alimentation, le
   redémarrage autonome n'est pas démontré. Le dernier noyau diagnostic est
   en RAM, SD démontée.
3. **SD en SPI très lente** : l'observateur lourd biaise les mesures
   (64 KiB : OFF1 ≈ 1,466 s, ON ≈ 2,072 s, OFF2 ≈ 1,479 s ; ancien noyau
   ≈ 0,91 s). Sonde légère préparée **mais non chargée** ; aucune SCLK n'a
   été mesurée physiquement ; le pilote U-Boot n’a pas encore reçu une correction de débit validée.
4. **3D en temps réel non qualifié** : dernier A/B/A à 120 images fixes,
   6,86 → 6,73 → 6,69 FPS, aucun gain démontré ; 8 lots synchrones par image.
   Le goulot d'étranglement « SUBMIT » (475 commandes par image) n'est pas
   encore réparti entre GPU occupé, attente FIFO, timing, ordonnancement et
   exclusion d'affichage de texte.
5. **Latences** : p99 jusqu'à 420 ms sur certaines activités.
6. **Sauvegarde volatile** et **contenu LUMA3D inachevé** (audio, manettes,
   véhicules 3D, intégration des nouveaux jeux).
7. **USB** : transferts MSC de gros volume encore à fiabiliser.
8. **Instrumentation** : la lecture de `CYCLE` en mode U ne qualifie pas
   son emploi en mode S. Le protocole de sonde légère doit protéger ce cas
   et mesurer son propre coût avant d’attribuer les durées au SPI.

## 14. Documents de référence

- [ARCHI/COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md) — autorité
  compatibilité et conservation de la référence.
- [ARCHI/FONCTIONNALITES_ACTUELLES.md](FONCTIONNALITES_ACTUELLES.md) —
  capacités et mesures de référence.
- [ARCHI/GPU_V1.md](GPU_V1.md), [ARCHI/GPU_GEOMETRY.md](GPU_GEOMETRY.md) —
  contrats GPU.
- [ARCHI/MOTEUR_JEU_ETAT_20261027.md](MOTEUR_JEU_ETAT_20261027.md) — moteur
  commun.
- [ARCHI/LINUX_AFFICHAGE_PARTAGE.md](LINUX_AFFICHAGE_PARTAGE.md) — partage
  CPU/GPU de l'affichage.
- [ARCHI/ARCHI_V2_CONSOLE_JEUX.md](ARCHI_V2_CONSOLE_JEUX.md) — décisions
  d'architecture.
- [linux/README.md](../linux/README.md) — port Linux, modes de démarrage.
- [games/luma3d/README.md](../games/luma3d/README.md) — jeu LUMA3D.
- [AGENTS.md](../AGENTS.md) — règles de travail obligatoires.

## 15. Preuves récentes et état des artefacts

Les chemins suivants désignent des preuves conservées sur le poste. Leur
présence dans un clone Git dépend des fichiers effectivement publiés ; un
chemin dans cette table ne promet pas le téléchargement d’un binaire.

| Sujet | Preuve locale |
|---|---|
| Jeux de plateau A/B/A | `TESTS/game_dirty_rows_hwprep_20261031_01/hardware_analysis_01/ANALYSIS.md` |
| Parcours 3D, temps SUBMIT | `TESTS/game_3d_submit_diag_20261031_01/DIAGNOSTIC.md` |
| Lectures SD et biais de mesure | `TESTS/prodock_new_20261028/sd_spi_diag_root_trial_01/spi_measure_preparation_01/HARDWARE_REVIEW_01.md` |
| Compteurs accessibles en mode U | `TESTS/prodock_new_20261028/sd_spi_diag_root_trial_01/user_counter_run_preparation_01/HARDWARE_ANALYSIS.md` |
| Candidat Serres | `TESTS/game_world_dirty_rows_20261031_01/DELIVERY.json` |
| Capture Neo S400 | `TESTS/neo_common_cause_20261028/copy_result_analysis_01/s400_20261031_01/MAPPED_DELIVERY.json` |

Voir aussi [construction et tests](DEMARRAGE_ET_TESTS.md) et
[conservation des artefacts](CLEANUP.md). Les anciens documents restent datés :
le chapitre graphique du 9 octobre précède G3D1 et ne décrit donc pas toutes
les capacités introduites ensuite.
