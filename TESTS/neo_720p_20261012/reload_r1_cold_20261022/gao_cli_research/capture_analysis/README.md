# Comparaison indépendante des lectures GAO R10

Analyse locale des trois CSV conservés sous `r10_initial_read_01..03`.
Aucun accès carte, outil Gowin exécuté ou fichier brut modifié. Le script
`compare_captures.py` vérifie les 20 colonnes contre le XML GAO, les 4 096
indices, les valeurs binaires, les SHA et l'identité des bruts après analyse.

La [revue complémentaire AE350](ae350_review.md) compare les ports, PLL et
sources de R10, N56r8 SG4 et Pro Dock G22r0. Ses extractions reproductibles
sont dans [macro_comparison.json](macro_comparison.json) et son outil local
dans [compare_macro.py](compare_macro.py).

Les dates du CSV sont des indices : le CLI installé écrit une période de 1 µs
en dur. La configuration échantillonne à 50 MHz, soit 20 ns par pas. Les temps
obtenus sont relatifs au début de la fenêtre ; ils ne datent pas la configuration
du FPGA. Une fenêtre contient 81,92 µs de points, dernier point à 81,90 µs.

| Colonne | Différences 1→2 | Différences 2→3 | Lecture 2 et lecture 3 |
|---|---:|---:|---|
| `ddr_init` | 128 | 0 | 1 sur 4 096 points |
| `u_soc/init_sync[0]` | 129 | 0 | 1 sur 4 096 points |
| `soc_dbg[0]` = POR/HW_RSTN | 129 | 0 | 1 sur 4 096 points |
| `vid_hclk` | 3 277 | 1 639 | activité échantillonnée, aucune fréquence mesurée |
| Les 16 autres colonnes | 0 | 0 | identiques, y compris `gpu_clk` |

La comparaison 1→2 compte 3 303 lignes et 3 663 bits différents. Le nombre
de valeurs à 1 de DDRinit passe de 3 968 à 4 096, celui d'init_sync/POR de
3 967 à 4 096 : une simple rotation du même tampon n'explique pas ces écarts.

Dans la première lecture seulement, DDRinit monte à l'indice 126 (2,52 µs),
init_sync[0] et POR/HW_RSTN à 127 (2,54 µs). Les trois retombent aux indices
4094 et 4095. Ces deux points de bord ne démontrent pas une chute physique
de la DDR. La quantification à 20 ns ne mesure pas le délai réel de la chaîne
de synchronisation à 80 MHz.

Dans les trois fichiers, `u_soc/exts_hrstn` et `vid_hrstn` restent bas ; les
locks PLL restent hauts, `ae350_rst_sync=00` et les deux états PLL_INIT sont
111 (état terminal 7). Deux lectures distinctes rapportent donc un état tardif
cohérent : entrée POR/HW_RSTN libérée, sortie EXTS_HRSTN encore active. Cela
n'identifie pas la cause et ne prouve ni le boot CPU ni la validité des clocks.

## Limites du chemin « initial »

La relecture des désassemblages conserve seulement les faits suivants :

- `read_VER_2000`, 0x46a9c3..0x46aa28, charge l'attribut XML dans AoCore+0x68.
- `startDataTrigger`, 0x47b5ad, saute `startTrigger` lorsque cet attribut est vrai.
- `checkState` envoie un **WRITE** `regSelectData(3)` avec
  `OP_SELECT_CAPTURE_INIT` (0x47e276..0x47e315), puis
  `OP_READ_CAPTURE_INIT` (0x47e439..0x47e473).
- Le wrapper généré relie `GW_JTAG.test_logic_reset_o` au contrôleur GAO et
  au cœur de capture. Cette connexion ne prouve pas qu'un reset ait été
  actionné pendant chaque lecture ni son effet sur la mémoire.
- Les corps du contrôleur et de la mémoire GAO sont protégés ; le chemin
  logiciel seul n'établit ni une lecture non destructive, ni l'absence de
  réarmement automatique ou d'actualisation après lecture/session JTAG.

La répétabilité d'une mémoire initiale figée est donc **non démontrée**.
Actualisation de capture, consommation de l'initiale, effet de session JTAG et
défaut de lecture ne sont pas départagés ici. Le timing GAO est en échec hold :
les constats restent des observations de diagnostic, pas une qualification.

SHA des CSV :

- Lecture 1 : `db63f30efdb210aa4c301edd1fbcef4deb51dbb489695fbaa0899959a378c9dc`
- Lecture 2 : `0ebe1280792292f927f531a7b5b448fa15419dd6eaeb284b1d59037a85ba0917`
- Lecture 3 : `e27fa8a9ccf7df67307c3fad3a06bb8b6986d47a77fab62ad84cbba40d629189`
