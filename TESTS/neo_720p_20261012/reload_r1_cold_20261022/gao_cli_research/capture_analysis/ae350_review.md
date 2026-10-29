# AE350 R10 : revue des conditions de démarrage

Les trois lectures GAO rapportent `HRESETN = EXTS_HRSTN = 0`. Les lectures 2
et 3 rapportent simultanément `POR_N = HW_RSTN = 1` pendant les 4 096 points.
Cela place l'observation du blocage **entre les entrées reset libérées et la
sortie reset du macro dur**, sous réserve de la validité de l'instrumentation.
Ce n'est pas une identification de la cause interne. Le timing GAO échoue en
hold et la mémoire « initiale » n'est pas répétable : voir [comparaison](README.md).

Cette revue n'exécute aucun outil matériel et ne change aucune source ni
configuration. Les propositions de signaux ci-dessous ne constituent pas un
nouveau candidat construit ou autorisé sur carte.

## Comparaison reproductible des interfaces routées

[compare_macro.py](compare_macro.py) extrait les interfaces directement des
trois `.vo` et conserve leurs SHA dans [macro_comparison.json](macro_comparison.json).
Il vérifie que les fichiers lus sont inchangés après extraction.

| Élément comparé | R10 contre N56r8 SG4 | R10 contre Pro Dock G22r0 |
|---|---|---|
| 149 connexions du macro `AE350_SOC` | Toutes identiques, sans renommage des nets | 8 différences, détaillées dans le JSON |
| Paramètres explicites du macro | Aucun dans les trois `.vo` | Aucun |
| 48 connexions de la PLL AE350 | Toutes identiques | Toutes identiques |
| 94 paramètres de la PLL AE350 | Tous identiques | Tous identiques |
| 7 sources ciblées : wrapper, config, ITCM, PLL et PLL_INIT | SHA tous identiques | Wrapper généré et config ITCM différents ; les 5 autres identiques |

Les huit différences avec la Pro Dock sont `POR_N`, `HW_RSTN`,
`CORE0_WFI_MODE`, `UART2_TXD`, `EXTS_HADDR`, `EXTS_HREADYIN`, `GPIO_IN` et
`ROM_HRDATA`. Certaines sont des alias, d'autres de vraies différences de
périphériques ou de ROM. Pro Dock utilise `ITCM_SIZE=14` et la ROM console ;
Neo utilise `ITCM_SIZE=10` et le parking ITCM. **N56r8 SG4 est donc le témoin
le plus proche**, et le port ROM ainsi que les sources ITCM sont identiques
à R10 dans ce témoin. L'identité des ports ne démontre pas l'identité des
routes, de l'état interne du macro ou des signaux électriques.

Sources principales figées :

- [R10, macro routé](/home/michael/console/tang/impl/console_neo_n56r10_gao_startup/impl/pnr/console_neo.vo:1226581).
- [R8 SG4, macro routé](/home/michael/console/tang/impl/console_neo_n56r8_hdmi_sg4/impl/pnr/console_neo.vo:1217262).
- [Pro Dock G22r0, macro routé](/home/michael/console/tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.vo:1211167).
- [R10, PLL routée](/home/michael/console/tang/impl/console_neo_n56r10_gao_startup/impl/pnr/console_neo.vo:1113795).

## Entrées effectivement câblées

