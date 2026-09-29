# L11 — décors en tuiles matériels

Intégration : 29 septembre 2026. Validation finale : 30 septembre 2026. Cible : Tang Mega 138K Pro Dock, AE350 800 MHz.
Interface et architecture : [GPU_L11_TILEMAPS.md](../ARCHI/GPU_L11_TILEMAPS.md).
Référence de départ : commit `33c6798` (G6), bitstream `console_gpu_fast_800.fs`.

## État

| Étape | État |
|---|---|
| Simulation RTL, 800 × 480 | **Validée** |
| Références firmware et hôte | **Validées** |
| Non-régression en simulation et sur hôte | **Validée**, journaux identiques |
| Placement/routage et timing, build final `gpu_l11_usb_r13` | **Validés**, marge minimale +0,093 ns |
| Essai sur carte | **G0–G6/FAST/L11 validés avec `gpu_l11_usb_r13`** ; 1 088 200 octets USB exacts |
| Contrôle visuel du LCD par Michael | **VALIDÉ sur r13** : « Oui, le décor défile correctement » |

Le bitstream final est [archivé](../bitstreams/console_gpu_l11_800.fs) avec
son [SHA-256](../bitstreams/console_gpu_l11_800.sha256), chargé en SRAM et
validé sur la Pro Dock. Les pertes USB reproduites sur la première version
L11 ont été corrigées dans les FIFO de paquets. Deux essais de 100 séries,
dont un avec composition de tuiles active, vérifient 1 088 200 octets sans
perte. Détails, limites et historique : [TESTS_USB_REPRISE.md](TESTS_USB_REPRISE.md).

## Ce qui est implémenté

- Couches en tuiles 8 × 8, 16 × 16 et 32 × 32, plein écran 800 × 480,
  défilement au pixel, retournements par case, répétition par axe,
  transparence de l'index zéro, 8 192 tuiles par jeu.
- Composition pendant l'affichage : aucune commande de dessin pour défiler.
- Registre de capacité `0x05c` et remise à zéro des maxima par `0x02c`.
- Pilote `gpu_make_tile_layer`, `gpu_tiles_supported`.
- Diagnostic `U` (scène et quatre poses vérifiées), `Y` (pose suivante),
  `W` (défilement animé et mesure).

## Simulation RTL

`rtl/gpu_layers_tb.sv` garde G3 et G4 et ajoute le paramètre `TILES`, qui
vaut aussi le nombre d'images plein écran de la scène de charge.

| Test | Résultat |
|---|---|
| 5 couches de tuiles, 3 images, 64 sprites : tailles 8/16/32, retournements, répétition X, Y et XY, fin de décor, défilement au-delà de 32 767, fenêtres partielles et hors écran | Chaque pixel RGB exact, empreinte exacte, **2 284 / 2 556 cycles** ✓ |
| 4 couches de tuiles plein écran (16, 16, 8, 32), 7 images plein écran, 64 sprites | Pixels exacts, **2 452 / 2 556 cycles**, zéro ligne manquante ✓ |
| 8 couches refusées : adresses non alignées, code de taille 3, grille de 8 cases, étendue de 65 536 pixels en largeur puis en hauteur, grille et jeu de tuiles au-delà du premier Gio | Aucun pixel produit, 8 refus comptés par ligne ✓ |
| Retour à une scène d'images après les tuiles | Empreinte exacte ✓ |
| Remise à zéro des maxima par `0x02c` | Le registre relit le maximum de la scène courante ✓ |
| Registre de capacité `0x05c` | `0x00000d07` ✓ |
| Lectures CPU concurrentes pendant tout le test | 1 797 891, données exactes ✓ |

Journal : [gpu_l11_layers_simulation.txt](gpu_l11_layers_simulation.txt).
La référence du banc peint chaque pixel par une lecture de case et une
lecture d'octet de tuile. Elle n'utilise ni rafales, ni assemblage de mots,
ni ordre des requêtes du matériel.

```sh
verilator --binary --timing -Wno-fatal --top-module gpu_layers_tb \
  -GW=800 -GH=480 -GVT=533 -GSPRITES=1 -GTILES=7 --Mdir /tmp/console_gpu_l11 \
  TESTS/rtl/gpu_layers_tb.sv tang/rtl/video/gpu_scanout.v \
  tang/rtl/video/gpu_line_reader.v tang/rtl/video/gpu_tile_row.v \
  tang/rtl/video/gpu_sprite_cache.v tang/rtl/board/ddr_gpu_arb.v \
  tang/rtl/board/cdc_word.v
/tmp/console_gpu_l11/Vgpu_layers_tb
```

