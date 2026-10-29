# R9 : échec de démarrage commun CPU/vidéo, cause physique non mesurée

L’échec R9 n’est pas localisé au seul GPU. Le TAP AE350 rend son IDCODE, mais les transactions DMI expirent avant toute confirmation d’arrêt CPU. Le RTL possède un verrou de démarrage commun : **la calibration DDR doit terminer pour libérer POR/HW reset du CPU ; le reset du scanout dépend ensuite de la sortie reset du CPU**. Une calibration bloquée, ou un blocage de la chaîne PLL AE350 → reset CPU, peut donc expliquer les deux symptômes sans supposer deux pannes indépendantes.

Cette explication est une **hypothèse compatible avec le câblage**, pas la mesure de la panne. Aucun niveau `ddr_init`, PLL LOCK ou reset CPU n’a été observé sous R9. « Pas de mire » ne prouve pas à lui seul l’absence électrique du signal TMDS. Aucun nouveau routage ni accès carte n’est effectué par cette analyse.

## Identités et observations séparées

| Version | SHA-256 bitstream | Observation matérielle pertinente | Qualification STA |
|---|---|---|---|
| N56r8 SG4 | `51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35` | Repli vérifié : CPU accessible/garé, frame +62, checksum `1ff8f800`, mire confirmée par utilisateur | FAIL, setup −0,144 ns |
| R2 observateur | `150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01` | Deux rechargements avec CPU accessible ; lecteur mémoire encore bloqué `mrst=01` | FAIL, setup −1,848 ns / recovery −1,418 ns |
| R9 DMA C150 | `1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde` | Deux essais : DONE, IDCODE `1000563d`, DMI timeout ; aucune confirmation CPU_HALTED | FAIL, setup −0,849 ns / recovery −0,360 ns |

N56r8 SG4 n’est **pas** le candidat de routage R8 C150. R2 est un témoin de démarrage du CPU, pas une référence de framebuffer fonctionnel.

Les preuves exactes sont le [résultat R9 à 100 kHz](../r9_route9_rgb_trial_100k/result.json), son [journal DMI](../r9_route9_rgb_trial_100k/reset.log), le [journal du repli](../r9_route9_rgb_trial_100k/restored.log), le [premier essai à 1 MHz](../r9_route9_rgb_trial/result.json) et les [deux rechargements R2](../r9_route2_reset_reloads/result.json). `cpu_left_halted:true` dans le résultat final R9 concerne le **repli N56r8**, pas R9. Le second essai attend deux secondes après programmation et utilise 100 kHz ; il ne résout pas l’échec DMI. DONE n’est pas une vérification de lecture SRAM.

## Chaîne de démarrage réellement câblée

Références figées R9 : [console_neo.v](../../../../tang/impl/console_neo_n56r9_route9_dma_c150/source/tang/boards/neo/console_neo.v), [ae350_soc.v](../../../../tang/impl/console_neo_n56r9_route9_dma_c150/source/tang/rtl/board/ae350_soc.v), [pll_init.v](../../../../tang/impl/console_neo_n56r9_route9_dma_c150/source/tang/rtl/board/pll_init.v).

1. `console_neo.v:135–152` : PLL AE350, bus 80 MHz/core 800 MHz/RTC 10 MHz. `ae350_rst_sync=11`, preset asynchrone tant que le lock filtré manque, puis deux cycles bus avant `ae350_por_n=1`.
2. `ae350_soc.v:132–145` : PLL DDR indépendante, référence 50 MHz, mémoire ≈300 MHz ; son ENCLK2 reçoit `ddr3_stop`. `PLL_INIT` filtre le lock via sa machine d’état ; le lock brut et le lock filtré sont deux signaux distincts.
3. `ae350_soc.v:150–155` : `init_sync=00`, effacement asynchrone par `!rst_key_n`, puis deux étages 80 MHz échantillonnant `ddr3_init_completed`. `ae350_rstn=init_sync[1]`.
4. `ae350_soc.v:378–379` : ce signal alimente POR et HW reset du wrapper AE350. La primitive routée conserve bien **les deux** broches `POR_N` et `HW_RSTN`, reliées à `soc_dbg[0]`.
5. `ae350_soc.v:330–331` : `vid_hrstn_r=0` puis copie de `exts_hrstn` sur l’horloge EXTS. `console_neo.v:102–110` l’envoie au scanout ; la mire interne dépend donc aussi de cette libération.
6. `console_neo.v:26–34,118` : PLL vidéo et reset du sérialiseur HDMI sont indépendants du reset CPU, avec trois étages `pixel_up=000` après pixel LOCK. Un scanout maintenu en reset ne démontre donc pas que cette PLL est arrêtée.
7. `console_neo.v:194` et `neo.cst:8` : `led_n=~ddr_init`, broche V13. V13 bas signifie calibration terminée ; V13 haut signifie `ddr_init=0`. C’est un témoin matériel déjà exporté, sans dépendance DMI/AHB.

