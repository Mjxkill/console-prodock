# Audit clock / reset / initialisation — R19 et R21r1

Lecture uniquement, 27 octobre 2026. Aucun nouveau bitstream, aucune opération carte, aucune modification RTL/SDC/CST. Références : `console_neo_n56r19_capture_ce_local` et `console_neo_n56r21r1_capture_memory`.

La condition « timing entièrement fermé » n'est pas satisfaite : R19 et R21r1 sont globalement FAIL. Cela ne suffit toutefois pas à expliquer le nouveau refus de démarrage. L'essai A/B/A à 100 kHz JTAG établit que R19 est accessible, R21 a un écran noir avant la requête DMI puis DMI expire, et R19 redevient accessible après restauration. Le TAP IDCODE de R21 répond. L'essai UART R21 ne prouve pas la réception de la trame de reset.

## Matrice des frontières de démarrage

Chemins relatifs à `tang/impl/console_neo_n56r21r1_capture_memory/`, sauf indication. Les numéros TR désignent `impl/pnr/console_neo.tr`.

| Frontière réelle | Preuve disponible | Limite de cette preuve |
|---|---|---|
| 50 MHz → séquenceur PLL_INIT | `source/tang/rtl/ae350/pll_ae350/gowin_pll_ae350.v:57–67` : init_clk, I_RST=0, CLK_PERIOD=20, MULTI_FAC=16. `neo.sdc:2` crée clk50. `pll_init.v:23–44,126–199` initialise et cadence compteurs/FSM/enable. Cellules et INIT identiques R19/R21 (`cpu_route_compare_01/result.json`). UG306-1.0.7E p.53 accepte init_clk de 1 à 100 MHz et son partage avec CLKIN à 50 MHz. | Les INIT réellement configurés n'ont pas été relus sur R21. Le STA ne prouve pas à lui seul le chargement de configuration ou la réussite analogique du verrouillage. |
| PLL_INIT → paramètres / RESET du PLL | `pll_init.v:201–219` échantillonne LOCK et pilote ICPSEL/LPFRES. O_RST est actif pendant STATE2, un cycle 50 MHz, soit 20 ns en RTL ; O_LOCK transmet PLLLOCK uniquement en STATE7. Route RESET maximale : 9,253 ns R19 → 9,570 ns R21. Les contrôles de release d'Enable vers les CLEAR du séquenceur sont présents dans TR11373–11390. | Aucune exigence quantitative minimale de RESET ou de stabilisation analogique à ces ports n'a été identifiée dans ces preuves. Le délai de route n'est pas un contrôle de largeur d'impulsion RESET. Cette impulsion n'est donc ni qualifiée ni démontrée fautive ici. |
| LOCK validé → ae350_rst_sync | `console_neo.v:148–153` : assertion asynchrone quand LOCK est bas, release par deux bascules bus80, INIT11. `neo.sdc:37` exempte leurs PRESET asynchrones ; bus80 est déclaré à 12,5 ns. | Cette exception doit rester justifiée par la structure du synchroniseur. Elle ne prouve pas la qualité analogique de LOCK et ne doit pas être étendue à tous les resets. |
| Disponibilité DDR/PLL → attente 50 ms → init_sync[0] | `neo_reset_trial.v:69–102` synchronise la disponibilité vers clk50 et compte 2 500 000 cycles. `ae350_soc.v:151–155` utilise ensuite deux bascules bus80. Chemin holding → release_request → init_sync0 : TR735355–735390, borne max_delay 8 ns effectivement appliquée, slack +4,515 ns. DDRready brut participe aussi à release_request. | Rien ne prouve que DDRready et PLLready deviennent réellement hauts sur R21. Une perte trop brève pour être échantillonnée ne garantit pas un nouveau délai complet de 50 ms. La borne ne prouve pas la séquence interne du CPU. |
| ae350_rst_sync[1] → CLEAR des init_sync | Source et destination bus80. Recovery +8,851 ns dans TR7072–7073 ; removal +1,416 ns dans TR12062–12063. Détails TR317713–317735 et TR530856–530878. | Ce contrôle existe et passe. **Ajouter un false_path ici supprimerait une vérification correcte** : la source est déjà synchronisée au même domaine. Aucune faute de contrainte démontrée sur cette frontière. |
| init_sync[1] → POR_N et HW_RSTN du macro AE350 | `ae350_soc.v:379–380` raccorde les deux resets à la même sortie. SDF2199561–2199562 : route maximale 9,733 ns, contre 9,531 ns sur R19. Audit parent `root_constraints_01/ae350_sdf_audit.json` : 730 SETUPHOLD dans le macro, mais aucune occurrence de POR_N/HW_RSTN et aucun RECOVERY/REMOVAL/WIDTH/PERIOD dans l'export SDF ; bloc identique R19/R21. | **Lacune précise de preuve** : le contrat de durée, ordre POR/HW, horloges nécessaires et synchronisation interne n'est pas établi. L'absence dans le SDF ne démontre pas l'absence d'exigence dans la bibliothèque STA interne Gowin. Impossible de qualifier ou d'invalider les 9,733 ns sans spécification. |
| CORE 800 / AHB 80 / RTC 10 MHz → macro | `neo.sdc:3–5` déclare les horloges aux sorties PLL ; `:12` sépare CORE et RTC du reste. TR76–78 reconnaît les fréquences ; TR99 indique « No timing paths to get frequency of core_clk! ». La bibliothèque officielle décrit CORE_CLK comme chemin dédié à 800 MHz. SDF contient des arcs CORE → WFI/SCAN et des SETUPHOLD de CORE_CE/EMA. | Le CPU dur n'est pas un ensemble de bascules fabric dont ce STA fermerait les chemins internes. Le délai SDF CORE=0 ne signifie pas une latence physique nulle. Les groupes asynchrones doivent être justifiés par le contrat du macro ; ils ne prouvent pas la relation reset/CORE. Aucune mesure des 800 MHz sur R21. |
| DBG_TCK / TMS / TDI → JTAG AE350 | Le SDF contient TMS/TDI SETUPHOLD par rapport à DBG_TCK, et DBG_TCK → TDO_OUT. Le SDC ne crée aucune horloge TCK et aucun budget input/output delay pour ces ports. Route TCK maximale inchangée à 2,677 ns ; TMS 2,668 → 2,777 ns ; TDI inchangée à 5,319 ns. | Une fermeture explicite du timing de cette interface manque dans ce SDC, alors que le macro expose des arcs. Sa causalité dans l'échec R21 n'est pas démontrée : TAP répond même à 100 kHz, mais DMI attend. La réponse du TAP ne qualifie pas toute la chaîne DMI interne. |
| Reset de scanout et prst[1] | Logique préservée, route modifiée ; promotion LW observée sur R21. Le reset des sérialiseurs HDMI possède des contrôles recovery explicites passants (TR11351–11363). | LW est une ressource légitime. Aucun écart quantitatif à une spécification ni chaîne logique prst → DMI n'a été établi. La présence de LW n'explique pas la panne. |

