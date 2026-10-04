# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Console de jeux sur **Tang Mega 138K Pro Dock** (GW5AST-138, boîtier FPG676) :
CPU AE350 (RISC-V) à 800 MHz, GPU maison en Verilog, DDR3 partagée CPU/GPU,
LCD 800 × 480 en pixels indexés 8 bits + palette, ou framebuffer RGB565.
Documentation, fiches de test
et messages de commit sont rédigés **en français** (`G5 : … validés à 800 MHz`).

Documents de référence, à lire avant toute évolution :

- `ARCHI/ARCHI_V2_CONSOLE_JEUX.md` : périmètre et état des jalons G0–G7
  (`ARCHI_V1.md` est remplacé ; les fonctions d'acquisition de signaux sont hors périmètre).
- `ARCHI/FEUILLE_DE_ROUTE_CONSOLE.md` : lots restants L00–L18, contraintes, budgets.
- `ARCHI/GPU_G*_REGISTRES.md`, `GPU_G5_TRIANGLES_3D.md`, `GPU_SPANS_DDR256.md`,
  `GPU_L11_TILEMAPS.md`, `GPU_L12_AFFINE.md`, `GPU_L13_L15_RGB_DEPTH.md`,
  `GPU_PERSPECTIVE_COMPOSITION.md`, `GPU_V1.md`, `FONCTIONNALITES_ACTUELLES.md`,
  `JEU_COURSE.md` : contrats de registres, d'opcodes,
  de décors en tuiles et protocole USB du jeu.
- `TESTS/TESTS_*.md` : une fiche de validation par jalon, avec mesures et journaux.

## Commandes

### Build complet (firmware + IP AE350 + FPGA + contrôle du timing)

```sh
python3 tools/build_gpu.py --name gpu_xxx_r1
```

- Le firmware est **incorporé dans l'initialisation ITCM du bitstream** : tout
  changement de firmware exige ce build complet, qui régénère l'IP AE350.
- `tang/impl/<name>` ne doit pas déjà exister : chaque build utilise un nom
  nouveau (`…_r1`, `…_r2`). Les sources sont figées dans `tang/impl/<name>/source`
  avec leur SHA-256 dans `sources.json`.
- Le script écrase `tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v` et
  `cfg/riscv_ae350_soc.vg` : ce diff est attendu après un build.
- Il échoue si une marge de timing est négative. Résultat :
  `tang/impl/<name>/impl/pnr/console_<name>.fs` et `bitstream.sha256`.
- Un build dure environ 12 minutes. Le placement est reproductible mais très
  sensible : une petite modification déplace le pire chemin d'une à deux
  nanosecondes. Compter plusieurs builds pour un changement RTL.
  Les builds étendus GPU V1 du 4 octobre ont demandé **19 minutes à 2 h 36
  pour le placement/routage**, selon la variante : ne pas appliquer
  l'estimation historique de 12 minutes à ce circuit. Un routage plus long
  ne garantit pas de meilleures marges. Le statut physique figure dans
  `TESTS_GPU_V1.md`.
- D'autres projets compilent avec Gowin sur ce PC. Identifier chaque processus
  par son répertoire de travail avant de le gérer ; ne jamais arrêter ou
  relancer globalement les processus Gowin. Les builds de cette console restent
  dans leurs dossiers `tang/impl/<name>` respectifs.
- La liste des fichiers RTL compilés est dans `tang/build_gpu.tcl` ; la liste des
  fichiers firmware figés est dans `tools/build_gpu.py`. Tout nouveau fichier
  source doit être ajouté aux deux endroits concernés, ainsi qu'aux dépendances
  de `fw_console/Makefile`.

### Firmware seul (vérifier la compilation et la taille)

```sh
make -B -C fw_console MAIN=gpu_diag.c CFLAGS_EXTRA=-DCONSOLE_GPU
```

Sans `MAIN`, le Makefile construit `main.c`, l'ancien écho E2.

### Simulations RTL (Verilator, bancs dans `TESTS/rtl/`)

```sh
# Chemin complet AHB → blitter → DMA → arbitre DDR, comparé à un modèle Python
python3 TESTS/test_gpu_accel.py
# Alpha RGB565, textures et Z16 : références indépendantes et scènes firmware
python3 TESTS/test_gpu_raster.py --out /tmp/console_raster
python3 TESTS/test_gpu_raster_scene.py --out /tmp/console_raster_scene
python3 TESTS/test_gpu_raster_geometry.py --out /tmp/console_raster_geometry
# Extension V1 : cibles, textures 512, matériaux, copie, mipmaps et scènes
python3 TESTS/test_gpu_v1.py --out /tmp/console_v1
python3 TESTS/test_gpu_v1_api.py
python3 tools/render_gpu_v1.py --out /tmp/console_v1_scenes --rtl
# Perspective : ajouter --perspective aux tests de scène et de géométrie ;
# TESTS/test_gpu_perspective.py vérifie séparément la division et son reset.
# Même liste de commandes contre un instantané RTL antérieur
python3 TESTS/test_gpu_accel.py --rtl-root tang/impl/gpu_racer_r2/source --out /tmp/gpu_baseline_comparison

# Un banc isolé : triangles
verilator --binary --timing -Wno-fatal --top-module gpu_triangle_tb \
  --Mdir /tmp/console_gpu_triangle TESTS/rtl/gpu_triangle_tb.sv tang/rtl/video/gpu_triangle.v
/tmp/console_gpu_triangle/Vgpu_triangle_tb

# Un banc isolé : 16 couches + 64 sprites ; ajouter -GTILES=7 pour les décors en tuiles
verilator --binary --timing -Wno-fatal --top-module gpu_layers_tb \
  -GW=800 -GH=480 -GVT=533 -GSPRITES=1 --Mdir /tmp/console_gpu_g4 \
  TESTS/rtl/gpu_layers_tb.sv tang/rtl/video/gpu_scanout.v tang/rtl/video/gpu_line_reader.v \
  tang/rtl/video/gpu_tile_row.v tang/rtl/video/gpu_sprite_cache.v tang/rtl/video/gpu_rgb_reader.v \
  tang/rtl/board/ddr_gpu_arb.v tang/rtl/board/cdc_word.v
/tmp/console_gpu_g4/Vgpu_layers_tb
```

Sans `-GW=800 -GH=480 -GVT=533`, le banc tourne en 64 × 32 en quelques secondes.
Sans `-GTILES`, son journal doit rester identique à `TESTS/gpu_fast_layers_simulation.txt`.

### Tests hôte (sans carte)

```sh
python3 tools/render_racer.py --pose 1      # poses 0..3 ; --cached pour la variante panorama
python3 tools/render_gpu_3d.py --pose 0     # de même render_gpu_layers.py, render_gpu_sprites.py, render_gpu_demo.py
python3 tools/render_gpu_tiles.py --sweep   # décors en tuiles : toutes les poses et positions de défilement
python3 tools/render_gpu_raster.py --out /tmp/console_raster_images --sweep  # 512 angles sous UBSan
python3 TESTS/test_racer_controller.py      # manette Web : Chrome headless + node
```

Les `render_*.py` compilent avec `cc` les **mêmes en-têtes de scène que le
firmware** (`fw_console/*_scene.h`, `*_demo.h`) et produisent l'image et
l'empreinte attendues ; `--hardware-log FICHIER` les compare à un journal UART.
`tools/gpu_compose.py` est la composition de référence commune aux couches,
sprites et tuiles ; elle ne partage aucun code avec le RTL ni le firmware.

### Tests sur carte

```sh
openFPGALoader --busdev-num BUS:DEV -b tangmega138k -m chemin/vers/console_xxx.fs   # chargement SRAM
python3 tools/check_gpu_console.py --wait 20
python3 tools/racer_web.py      # manette du jeu sur http://localhost:8765
```

- Identifier la carte avant de charger (Pro Dock, série FTDI `2023112818` ;
  les numéros bus:dev changent). Chargement en **SRAM** : la flash n'est pas modifiée.
- Attendre la sortie `DONE` du loader avant d'ouvrir la liaison de diagnostic.
- Le port USB CDC `359f:2011` n'admet **qu'un seul programme à la fois**
  (diagnostic, `racer_web.py` ou `play_racer.py`).
- `check_gpu_console.py` choisit les tests G0…G6/FAST d'après la chaîne
  d'identité renvoyée par le firmware ; il faut la faire évoluer avec le jalon.

## Architecture

### Chaîne matérielle

```
AE350 800 MHz ──AHB 80 MHz──> gpu_accel.v (registres + FIFO de commandes, 2 horloges)
                                 └─> blitter.v + gpu_triangle.v ─> gpu_blit_dma.v ─┐
AE350 ──> pont AHB/DDR (adaptateur 128 bits) ──────────────────────────────────────┤
                                                                     ddr_gpu_arb.v ┴─> DDR3 (rafales 256 bits)
DDR3 ─> gpu_line_reader.v (16 couches : images, ou décors en tuiles par gpu_tile_row.v)
     + gpu_sprite_cache.v (64 sprites, BSRAM)
     ─> gpu_scanout.v (composition, palette, échange au retour vertical) ─> LCD 35 MHz
```

- Trois domaines : bus 80 MHz, GPU/DDR UI 75 MHz, LCD 35 MHz. Les **8/8 horloges
  PRIMARY sont utilisées** : aucune nouvelle horloge globale n'est disponible ;
  utiliser des activations synchrones.
- `tang/rtl/video/` contient le GPU ; `tang/rtl/board/` le socle AE350/DDR3
  (`ext_regs.v`, `ddr_gpu_arb.v`, pont AHB) ; `tang/rtl/console_top.v` est le top.
  Les IP USB/DDR3/AE350 comprennent des netlists fournisseur fermées ;
  `tang/rtl/usb/sync_fifo/` contient aussi des sources ouvertes corrigées
  pour les reprises de paquets et sondages vides (voir `TESTS_USB_REPRISE.md`).
- Les `build_e*.tcl`, `console_e0b_*.v`, `console_top_noddr.v`, `ref_demo/` sont
  des jalons historiques E0–E2 conservés comme points de retour.

### Modèle graphique

- Une couche est soit une image, soit un **décor en tuiles** (grille de cases
  de 16 bits + jeu de tuiles 8/16/32 en DDR), composé pendant l'affichage :
  le défilement ne demande aucune commande de dessin.
- **Page, couche et sprite sont trois objets distincts.** Une page est une image
  stockée en DDR (16 emplacements, `0x00800000 + n × 1 Mio`, 384 000 octets
  utiles) ; une couche est un élément de la composition affichée qui référence
  une surface ; un sprite est un objet de 1 à 32 pixels par axe, en cache BSRAM.
- Commande GPU : 8 mots de 32 bits, opcodes 1 à 13 (`enum gpu_opcode` dans
  `fw_console/gpu.h`) pour le chemin indexé ; opcodes 14 à 21 pour le moteur
  RGB565 de `gpu_raster.v`. **Un seul producteur** de commandes à la fois.
- L'index 0 est transparent pour les sprites et les couches avec clé zéro.
  Une couche opaque peut afficher l'index 0. Les tables de
  couches/sprites sont validées atomiquement au retour vertical ; la palette
  n'appartient pas à cette transaction.
- Le moteur RGB565 mélange un alpha uniforme 0..256 par commande, texture
  au plus proche voisin (cache maximal 128 × 128), et Z16 LESS.
  Une page RGB565 ou Z occupe 768 000 octets. `gpu_rgb_reader.v` assure
  l'affichage direct. `a` vérifie quatre poses affines,
  `b` anime, `c` met en pause. Voir `GPU_L13_L15_RGB_DEPTH.md`.
- Extension perspective/composition, statut physique dans `TESTS_GPU_PERSPECTIVE.md` :
  `gpu_perspective.v` calcule exactement floor(UQ/Q) et floor(VQ/Q), avec
  le plan Q de l'opcode 21 et deux pixels anticipés. La composition conserve
  un bit de couverture par pixel et peut superposer les couches indexées
  sur le fond RGB565 ; `gpu_rgb565_scene_submit` présente l'ensemble au vblank.
  Validée sur Pro Dock dans `gpu_perspective_r10`, archivée sous
  `bitstreams/console_gpu_perspective_800.fs` ; cette version conserve tous
  les modes graphiques antérieurs. `d` vérifie les quatre poses avancées et leur somme LCD, `e` les anime,
  `c` arrête. Aucun alpha par texel ni mélange alpha des couches.
- Les origines des plans U/V/Z sont extrapolées à (0,0), en signé 48 bits :
  ne jamais borner l'origine Z à la profondeur stockée de 16 bits. Une face
  omise par le préparateur CPU manque aussi dans sa référence de pixels ;
  le test géométrique indépendant doit passer sur les 512 phases de rotation.
- L'extension GPU V1 (opcodes 22…30, `gpu_v1.v`, `gpu_texture_cache.v`,
  `gpu_copy565.v`) est **validée sur Pro Dock dans `gpu_v1_r31`** et archivée
  sous `bitstreams/console_gpu_v1_800.fs`. Elle ajoute cibles/pas/scissor, cache DDR de textures jusqu'à
  512 × 512, ARGB4444, additif, Gouraud, brouillard, mipmaps explicites,
  copies RGB565 et présentation 400 × 240 agrandie ×2 avec HUD natif.
  Pilote `gpu_v1.h/.c`, ressources `tools/gpu_assets.py`, ABI `GPU_V1.md`.
  `f` vérifie douze poses et mesure le changement de résolution ; `g` anime
  trois scènes de qualification ; `c` met en pause. Deux rechargements HS,
  suite complète, douze poses et 30 minutes d'endurance (58 680 images)
  passent ; les trois scènes sont confirmées visuellement. Preuves et mesures
  dans `TESTS/TESTS_GPU_V1.md`.
  Les transactions DDR V1 sont enregistrées et gardées jusqu'à acceptation ;
  les chemins des opcodes 1…21 conservent leurs cycles. Toute modification
  d'adressage/arrondi se compare à la référence Python indépendante.