### Budget de ligne mesuré en simulation

Couches plein écran, sans sprite. Étude faite avec des copies du banc.

| Scène | Cycles sur 2 556 |
|---|---:|
| Aucune couche active | 259 |
| 1 couche de tuiles 32 × 32 | 437 |
| 1 couche de tuiles 16 × 16 | 517 |
| 1 couche de tuiles 8 × 8 | 658 |
| 4 couches de tuiles 32 × 32 | 960 |
| 4 couches de tuiles 16 × 16 | 1 271 |
| 4 couches de tuiles 8 × 8 | 1 842 |
| 8 couches de tuiles 16 × 16 | 2 270 |
| 6 couches de tuiles 8 × 8 | Dépassement, signalé par le banc |

Ces chiffres sont ceux du banc, avec sa contre-pression DDR. La charge
réelle reste à mesurer sur la carte.

## Références firmware et hôte

Trois calculs indépendants de l'image existent : le banc SystemVerilog, la
référence C du firmware (`reference_tile_row`) et la composition Python
(`tools/gpu_compose.py`). L'outil hôte exécute la scène et la référence du
firmware sans modification, sous UBSan, avec la mémoire de la scène placée
à son adresse DDR, puis compare leur empreinte à celle de Python.

| Pose | Contenu | Empreinte |
|---|---|---|
| [0](images/gpu_l11_pose0_expected.png) | Montagnes 32 × 32 répétées, terrain 16 × 16, bandeau 8 × 8, image, 8 sprites | `4fe83fa7` |
| [1](images/gpu_l11_pose1_expected.png) | Défilements non alignés sur les tuiles | `54fe6592` |
| [2](images/gpu_l11_pose2_expected.png) | Terrain en fin de grille, fond au bord haut | `997e660c` |
| [3](images/gpu_l11_pose3_expected.png) | Fenêtres en partie hors écran, terrain au-delà de sa grille, défilement 40 000 | `633ebfa6` |

| Test | Résultat |
|---|---|
| 4 poses : référence firmware contre composition Python | Empreintes identiques ✓ |
| 9 positions de défilement de l'animation : 1, 5, 6, 15, 16, 17, 208, 415, 416 | Empreintes identiques ✓ |
| UBSan sur la scène et la référence du firmware | Aucune erreur ✓ |

```sh
python3 tools/render_gpu_tiles.py --sweep
python3 tools/render_gpu_tiles.py --pose 1
```

## Non-régression

| Test | Référence | Résultat |
|---|---|---|
| 16 couches et 64 sprites, 800 × 480 | `gpu_fast_layers_simulation.txt` | Journal identique : 2 341, 5 889 et 2 898 cycles, 1 124 984 lectures CPU ✓ |
| 16 couches sans sprite, 800 × 480 | RTL du commit `33c6798`, même banc | Journal identique : 1 991 cycles, 613 265 lectures CPU ✓ |
| Blitter, 541 commandes | `gpu_l11_usb_blitter_equivalence.txt` | Pixels et gardes exacts, 95 449 écritures DDR ; un cycle ajouté à chaque fin de transfert DMA (+1,73 % de cycles sur ce banc) ✓ |
| Triangles, 255 triangles | `gpu_fast_triangle_simulation.txt` | Journal identique ✓ |
| Arbitre DDR GPU | `gpu_g4_arb_simulation.txt` | Journal identique ✓ |
| Rendus hôte G2, G3, G4, G5 et course | Images de `TESTS/images/`, journal `gpu_fast_uart.txt` | Images identiques octet pour octet, empreintes identiques au journal de la carte ✓ |
| Manette Web | `test_racer_controller.py` | PASS ✓ |

Les journaux identiques au cycle près montrent qu'une couche d'image suit
le même chemin et prend le même temps qu'avant L11.

### Preuves d'équivalence des réécritures

| Logique réécrite | Preuve | Résultat |
|---|---|---|
| Fenêtre vide d'une couche ou d'un sprite | `rtl/gpu_clip_equiv.sv`, toutes les positions, largeurs critiques et aléatoires, 800 et 64 pixels | 6 815 744 cas identiques ✓ |
| État « file pleine » de `ddr_ui_adapt` et `ddr_arb` | `rtl/ddr_tag_queue_equiv.sv`, exhaustif | 4 096 cas identiques ✓ |

