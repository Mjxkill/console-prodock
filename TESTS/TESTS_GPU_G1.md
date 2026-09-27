# G0/G1 — DDR3 partagée et premier framebuffer LCD

Validation du 27 septembre 2026, Tang Mega 138K Pro Dock FPG676.

## Résultat

- CPU **800 MHz**, bus AHB/APB **80 MHz**, interface DDR3 **75 MHz**,
  LCD **35 MHz**. Aucun ajout d'horloge globale : toujours 8/8 PRIMARY.
- Lecture graphique native **256 bits**, partagée avec le pont mémoire CPU.
- Une surface affichée **800 × 480, 8 bits indexés**, palette RGB666 de
  256 couleurs, deux tampons de ligne et deux pages de démonstration en DDR3.
- Changement de page appliqué au retour vertical, sans réécrire l'image affichée.
- DDR3, écho USB, sommes des deux pages et quatre permutations : **PASS**.
  Aucune ligne manquante pendant cinq tests mémoire CPU concurrents de 1 Mio.
- Contrôle visuel confirmé par Michael : image correcte, cadre blanc et
  rectangle rouge, sans décalage ni scintillement signalé.

Les 16 couches, sprites, blitter, texte et triangles restent les étapes suivantes.
G1 utilise un lecteur avec une requête DDR en vol ; il ne mesure pas encore
le débit nécessaire à 16 couches. Le port graphique est en lecture seule ;
les écritures natives du blitter seront ajoutées et testées en G2.

## Correction mémoire du firmware

Le linker historique `itcm_all.ld` plaçait aussi les données modifiables et
la pile dans l'ITCM de démarrage. L'écho E2 fonctionnait, mais la maintenance
du D-cache provoquait une exception et la désactivation du cache au démarrage
empêchait le programme de fonctionner normalement.

`fw_console/itcm.ld` conserve le code et l'image initiale dans l'ITCM à
`0x80000000`, place les données/BSS dans l'ILM à `0xA0000000` et la pile en DLM
à `0xA0200000` (zone de 32 Kio). Le BSP copie les données initialisées via
`CFG_XIP`. Les tests sans cache et avec vidage/invalidation passent après
cette correction. Le cœur reste à 800 MHz.

Le diagnostic D vérifie les 64 positions d'octet et 32 positions de demi-mot
de deux rafales DDR, avec contrôle des voisins, cache de données désactivé.
Il vérifie ensuite des adresses distinctes de 0 à `1 << 29` dans l'espace
configuré de 1 Gio. Ce test d'adresses ne constitue pas un test exhaustif
de chaque octet du Gio. Enfin, trois passes de 1 Mio (adresse, inverse,
xorshift) sont écrites puis relues après vidage/invalidation du cache.

## Interface et cohérence

Registres 32 bits à `0xE9000000` ; les adresses de page sont en **octets**.

| Décalage | Fonction |
|---|---|
| `0x00` | Identifiant `0x47505531` (`GPU1`). |
| `0x04` | Adresse de travail de la page, alignée sur 32 octets, espace DDR de 1 Gio. |
| `0x08` | Activation de travail, bit 0. |
| `0x0C` | Écrire 1 pour valider adresse/activation ensemble au retour vertical ; lire bit 0 = validation en attente. |
| `0x10` | Adresse active, image synchronisée vers le bus. |
| `0x14` | Activation active. |
| `0x18` | Compteur de trames LCD. |
| `0x1C` | Compteur de lignes non prêtes à l'échéance. |
| `0x20` | Somme 32 bits des mots de la dernière image lue en DDR. |
| `0x24` | Compteur des lectures ayant atteint la dernière ligne. |
| `0x400 + 4*i` | Palette en écriture : RGB666 dans les bits 17:0. |

Pas de ligne fixe : 800 octets. La fenêtre active contient exactement
800 × 480 pixels. Totaux : 1193 × 533 cycles à 35 MHz, soit environ
**55 images/s nominales**, pas une mesure de fréquence au connecteur LCD.

Le CPU prépare une page hors affichage, exécute
`ae350_dcache_flush_range(base, 800 * 480)` puis une barrière `fence`, et
soumet l'adresse et l'activation. Les paramètres restent stables jusqu'à
l'acquittement du domaine pixel. Une deuxième validation attend la précédente.
La palette n'est pas doublée : la programmer avant l'activation pour éviter
une modification des couleurs en milieu de trame.

Le lecteur précharge la ligne suivante dans l'autre banque. Les requêtes et
acquittements entre domaines utilisent des bascules synchronisées et des
données maintenues stables. Une ligne en retard est noire en entier, comptée
et identifiée par son numéro de trame/ligne ; elle ne décale pas les suivantes.
La somme 32 bits sert au diagnostic et ne remplace pas une comparaison pixel
à pixel ni un CRC sensible à toutes les permutations de mots.