- Cohérence de cache CPU/GPU : vider le cache d'une surface écrite par le CPU
  avant de soumettre (`gpu_publish_surface`), attendre `gpu_wait()` puis
  invalider avant de relire sur le CPU une surface écrite par le GPU.
- `DONE` est un compteur de commandes terminées sur 16 bits, à traiter modulo.
- Budget de composition : environ 2 556 cycles à 75 MHz par ligne LCD ; un
  dépassement est compté (lignes manquantes), jamais masqué. Écrire dans
  `0x02c` remet les maxima à zéro pour mesurer une scène.
- Le registre de demande de lecture DDR de `gpu_line_reader.v` alimente
  l'arbitrage : ne rien insérer entre ce registre et `fetch_valid`.
- Conserver le choix du pas RGB565 comme multiplexage/décalage dans
  `gpu_scanout.v`. Une multiplication variable a fait absorber et inverser
  deux registres de changement de page dans un DSP à deux horloges (r1 L13).
  Le build vérifie ce cas avec `check_gpu_scanout_synthesis.py` ; ne pas se
  fier au seul passage du RTL et du timing. Preuve dans `TESTS_GPU_L13_L15.md`.
- Conserver `syn_preserve` sur le registre `packet` de `gpu_v1.v`. Gowin
  1.9.12 a inversé les activations de deux étages C absorbés dans les DSP
  d'adressage de copie et de fins de plages : r20 passe le timing mais rate
  la copie sur carte. `check_gpu_copy_synthesis.py` contrôle les modules
  `gpu_copy565` et `gpu_v1` ; le modèle officiel de primitive reproduit le
  défaut. Exiger également `V1 MEMORY PASS` (copie entre pages, changement
  de cible Z, gardes) avant les références de scènes. Ne pas corriger une
  netlist générée à la main ; preuves dans `TESTS/TESTS_GPU_V1.md`.