```sh
verilator --binary --timing -Wno-fatal --top-module gpu_clip_equiv \
  --Mdir /tmp/console_clip_equiv TESTS/rtl/gpu_clip_equiv.sv && /tmp/console_clip_equiv/Vgpu_clip_equiv
verilator --binary --timing -Wno-fatal --top-module ddr_tag_queue_equiv \
  --Mdir /tmp/console_tq_equiv TESTS/rtl/ddr_tag_queue_equiv.sv && /tmp/console_tq_equiv/Vddr_tag_queue_equiv
```

`ddr_subsys` contient l'IP DDR3 et n'a pas de banc dans ce dépôt : la
réécriture de `ddr_ui_adapt` et `ddr_arb` est couverte par les preuves
ci-dessus et celles de la fiche USB, ainsi que par les tests mémoire `D`
et `M` réussis sur la carte.

## Placement/routage initial, build `gpu_l11_r14` (historique)

| Mesure | Résultat |
|---|---|
| Chemins détaillés | 110, tous positifs ✓ |
| Marge minimale | **+0,140 ns** (maintien) ; pire chemin d'établissement +0,339 ns ✓ |
| Lignes TNS établissement/maintien | 24, toutes à zéro ✓ |
| Fréquences | Cœur 800 MHz, AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz, inchangées ✓ |
| Contraintes d'horloge `gpu.sdc` | Inchangées ✓ |
| Sources figées | 79 fichiers vérifiés avant la correction USB ✓ |
| SHA-256 du bitstream | `96e045a9bd98a66460dcc2f08bbf100026aff2afd5458db8a073d25e7e4c419d` |

Fréquence maximale du domaine graphique : 76,960 MHz pour 75,002 MHz.

Occupation de **toute la console** :

| Ressource | `gpu_fast_r2` | `gpu_l11_r14` | Variation |
|---|---:|---:|---:|
| Logique | 26 332 | 29 334 / 138 240 | +3 002 |
| Registres | 19 080 | 21 166 / 139 140 | +2 086 |
| BSRAM | 203 | 217 / 340 | +14 |
| DSP | 17 | 17 / 298 | 0 |
| Horloges PRIMARY | 8 | 8 / 8 | 0 |

Le module `gpu_tile_row` seul compte 1 963 LUT, 1 904 registres et 7 BSRAM
dans le rapport de synthèse. Le firmware occupe 53 160 octets d'image ITCM
sur 65 536, avec 28 920 octets de BSS.

## Difficultés rencontrées

Treize builds n'ont pas été retenus. Aucun n'a été chargé sur une carte.

| Build | Constat | Suite donnée |
|---|---|---|
| r1 | Arrêt avant placement : la synthèse renomme la cellule `n147_s7` visée par une contrainte | Nom repris de la netlist |
| r2 | −0,804 ns, compteur de couches refusées | Refus enregistré dans un registre, compté au cycle suivant |
| r2 | −0,311 ns, décision de fusion | Décision mise en registre, même cycle |
| r3 | −2,817 ns, aiguillage des demandes de lecture devant l'arbitrage DDR3 | Demande dans un registre sans logique derrière |
| r4, r6 | Arrêt : la cellule change encore de nom | `tools/build_gpu.py` résout le nom à chaque build |
| r5 | −1,993 ns, l'acquittement DDR3 choisissait l'adresse suivante | Prochaine demande préparée dans un registre |
| r7 | 125 chemins en défaut avec le placement « priorité timing » | Option retirée |
| r8 | −2,317 ns, signal de bloc décodé de l'état | Étapes des tuiles hors du registre d'état ; indicateur en registre |
| r9, r10 | −0,287 à −1,833 ns, rejet d'une couche | Rejet préparé un état plus tôt |
| r11 | Table des cases en registres : +4 000 registres | Ce FPGA n'a pas de RAM distribuée ; retour à la BSRAM |
| r12 | −0,782 ns, file du pont DDR3, logique non modifiée | Seize options de l'outil essayées sans effet |
| r13 | −2,723 ns après copie locale du reset du pont DDR3 | Changement retiré |
| r14 | **Timing validé** | — |