Les interfaces d'acquisition héritées restent inactives. Leur suppression
du wrapper et l'extension de l'arbitrage aux écritures du blitter restent à faire.

## Commandes USB du firmware G1

Firmware `fw_console/gpu_diag.c`, option C `CONSOLE_GPU`.
Les commandes sont des octets ASCII, sans nécessité de retour à la ligne.

| Commande | Action |
|---|---|
| `?` | Identifie firmware G1 et horloges. |
| `D` | Test DDR destructif : à exécuter avant `V`. |
| `E` + longueur uint16 little-endian + données | Écho binaire exactement de la longueur annoncée. |
| `V` | Prépare deux pages à `0x00800000` et `0x00900000`, programme la palette, affiche la première. |
| `F` | Permute les pages au retour vertical ; utiliser après `V`. |
| `S` | Affiche adresse active, compteurs, somme et état de validation. |
| `M` | Test CPU de 1 Mio à `0x00200000`, sans toucher les pages affichées. |

La première mire a un dégradé coloré, un cadre blanc de quatre pixels et un
rectangle central rouge. La seconde inverse des composantes de couleur et
présente un rectangle vert. La séquence automatique revient à la première.

## Vérifications

Simulation Verilator :

- `ddr_gpu_arb_tb.sv` : file de 16 lectures pleine, refus de commandes,
  retours CPU/GPU, lecture et retour simultanés, données/masques d'écriture
  inchangés malgré les attentes indépendantes de l'IP. 154 lectures, 19 écritures.
- `gpu_scanout_tb.sv` : comparaison de chaque pixel après palette, limites
  exactes, alternance des banques, somme, permutation au retour vertical,
  panne mémoire sur plusieurs trames et reprise. PASS en 64 × 4 puis
  **800 × 480**, avec 2 996 221 lectures CPU concurrentes dans ce dernier banc.

```sh
verilator --binary --timing -Wno-fatal --top-module ddr_gpu_arb_tb \
  --Mdir /tmp/console_gpu_arb_tb TESTS/rtl/ddr_gpu_arb_tb.sv tang/rtl/board/ddr_gpu_arb.v
/tmp/console_gpu_arb_tb/Vddr_gpu_arb_tb

verilator --binary --timing -Wno-fatal --top-module gpu_scanout_tb \
  -GW=800 -GH=480 -GHT=1193 -GVT=533 -GHSTART=182 -GVSTART=8 -GHSYNC=210 -GVSYNC=45 \
  --Mdir /tmp/console_gpu_full_tb TESTS/rtl/gpu_scanout_tb.sv \
  tang/rtl/video/gpu_scanout.v tang/rtl/board/ddr_gpu_arb.v tang/rtl/board/cdc_word.v
/tmp/console_gpu_full_tb/Vgpu_scanout_tb
```

Sur carte, `python3 tools/check_gpu_console.py` :

- Identification du CDC par VID/PID `359f:2011` ; écho exact de 5 441 octets.
- Masques, adresses et trois passes DDR : zéro erreur.
- Pages : sommes `c5c4fc70` et `a3a2ec50` attendues par le CPU et relues par le GPU.
- Quatre permutations, cinq tests CPU concurrents de 1 Mio : zéro erreur,
  compteurs de trames en progression, **underflows = 0**.

## Construction et artefact

```sh
python3 tools/build_gpu.py --name gpu_g1_nouveau
```

Le nom désigne un nouveau dossier sous `tang/impl/`. Le script recompile le
firmware, régénère obligatoirement la netlist AE350 avec les octets ITCM,
copie les sources utilisées, synthétise/place/route avec Gowin 1.9.12 et
contrôle les marges détaillées ainsi que le TNS. `sources.json` contient les
empreintes des entrées ; les journaux et rapports restent dans ce dossier.
`tang/build_gpu.tcl` sélectionne le GPU ; `build_e2.tcl` garde la mire E2.

Build final : `tang/impl/gpu_g1_r3/`, bitstream `console_gpu_g1_r3.fs`, archivé
dans `bitstreams/console_gpu_g1_800.fs` avec son fichier `.sha256`.
Le journal du test matériel est conservé dans `TESTS/gpu_g1_uart.txt`.
Timing : 24 lignes setup/hold du résumé TNS sans violation ; 110 chemins
détaillés, marge minimale **+0,140 ns**.
Utilisation totale : 10 710 éléments logiques, 10 460 registres,
109/340 BSRAM, 8/8 horloges PRIMARY.

SHA-256 : `6da6971750a554925ce0ca48533d9524546d0a7a3a10827153c4e7529d0c8eaf`.
Chargement **SRAM** sur le FTDI **2023112818**, identifié en USB `3:12` lors
de ce test. L'autre carte, FTDI `2025041420`, n'est pas concernée.
La référence E2 reste archivée dans `bitstreams/console_e2_uart_800_echo.fs`.