| Groupe | Valeur ou connexion R10 | Ce que cela permet de dire |
|---|---|---|
| `POR_N`, `HW_RSTN` | Tous deux `soc_dbg[0]` = `init_sync[1]` | Le signal sondé alimente logiquement les deux entrées, sans une troisième entrée de reset externe oubliée dans cette interface. |
| `CORE_CLK` | `core_clk`, PLL `CLKOUT1`, 800 MHz configurés | Connexion conforme au chemin direct demandé par MUG1030 ; fréquence et livraison physique non mesurées par la GAO actuelle. |
| `AHB_CLK`, `APB_CLK` | Même `vid_hclk`, PLL `CLKOUT0`, 80 MHz configurés | Activité échantillonnée visible ; pas de mesure de fréquence à partir de 50 MHz. |
| `DDR_CLK` | `clk_d`, référence 50 MHz du design | Horloge distincte des 300 MHz de la mémoire DDR ; ne pas confondre les deux domaines. |
| `RTC_CLK` | `rtc_clk`, PLL `CLKOUT4`, 10 MHz configurés | Pas observée dans les 20 sondes actuelles ; LOCK ne prouve pas son activité. |
| `CORE_CE`, `AXI_CE`, `DDR_CE`, `AHB_CE`, `APB2AHB_CE` | VCC | Aucun de ces enables externes n'est statiquement coupé. |
| `APB_CE[7:0]` | `10111101` | Même masque R8 et Pro Dock ; ne pas interpréter ses deux zéros comme une régression nouvelle. |
| `TEST_RSTN`, `TRST_IN`, `RET1N`, `RET2N`, `PGEN_CHAIN_I` | VCC | Mêmes valeurs statiques que les deux témoins. La documentation locale consultée ne décrit pas toutes les séquences internes associées. |
| `SCAN_TEST`, `SCAN_EN`, `TEST_MODE`, `TEST_CLK`, `WAKEUP_IN` | GND | Aucun mode de test ou wakeup externe nouvellement activé. |
| PLL `ENCLK0..6` | VCC, `CLKOUT0..4_EN=TRUE` | Les sorties utiles ne sont pas désactivées par leur entrée de validation. |
| `ROM_HREADY`, `ROM_HRESP` | VCC, GND | La réponse ROM n'impose pas de wait permanent par ces broches. |
| `APB_PREADY`, `EXTM_HREADY` | GND | Interfaces externes inutilisées dans cette configuration ; mêmes valeurs sur R8 fonctionnel. Ce seul zéro ne diagnostique pas une panne reset. |
| `DDR_HREADY`, `DDR_HRESP`, `EXTS_HREADYIN` | Réponses dynamiques des ponts | Non observées ; utiles seulement avec le transfert correspondant pour diagnostiquer un blocage de bus. |

`PLL_INIT=7` appartient au contrôleur d'initialisation **de la PLL**, et non
à une machine d'état de démarrage du CPU. `vid_hrstn` est une copie
enregistrée de `EXTS_HRSTN` ; avec les deux à zéro, son registre n'est pas
une explication indépendante de la sortie reset du macro.

La libération de `POR_N/HW_RSTN` est synchronisée sur AHB après DDRinit.
Elle n'est pas, dans ce RTL, une preuve de respect de toutes les contraintes
internes de séquencement du bloc dur. La même structure fonctionne dans
R8 ; aucun minimum de durée POR/HW ni ordre obligatoire de ces deux entrées
n'a été établi par les manuels locaux consultés. Il serait donc injustifié
de changer cet ordre ou de contourner le reset à partir de cette capture.

## Hypothèses à départager, sans cause affirmée

| Hypothèse | Observation discriminante manquante | Limite de l'interprétation |
|---|---|---|
| Lecture GAO partiellement renouvelée ou défectueuse | Répétition avec provenance de la fenêtre connue et instrument qualifié, comparaison d'états indépendants | Les lectures 2/3 confortent un état tardif, pas une mémoire initiale immuable. |
| Une horloge nécessaire n'est pas livrée correctement malgré les LOCK | `RTC_CLK`, activité du chemin cœur, enables et resets PLL corrélés ; au besoin témoin divisé admissible dans un futur candidat | Une sonde 50 MHz ne mesure pas directement 80 ou 800 MHz ; ajouter une charge sur le chemin cœur dédié peut lui-même perturber ce chemin. |
| Séquence reset/power interne du macro non achevée | `PRESETN`, `DDR_RSTN` avec `HRESETN` et les entrées POR/HW | Trois sorties basses orientent vers un état plus global ; une seule basse distingue un domaine. Aucun de ces résultats n'identifie seul la cause. |
| Le cœur exécute puis entre dans un état particulier | `ROM_HTRANS[1]`, une sélection de `ROM_HADDR`, `CORE0_WFI_MODE` ; réponses de bus associées | Une activité ROM prouve des transactions sur ce port, pas nécessairement leur auteur ni le bon déroulement du boot. WFI isolé n'est pas un compteur d'instructions. |
| État SMU interne de reset, veille ou horloges | Lorsque l'accès redevient possible : lecture seule de WRSR, CER, CRR et des registres de statut documentés | Les entrées CE à 1 ne prouvent pas les enables internes. Rien n'établit qu'un logiciel ait modifié ces registres pendant cet échec. |
| Livraison physique ou relation temporelle des resets différente | Arcs spécifiques de recovery/removal et relations aux domaines concernés, puis observation qualifiée | Les échecs STA existants restent réels, mais ne constituent pas une preuve que leur pire chemin GPU explique HRESETN. |