Constat de fond : dans le domaine à 75 MHz, plusieurs chemins anciens
(blitter, diviseurs des triangles, arbitrage, pont DDR3) sont à moins d'une
nanoseconde de la limite. Chaque placement en faisait ressortir un
différent. Le build validé a été rejoué et donne exactement +0,139 ns : le
placement est reproductible, mais très sensible à une petite modification.
La solution retenue fixe les emplacements des mémoires du build validé.

Trente-quatre variantes ont été compilées en parallèle hors du dépôt pour
comparer les options de l'outil et les corrections ; deux passaient le
timing. Celle qui est retenue cumule l'ancrage des mémoires et le registre
d'entrée des tuiles.

Ce registre d'entrée coûte environ cinq cycles par couche de tuiles. La
scène de charge du banc est passée de 8 à 7 images plein écran à côté des
quatre couches de tuiles.

## Validation finale sur carte — `gpu_l11_usb_r13`

[Journal complet](gpu_l11_uart.txt), [timing](gpu_l11_timing.txt),
[ressources](gpu_l11_resources.txt), [manifeste](gpu_l11_sources.json).
Pro Dock FTDI `2023112818`, chargement SRAM terminé (`DONE`), cœur 800 MHz,
bus 80 MHz, GPU/DDR UI 75 MHz et LCD 35 MHz.

| Mesure | Résultat final |
|---|---|
| Timing | 110 chemins détaillés positifs, établissement +0,093 ns, maintien +0,138 ns, TNS nul |
| Fréquence maximale du domaine GPU | 75,530 MHz pour une contrainte à 75,002 MHz |
| Logique, console entière | 30 101 / 138 240 (environ 22 %) |
| Registres, console entière | 21 530 / 139 140 (environ 16 %) |
| BSRAM / DSP / horloges PRIMARY | 217 / 340 ; 17 / 298 ; 8 / 8 |
| Image ITCM / BSS | 53 160 / 28 920 octets |
| DDR3, G0–G6, FAST | Tous réussis |
| Poses L11 0/1/2/3 | `4fe83fa7` / `54fe6592` / `997e660c` / `633ebfa6`, exactes |
| Maximum de ligne, poses 0/1/2/3 | 952 / 956 / 955 / 812 cycles |
| Défilement, séries de 240 images | 55,06 à 55,17 images/s, zéro commande de dessin |
| Défilement avec trafic CPU DDR | 55,36 images/s, maximum 1 105/2 556 cycles |
| Refus / lignes manquantes / erreurs DDR | 0 / 0 / 0 |
| Course, modes original et cached, 240 images chacun | 55,11 images/s dans les deux modes ; GPU maximal 9,851 / 10,445 ms |
| USB avant les diagnostics, 100 séries | 544 100 octets exacts |
| USB après les diagnostics, avec tuiles actives, 100 séries | 544 100 octets exacts, maximum de ligne 952, aucune ligne manquante |

Le délai supplémentaire d'un cycle à la fin des écritures DMA est volontaire
et testé. La cadence de la course reste celle du panneau. Les autres
réécritures conservent les cycles et les valeurs des interfaces comparées.
[Preuves détaillées](TESTS_USB_REPRISE.md).

La comparaison indépendante Python/firmware/carte est conservée dans
[gpu_l11_usb_host_comparison.txt](gpu_l11_usb_host_comparison.txt). La
simulation finale 800 × 480, avec comparaison des lectures AHB, est dans
[gpu_l11_usb_layers_simulation.txt](gpu_l11_usb_layers_simulation.txt).

Bitstream : [console_gpu_l11_800.fs](../bitstreams/console_gpu_l11_800.fs).
SHA-256 : `163203fdb7665e74c7df3e067d1660625a545bb46a851df621c7c2734d4e800d`.

Pour reproduire après identification de la bonne Pro Dock et chargement :

```sh
python3 tools/check_usb_stress.py --rounds 100 --out /tmp/l11_usb_before
python3 tools/check_gpu_console.py --wait 20 > /tmp/l11_uart.txt
python3 tools/render_gpu_tiles.py --sweep --hardware-log /tmp/l11_uart.txt
python3 tools/check_usb_stress.py --rounds 100 --tiles --out /tmp/l11_usb_after
```

Le test termine avec la scène en tuiles affichée. `W` relance son défilement,
`Y` passe à la pose suivante et `U` réinitialise la démonstration.
