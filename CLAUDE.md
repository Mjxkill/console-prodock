# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Console de jeux sur **Tang Mega 138K Pro Dock** (GW5AST-138, boîtier FPG676) :
CPU AE350 (RISC-V) à 800 MHz, GPU maison en Verilog, DDR3 partagée CPU/GPU,
LCD 800 × 480 en pixels indexés 8 bits + palette. Documentation, fiches de test
et messages de commit sont rédigés **en français** (`G5 : … validés à 800 MHz`).

Documents de référence, à lire avant toute évolution :

- `ARCHI/ARCHI_V2_CONSOLE_JEUX.md` : périmètre et état des jalons G0–G7
  (`ARCHI_V1.md` est remplacé ; les fonctions d'acquisition de signaux sont hors périmètre).
- `ARCHI/FEUILLE_DE_ROUTE_CONSOLE.md` : lots restants L00–L18, contraintes, budgets.
- `ARCHI/GPU_G*_REGISTRES.md`, `GPU_G5_TRIANGLES_3D.md`, `GPU_SPANS_DDR256.md`,
  `JEU_COURSE.md` : contrats de registres, d'opcodes et protocole USB du jeu.
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
# Même liste de commandes contre un instantané RTL antérieur
python3 TESTS/test_gpu_accel.py --rtl-root tang/impl/gpu_racer_r2/source --out /tmp/gpu_baseline_comparison

# Un banc isolé : triangles
verilator --binary --timing -Wno-fatal --top-module gpu_triangle_tb \
  --Mdir /tmp/console_gpu_triangle TESTS/rtl/gpu_triangle_tb.sv tang/rtl/video/gpu_triangle.v
/tmp/console_gpu_triangle/Vgpu_triangle_tb

# Un banc isolé : 16 couches + 64 sprites
verilator --binary --timing -Wno-fatal --top-module gpu_layers_tb \
  -GW=800 -GH=480 -GVT=533 -GSPRITES=1 --Mdir /tmp/console_gpu_g4 \
  TESTS/rtl/gpu_layers_tb.sv tang/rtl/video/gpu_scanout.v tang/rtl/video/gpu_line_reader.v \
  tang/rtl/video/gpu_sprite_cache.v tang/rtl/board/ddr_gpu_arb.v tang/rtl/board/cdc_word.v
/tmp/console_gpu_g4/Vgpu_layers_tb
```

### Tests hôte (sans carte)

```sh
python3 tools/render_racer.py --pose 1      # poses 0..3 ; --cached pour la variante panorama
python3 tools/render_gpu_3d.py --pose 0     # de même render_gpu_layers.py, render_gpu_sprites.py, render_gpu_demo.py
python3 TESTS/test_racer_controller.py      # manette Web : Chrome headless + node
```

Les `render_*.py` compilent avec `cc` les **mêmes en-têtes de scène que le
firmware** (`fw_console/*_scene.h`, `*_demo.h`) et produisent l'image et
l'empreinte attendues ; `--hardware-log FICHIER` les compare à un journal UART.

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
DDR3 ─> gpu_line_reader.v (16 couches) + gpu_sprite_cache.v (64 sprites, BSRAM)
     ─> gpu_scanout.v (composition, palette, échange au retour vertical) ─> LCD 35 MHz
```

- Trois domaines : bus 80 MHz, GPU/DDR UI 75 MHz, LCD 35 MHz. Les **8/8 horloges
  PRIMARY sont utilisées** : aucune nouvelle horloge globale n'est disponible ;
  utiliser des activations synchrones.
- `tang/rtl/video/` contient le GPU ; `tang/rtl/board/` le socle AE350/DDR3
  (`ext_regs.v`, `ddr_gpu_arb.v`, pont AHB) ; `tang/rtl/console_top.v` est le top.
  `tang/rtl/usb/`, `ddrtest/` et les IP DDR3/AE350 sont des netlists fournisseur.
- Les `build_e*.tcl`, `console_e0b_*.v`, `console_top_noddr.v`, `ref_demo/` sont
  des jalons historiques E0–E2 conservés comme points de retour.

### Modèle graphique

- **Page, couche et sprite sont trois objets distincts.** Une page est une image
  stockée en DDR (16 emplacements, `0x00800000 + n × 1 Mio`, 384 000 octets
  utiles) ; une couche est un élément de la composition affichée qui référence
  une surface ; un sprite est un objet de 1 à 32 pixels par axe, en cache BSRAM.
- Commande GPU : 8 mots de 32 bits, opcodes 1 à 11 (`enum gpu_opcode` dans
  `fw_console/gpu.h`). **Un seul producteur** de commandes à la fois.
- L'index 0 est transparent ; il n'y a pas de mélange alpha. Les tables de
  couches/sprites sont validées atomiquement au retour vertical ; la palette
  n'appartient pas à cette transaction.
- Cohérence de cache CPU/GPU : vider le cache d'une surface écrite par le CPU
  avant de soumettre (`gpu_publish_surface`), attendre `gpu_wait()` puis
  invalider avant de relire sur le CPU une surface écrite par le GPU.
- `DONE` est un compteur de commandes terminées sur 16 bits, à traiter modulo.
- Budget de composition : environ 2 556 cycles à 75 MHz par ligne LCD ; un
  dépassement est compté (lignes manquantes), jamais masqué.

### Firmware (`fw_console/`)

- `gpu.c`/`gpu.h` : pilote (registres d'affichage en `0xe9000000`, blitter en
  `0xe9001000`). `gpu_diag.c` : boucle de commandes à un caractère sur UART2
  (115200 8N1 via USB CDC), tout le GPU étant sous `#ifdef CONSOLE_GPU`.
- Scènes et démonstrations dans des en-têtes inclus par `gpu_diag.c`. Les
  `*_scene.h` doivent rester compilables sur l'hôte : ce sont les références
  des comparaisons de pixels.
- Mémoire : 64 Kio ITCM, 64 Kio ILM, 32 Kio DLM (`itcm.ld`). L'image de
  référence occupe 48 112 octets d'ITCM ; les grosses ressources vont en DDR.
- La DDR3 commence à l'adresse 0 : les options
  `-fno-delete-null-pointer-checks -fno-isolate-erroneous-paths-dereference`
  de la toolchain sont indispensables.

## Contraintes propres au dépôt

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
