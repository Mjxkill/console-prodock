# IP des deux installations Gowin — 16 octobre 2026

Comparaison locale des métadonnées `*.ipspec` et des empreintes SHA-256
des fichiers sous `ipcore/*/data`. Le détail est dans
[`ip_versions_20261016.json`](ip_versions_20261016.json).

| IP du catalogue | IDE V1.9.12 | IDE V1.9.12.03 |
|---|---:|---:|
| DDR3 Memory Interface | 5.9 | 6.0 |
| USB 2.0 SoftPHY | 3.4 | 3.5 |
| USB 2.0 Device Controller | 3.2 | 3.3 |
| RISC-V AE350 SOC | 1.2 | 1.2 |
| FIFO | 1.1 | 1.1 |
| FIFO HS | 1.0 | 1.0 |
| PLL_ADV | 1.0 | 1.0 |

Les trois fichiers `data` de FIFO, FIFO HS et PLL_ADV sont identiques,
octet pour octet, entre ces installations. Les sept fichiers du répertoire
DDR3 diffèrent, y compris les sources du contrôleur au rapport 1:4 utilisé
ici. Des fichiers chiffrés différents ne constituent pas à eux seuls une
description des changements fonctionnels.

AE350 conserve 17 fichiers identiques sur 18. La seule différence observée
est `data/ddr3_default_settings/gwmc_param.v` : `DQ_WIDTH` passe de 32 à 16.
Cela concerne ce fichier de paramètres par défaut des installations ; ce
n’est pas une mesure de largeur du contrôleur DDR standalone de la console.

## Ce que les builds utilisent effectivement

- N41r1_newide route avec V1.9.12.03 la netlist synthétisée avec V1.9.12.
  Il ne régénère aucune IP.
- N42syn synthétise avec V1.9.12.03 et régénère le wrapper AE350 à partir
  de son catalogue 1.2 et de la configuration figée du projet.
- Dans N42syn, les fichiers générés DDR standalone, SoftPHY USB et
  contrôleur USB sont **strictement identiques à ceux de N41syn**. Le
  compilateur récent ne remplace pas automatiquement une netlist d’IP
  conservée dans les sources.
- Le fichier DDR conservé indique une génération par V1.9.12 ; les deux
  fichiers USB conservés indiquent V1.9.10.03. Ces numéros d’outil ne sont
  pas des numéros de version d’IP.
- Les FIFO CPU/DDR du profil Neo sont du RTL du projet ; leur stockage
  en registres est inchangé entre N41 et N42. Elles ne correspondent pas
  à une nouvelle invocation du générateur FIFO du catalogue.

**N42 n’est donc pas un essai du contrôleur DDR3 6.0 ni des nouvelles IP
USB.** Tester la DDR3 6.0 demande une régénération explicite, avec les mêmes
paramètres mémoire et un profil de comparaison séparé de la référence
Pro Dock. Aucun succès ou échec matériel de cette nouvelle IP n’est établi.

## Essai DDR6 ajouté ensuite

`neo_ddr6_ip_r1` a maintenant généré la DDR3 6.0 via le flux Tcl officiel.
Les 40 ports et les paramètres mémoire existants sont vérifiés identiques.
Le profil optionnel `neo-ddr6-fifo-registers` est utilisé par N43syn. Les
nouveaux paramètres et le choix BSRAM du générateur sont documentés dans
`generation.json`, sous `tang/boards/neo/ddr6/`. N42 conserve son rôle de
comparaison avec l’ancienne IP. Cela ne change pas les résultats matériels
antérieurs et ne constitue pas encore une qualification DDR6 sur carte.

## Comparaison documentaire DDR3 5.9 / 6.0 — 17 octobre 2026

Les numéros 5.9 et 6.0 sont ceux du catalogue IP, pas ceux des guides.
Documents comparés : IPUG281-2.5E et IPUG281-2.6E, métadonnées des deux
installations et configuration effectivement générée. Le guide récent
décrit AXI4 et les choix de buffers ; ce n’est pas un historique exhaustif
des changements internes de l’IP entre 5.9 et 6.0.