## Durée du reset et simulation

`TESTS/neo_720p_20261012/reset_sequence_20261025/README.md:3–6` précise que le délai de 20 ms vient d'un **exemple SDK** et **n'est pas un minimum constructeur établi**. Les 50 ms constituent la marge expérimentale choisie par l'utilisateur, pas une exigence MUG1031 démontrée.

Les simulations RTL et mappées du séquenceur sont archivées dans `simulation_50ms.log` et `mapped_50ms_r2/result.json`. Elles prouvent son comportement dans ces bancs. Le modèle AE350_SOC installé ne contient que des déclarations de ports (`/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v:16971–17322`). Un banc utilisant un substitut du CPU ne prouverait donc pas le démarrage interne du bloc dur.

## Comparaison des cibles

G22r0 Pro Dock cible 138B/FPG676 ; Neo R19/R21 cible 138C/PG484. Le L31r8 analyseur connu fonctionnel sur la même Neo cible également 138C/PG484 (`/home/michael/logic_analyser_wifi/tang/impl/linux_l31r8_local_20261012/workspace/tang/build_la16_usb.tcl:6`).

Le Gowin installé propose PBGA484A pour B et C. Leurs JSON de brochage sont identiques (SHA256 `a8ea98f6c79741f0f61ffcff37ddc5f9af1c43c7a536d4782bb1d8b9f28bfb08`). Cela ne prouve ni l'identité du silicium ni une erreur de sélection. La page Sipeed ambiguë indiquant B ne suffit pas à invalider C.

L'audit parent constate des arcs de macro AE350 différents entre Pro Dock et Neo. Toutefois, cible, outils et bibliothèques historiques diffèrent aussi : on ne peut attribuer cet écart à B/C seulement. Les blocs SDF du macro R19 et R21 sont identiques.

## Conséquence

L'ajout d'observation ne justifie pas une fonction cassée. Les preuves actuelles restent insuffisantes : timing global non fermé, contrat de démarrage du macro incomplet, interface JTAG sans budgets explicites. Aucune de ces lacunes n'est encore reliée causalement à l'échec de R21. Ajouter des exceptions ou des contraintes LW sans mécanisme établi pourrait masquer le problème.

Les contrôles hors carte utiles sont d'établir les exigences fabricant POR/HW/horloges, de tester les séquences dans les limites explicites du modèle disponible, et de publier la résolution réelle des exceptions et arcs JTAG. Le démarrage du CPU seul ne qualifierait pas le GPU.