### Firmware (`fw_console/`)

- `gpu.c`/`gpu.h` : pilote (registres d'affichage en `0xe9000000`, blitter en
  `0xe9001000`). `gpu_diag.c` : boucle de commandes à un caractère sur UART2
  (115200 8N1 via USB CDC), tout le GPU étant sous `#ifdef CONSOLE_GPU`.
- Scènes et démonstrations dans des en-têtes inclus par `gpu_diag.c`. Les
  `*_scene.h` doivent rester compilables sur l'hôte : ce sont les références
  des comparaisons de pixels.
- Mémoire : 64 Kio ITCM, 64 Kio ILM, 32 Kio DLM (`itcm.ld`). L'extension
  perspective/composition occupe 54 552 octets d'ITCM et 29 128 octets de
  BSS ; les grosses ressources vont en DDR. La compilation utilise `-Os`
  pour conserver toutes les démonstrations et références dans l'ITCM.
- Le firmware V1 validé occupe **63 832 octets d'ITCM** et
  29 184 octets de BSS. Surveiller la limite ITCM de 64 Kio à chaque ajout ;
  les trois scènes sont des charges de qualification, pas trois jeux finis.
- La DDR3 commence à l'adresse 0 : les options
  `-fno-delete-null-pointer-checks -fno-isolate-erroneous-paths-dereference`
  de la toolchain sont indispensables.