Les sorties supplémentaires existent bien dans le `.vo` :

- `PRESETN` → `u_soc/u_ae350/u_RiscV_AE350_SOC/PRESETN`.
- `DDR_RSTN` → `u_soc/u_ae350/u_RiscV_AE350_SOC/ddr_hrstn`.
- `CORE0_WFI_MODE` → `u_soc/u_ae350/u_RiscV_AE350_SOC/core0_wfi`.
- `ROM_HTRANS[1]` → `u_soc/u_ae350/u_RiscV_AE350_SOC/ROM_HTRANS[1]`.
- `PRDYN_CHAIN_O` existe aussi, mais sa signification et sa valeur attendue
  ne sont pas documentées dans les sources consultées : pas de diagnostic
  de « power ready » déduit de son seul nom.

Un prochain ensemble compact de sondes privilégierait donc les deux autres
sorties reset, RTC, ROM_HTRANS[1] et WFI, en gardant POR/HW et HRESETN pour
la corrélation. Ce sont des propositions d'observation pour l'opérateur,
pas une demande de modification du bitstream actif.

## Documentation locale primaire et portée

- [MUG1030-1.3E, Quick Start](/home/michael/ae350/MUG1030_quick_start.pdf),
  §2.6.4 : `CORE_CLK` doit venir directement de `PLL_R[0].CLKOUT1`.
  Le CST R10 impose bien PLL_R[0]. SHA
  `67c2b2624db31adbc1402e5be9a509558fcc6c10dad5c9fb5f6b6c8879d38490`.
- [MUG1029-1.3E, Software Programming](/home/michael/ae350/MUG1029_software_programming.pdf),
  chapitre 16, pages imprimées 162–170 : SMU contrôle reset, clocks et power ;
  WRSR distingue SW/WDT/HW/MPOR/APOR et réveils ; CER possède les enables
  internes HCLK/PCLK/CORE, initialisés à 1. SHA
  `bbf1d6585253576b1616135838623faec94677b61b2e2d273a9deebb2873af61`.
- Le SDK local [Driver_SMU.h](/home/michael/ae350/sdk/RiscV_AE350_SOC_V1.3/library/bsp/driver/include/Driver_SMU.h)
  confirme ces champs. `ae350.h` place SMU à `0xF0100000` : WRSR +0x10,
  CER +0x20, CRR +0x24. WRSR est W1C : une lecture future ne doit pas être
  accompagnée d'une écriture qui effacerait l'historique.
- La table 16-11 nomme `HART0_RESET`, mais le document le décrit RO et
  hardwired à 1. Ce n'est pas une entrée reset supplémentaire contrôlable
  et ce bit ne doit pas être interprété seul comme « cœur tenu en reset ».

Ces documents ne donnent pas l'équation interne de `HRESETN`, la durée
minimale de POR/HW ni une preuve que RTC soit la cause de l'échec. La logique
interne du hard macro n'est pas exposée dans le wrapper protégé. Aucun reset
n'est contourné et aucune cause unique timing, DDR ou SMU n'est affirmée.