Les captures complètes des primitives sélectionnées sont [N56r8](n56r8.json), [R2](r2.json), [R9](r9.json). Les **263 primitives** inspectées comprennent les PLL, la primitive AE350, les diviseurs/DLL/DCE et les chaînes PLL_INIT/reset ciblées. R2/R9 sont identiques bit pour bit sur leurs types, broches et paramètres INIT. Les 19 différences textuelles N56r8/R9 sont uniquement des alias nets (`state_145→state_178`, `soc_dbg_144→soc_dbg_177`, `n3587_7→n4009_7`). Les registres sources et LUT de lock sont vérifiés indépendamment, y compris l’inverseur logique de lock `LUT4 INIT=7FFF`.

Les sources R2/R9 ne diffèrent que par CST et métadonnées de fermeture timing ; le VG est identique : `0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157`. Entre N56r8/R9, les changements RTL concernent l’observateur et le lecteur/scanout ; les sources AE350, PLL, PLL_INIT et IP DDR sont inchangées. Cela exclut une modification RTL de leur séquence, pas une panne physique liée au placement.

Un contrôle complémentaire de **12 primitives DDR** (DLL, diviseur, trois `ddr_rsti_reg` et registres de completion) trouve aussi une identité exacte entre les trois versions, sans normalisation de nets. Le diviseur DDR reste `/4`, CALIB relié à GND ; DLL `CODESCAL=111`, `SCAL_EN=FALSE`, `DLL_FORCE=FALSE`. Ces réglages statiques identiques ne donnent pas les taps de calibration effectivement atteints sur carte.

## Clocks et routes physiques

Les trois SDC ont SHA `c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113`. Les contraintes des PLL et des resets de démarrage sont inchangées. Sites imposés : PLL AE350 `PLL_R[0]`, DDR `PLL_L[0]`, vidéo `PLL_R[3]`. Le rapport timing confirme AE350 `PLL_R[0]` et DCE vidéo `SG[4]` pour les trois versions. Le site DDR est ici une contrainte conservée, pas une nouvelle observation physique sur carte.

| Primitive | N56r8 | R2 | R9 |
|---|---|---|---|
| init_sync0 | R58C34[2][B] | R56C50[1][B] | R90C46[0][A] |
| init_sync1 | R58C34[2][A] | R56C50[1][A] | R90C46[1][B] |
| ae350_rst_sync1 | R67C99[0][B] | R85C89[2][B] | R79C87[1][B] |
| vid_hrstn_r | R50C120[0][A] | identique | identique |

Les rapports allouent PRIMARY à `vid_hclk` et `gpu_clk` dans les huit régions, inchangé. `clk5x` reste `BANK3_HCLK1`, DDR mémoire `BANK6_HCLK0 BANK7_HCLK0`. Les couvertures régionales de `clk_d`, pixel et USB changent avec le placement. RTC et reset interne DDR `gw3_top/ddr_rst` utilisent LW dans les trois versions. **Ce reset DDR sur LW n’est pas une nouvelle promotion R9.** Les changements LW du GPU décrits dans [la revue timing précédente](../route9_path_review/README.md) restent des défauts à conserver, mais ne constituent pas une preuve qu’ils bloquent le démarrage AE350.

Les avertissements PR1014 pour `clk_d` et `ae350_tck_d` sont exactement les mêmes dans les trois builds. Les délais ci-dessous viennent des arcs INTERCONNECT SDF, en ns au coin maximum ; ce sont des délais de route, **pas des marges STA ni des mesures d’oscilloscope**. [Données complètes](startup_sdf.json).

| Arc | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| clk50 → PLL AE350 / vidéo CLKIN | 4,983 | 4,983 | 4,983 |
| clk50 → PLL DDR CLKIN | 4,991 | 4,991 | 4,991 |
| PLL AE350 → CORE_CLK | 0 | 0 | 0 |
| PLL AE350 → AHB_CLK / APB_CLK | 3,442 / 3,451 | identique | identique |
| PLL AE350 → vid_hrstn_r.CLK | 3,468 | 3,468 | 3,468 |
| PLL AE350 → init_sync.CLK | 3,452 | 3,553 | 3,522 |
| TCK ibuf → hard DBG_TCK | 2,677 | 2,815 | 2,680 |
| TMS ibuf → hard TMS_IN | 2,760 | 2,878 | 2,896 |
| TDI ibuf → hard TDI_IN | 5,319 | 5,319 | 5,319 |
| RTC → hard RTC_CLK | 2,224 | 2,224 | 2,535 |
| init_sync1 → hard POR_N et HW_RSTN | 8,884 | 8,239 | 8,750 |
| DDRinit → init_sync0.D | 4,560 | 2,805 | 2,132 |
| init_sync0 → init_sync1.D | 0,396 | 0,396 | 0,415 |
| ae350_rst_sync1 → init_sync.CLEAR | 2,994 | 2,806 | 2,206 |
| PLL_INIT AE → PLL RESET | 10,209 | 9,595 | 9,438 |
| PLL_INIT DDR → PLL RESET | 2,188 | 3,400 | 3,293 |
| DDR_STOP → PLL DDR ENCLK2 | 2,981 | 2,566 | 3,570 |
| hard HRESETN → vid_hrstn_r.D | 5,484 | 5,255 | 4,364 |
| PLL DDR CLKOUT2 → DLL CLKIN / diviseur HCLKIN | 0,005 | 0,005 | 0,005 |
| Contrôle STOP → DLL STOP | 1,771 | 1,679 | 1,511 |
| Reset DLL enregistré → DLL RESET | 3,102 | 3,031 | 3,508 |
| Contrôle reset diviseur → CLKDIV RESETN | 0,378 | 0,343 | 0,378 |