## Contraintes propres au dépôt

- **USB : exigence utilisateur du 2 octobre 2026, HS 480 Mbit/s minimum.**
  Les variantes FS sont écartées et ne constituent pas une solution acceptable.
  Conserver leurs anciennes preuves de diagnostic, sans nouvelle compilation
  ou programmation FS sauf instruction explicite ultérieure.

- **Dépendances à des chemins locaux** : `/home/michael/gowin/Gowin_V1.9.12_linux/IDE`,
  `~/gowin/GMD_2025.01_linux` (toolchain RISC-V), `~/ae350/sdk`, et le dépôt voisin
  `/home/michael/logic_analyser_wifi` (`ae350/toolchain.mk`, `ae350/tools/itcm_init.py`).
  Ce dépôt voisin est une référence en lecture seule ; ne pas en importer le
  brochage ni les contraintes.
- Ne jamais modifier les netlists chiffrées ou fermées. Toute source reprise ou
  modifiée est consignée dans `tang/rtl/PROVENANCE.md` et `tang/rtl/video/PROVENANCE.md`.
- Conserver le cœur à 800 MHz et les domaines 80/75/35 MHz. Ne pas relâcher les
  contraintes (`tang/constr/gpu.sdc`) pour faire passer un build : la marge de
  référence n'est que de **+0,139 ns** (`gpu_fast_r2`).