- [IPUG281-2.5E, notamment §4.4.3–4.4.4](https://www.gowinsemi.com/upload/database_doc/2009/document/6820d9f57274d.pdf)
- [IPUG281-2.6E](https://cdn.gowinsemi.com.cn/IPUG281E.pdf)

Le PDF 2.5E n’a pas pu être téléchargé intégralement : le serveur a renvoyé
un corps vide. Les sections reset/PLL ont été comparées au texte indexé de
l’URL officielle. Le fichier local vide `ddr59_60_docs/IPUG281_2.5E.pdf`
n’est pas une copie exploitable du document. Le guide 2.6E est accessible
par le lecteur web. Les deux aides HTML installées sont identiques octet
pour octet ; elles ne documentent pas la migration. Les notes RN100
consultées ne donnent pas de détail de cette migration ; RN281 disponible
est une ancienne note du design de référence, pas une note de l’IP 6.0.

| Sujet | Constat vérifié |
|---|---|
| Interface native | Les 40 ports générés et les 35 paramètres préexistants sont conservés. |
| AXI4 | Nouvelle option du catalogue 6.0, désactivée dans notre génération. |
| Buffers contrôleur | Options MC_BSRAM / MC_SSRAM / MC_REG ajoutées au catalogue ; BSRAM par défaut. |
| Configuration générée | Ajout de `EBR_BASED` ; quatre nouveaux paramètres dont les identifiants AXI et `BURST_LEN`. Le burst physique reste `BURST_MODE="8"`. |
| Reset | Les deux guides demandent une libération de `rst_n` synchronisée sur `clk`, puis l’attente du véritable `pll_lock` par Sync_mod. |
| PLL 138K | Les deux guides relient `pll_stop` directement à `enclk2`. |
| Correctif FIFO GW5AST-138 | Aucun correctif spécifique identifié dans les documents consultés. |

La présence nouvelle de `EBR_BASED` ne démontre pas un changement de
technologie mémoire dans notre cas : l’inventaire des netlists routées N38
et N45r3 retrouve, sous `u_ip`, les mêmes types et noms d’instances mémoire
(16 SDPX9B et 16 SDPB, y compris les instances auxiliaires du générateur).
Ce sont des comptes de primitives dans les fichiers `.vo`, pas un compte
de blocs physiques indépendants. Les buffers de l’ancienne IP utilisaient
donc déjà des primitives mémoire bloc. Cette égalité ne prouve aucune
identité des connexions, resets, contrôles ou placements. Inventaire :
[`ddr59_60_docs/ddr_memory_cells.json`](ddr59_60_docs/ddr_memory_cells.json).

Deux points d’intégration préexistants restent à vérifier :

1. `ae350_soc.v` connecte `DDR3_RSTN` à `1'b1`, transmis à `rst_n` de l’IP.
   Le RTL ne fournit donc pas de séquence de reset explicite ; le démarrage
   dépend de l’initialisation interne/GSR. Cela ne démontre pas à lui seul
   une panne, ni une exigence nouvelle de la version 6.0.
2. La configuration conserve `Memory_Clock=400` et `tCK=2500 ps`, tandis
   que la PLL et le rapport STA N45r3 indiquent environ 300,03 MHz mémoire
   et 75,002 MHz UI. Le guide demande que la fréquence configurée corresponde
   à la fréquence mémoire. Cette incohérence doit être réconciliée ; son
   effet exact sur les compteurs internes chiffrés n’a pas été mesuré.

N45r3 a depuis été essayé sur carte : programmation DONE, mais examen du
cœur AE350 impossible ; aucun test DDR de ce build n’a commencé. N38 a été
restauré. Les différences multiples entre builds empêchent d’attribuer ce
résultat à la seule version d’IP. Avant un essai de buffers REG/BSRAM, il
faut observer indépendamment PLL, reset et fin de calibration.