Il n’y a pas de grand détour R9 nouveau dans le TCK, les clocks hard CPU ou le reset CPU qui expliquerait directement l’échec. Le routage DDR_STOP et les emplacements de synchroniseurs changent ; leur effet réel reste à mesurer. Les chemins recovery négatifs R9 sont en aval (`u_gpu/prst`), et le pire setup `busy_sync` est également un chemin GPU : les corriger n’est pas une démonstration que DMI reviendra.

## Observation indépendante du CPU : possibilités et limites

| Moyen existant | Ce qu’il observe réellement | Utilisable sans nouveau bitstream pour DDRinit/PLL ? |
|---|---|---|
| LED V13 | `~ddr_init` directement | **Oui pour DDRinit**, observation visuelle ou électrique par l’opérateur |
| IDCODE TAP AE350 via ESP-Prog | Chemin série TAP, ID hard CPU | Déjà lu sous R9 ; ne prouve pas que son domaine DMI répond |
| JTAG FPGA de configuration via Sipeed | ID, statut de configuration/DONE/CRC | Aucun bit de lock PLL utilisateur ou calibration DDR dans le statut documenté |
| `neo_reset_jtag` | TAP logiciel de l’expérience autonome, reset copies/signatures | **Non**, ce top remplace la console et n’est pas présent dans R9 |
| Diagnostic AHB/observateur console | Signaux de carte après traversée CPU/AHB | Non lorsque les transactions DMI ne terminent pas |
| Boundary scan SAMPLE | Potentiellement état de broches | Non préparé : aucun BSDL/mapping de V13/opcode SAMPLE validé retrouvé |
| GAO/instrumentation HDL | Signaux qui ont été insérés dans le design | Pas présent dans les sources/netlist actuelles ; nécessiterait une nouvelle construction |

[neo_reset_jtag.v](../../../rtl/neo_reset_jtag.v) déclare explicitement un top sans AE350/DDR/USB (lignes 1–7). Son ID `1000563d` est une constante de son TAP logiciel (lignes 49,84), pas un canal universel de télémétrie FPGA. [run_reset_probe.py](../../../../tools/neo/run_reset_probe.py), lignes 125–153, envoie IR2/DR163 à ce TAP particulier ; l’exécuter contre R9 ne donnerait pas la photographie attendue.

Le manuel local **UG704-1.0.4E**, §3.4 et §5.1, décrit le JTAG FPGA (IR **8 bits**) et le statut de configuration ; aucun champ n’y représente `ddr_init`, le lock AE350 ou le lock vidéo. Le TAP AE350 utilisé ici a un autre protocole. Le code local [gowin.cpp](/home/michael/Litex/openFPGALoader/src/gowin.cpp), lignes 473–519, lit ce statut ; sa section BSCAN à partir de la ligne 985 est un wrapper SPI flash avec commandes de broches, pas une routine passive prête à lire V13. La documentation mentionne IEEE1149.1 ; cela ne fournit pas à elle seule l’opcode et la position de V13. Ni les bibliothèques de primitives installées ni SUG283-3.6E n’ont livré une primitive de télémétrie JTAG réutilisable dans le bitstream existant. **Aucune instruction JTAG non documentée n’est proposée.**

## Séparation utile avant une autre expérience physique

- **V13 haut / LED DDR éteinte sous R9** : confirme `ddr_init=0` sur sa sortie, concentre l’enquête sur PLL DDR/DDR_STOP/calibration et sa chaîne de reset. Ne prouve pas quel sous-bloc est arrêté, ni que la DDR seule est en cause.
- **V13 bas / LED DDR allumée sous R9** : confirme calibration annoncée terminée ; regarder ensuite le lock AE350 filtré, ses clocks et les deux étapes `init_sync`/POR. Cela ne prouve pas la réception correcte du signal à chaque charge.
- **DMI à nouveau accessible** : lire les témoins existants de carte avant toute commande GPU ; comparer clocks/resets avant de revenir aux cônes `prst`/`busy_sync`.

Ces observations relèvent d’un protocole ultérieur du seul opérateur Neo. Le bitstream N56r8 actuellement visible n’est pas remplacé par cette analyse. Les futures propositions timing restent archivées, non lancées. Aucun essai de R9 supplémentaire n’est présumé autorisé par ce rapport.

Reproduction locale : `python3 TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_startup_analysis/verify_analysis.py`. Le [résultat vérifié](verification.json) conserve les identités sources, rapports, essais, documentation et script. `verified:true` signifie seulement que cette comparaison structurelle est reproductible ; `hardware_cause_proven:false` et les qualifications **FAIL** sont conservés.