- `tang/constr/gpu.cst` fixe l'emplacement des mémoires BSRAM du build validé.
  Une mémoire renommée ou supprimée arrête le build sur sa ligne : la mettre à
  jour ou la retirer. Une ligne `// @driver module=… instance=… pin=…` fait
  résoudre par `tools/build_gpu.py` le nom d'une cellule que la synthèse
  numérote elle-même ; la copie figée de `gpu.cst` reste identique à la source.
- Le FPGA n'a pas de RAM distribuée : une mémoire est en BSRAM ou en registres.
- Dans `gpu_line_reader.v`, l'état est codé en binaire sur 5 bits et les codes
  libres sont comptés : ajouter un état allonge le décodage des états 8 à 15.
  Les étapes d'une fonction nouvelle vont dans un registre séparé.
- Toute réécriture de logique existante s'accompagne d'une preuve d'équivalence
  (`TESTS/rtl/*_equiv.sv`) et de journaux de simulation identiques au cycle près.
  Exception documentée : les acquittements d'écriture DMA sont enregistrés
  depuis L11/USB r13 ; le banc prouve le décalage exact d'un cycle et mesure
  son coût, avec pixels et transactions conservés (`TESTS_USB_REPRISE.md`).
- Une accélération doit conserver exactement les pixels, les gardes mémoire et
  les opcodes existants ; les bancs comparent à une référence indépendante, à
  réutiliser plutôt qu'à remplacer.
- Livraison d'un changement RTL : simulations ciblées → build dans un dossier
  neuf → timing → ressources et taille du firmware → essai sur carte → archivage
  dans `bitstreams/` du `.fs` validé avec son `.sha256`, journaux dans `TESTS/`
  et fiche `TESTS/TESTS_*.md` mise à jour.
- Un résultat validé sur hôte ou en simulation n'est pas présenté comme validé
  sur carte. Les mesures citées valent pour la séquence testée.
- `tang/impl/gpu_*/` et `fw_console/build/` sont ignorés par git. D'anciens
  fichiers de `tang/impl/pnr/` restent suivis : les changements locaux de
  `cmd.do` et `device.cfg` sont sans rapport avec le GPU et ne doivent pas être
  mêlés aux commits graphiques.
