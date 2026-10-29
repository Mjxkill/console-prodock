# Contrat de démarrage POR/HW : documentation et code exact

Audit du 27 octobre 2026, sans carte, synthèse, routage ou modification des sources. Les observations ci-dessous distinguent les exigences publiées, les choix des exemples et les propriétés déduites du RTL. Elles n'établissent pas la cause de l'échec matériel R21.

## Exigences documentées

| Sujet | Document primaire | État de preuve |
|---|---|---|
| Cœur jusqu'à 800 MHz, DDR/AHB/APB sous 200 MHz, CORE/DDR/AHB asynchrones, AHB/APB synchrones 1:1 | MUG1031-1.3.1E, 23 janvier 2026, p.11, table4-1 | Raccordements et fréquences du projet compatibles avec ces éléments. Ne prouve pas l'activité physique pendant une panne. |
| Chemin cœur direct PLL_R[0]/CLKOUT1 | MUG1031-1.3.1E, p.46, §8.4.1 | Site contraint et raccordement présents dans les snapshots Neo et Pro Dock. |
| LOCK peut présenter des impulsions parasites pendant le verrouillage ; le surveiller continûment au moins 2 ms avant de le considérer établi | UG306-1.0.9E, 12 août 2026, p.40, noteLOCK table5-2 | Exigence explicite. Cette note a été ajoutée en version1.0.9E ; elle n'était pas dans la version1.0.7E lue précédemment. |
| Reset du PLL après stabilisation de la source si son entrée a été commutée ou était instable pendant qu'il fonctionnait | UG306-1.0.9E, p.39–40, note table5-2 | Exigence explicite, mais aucun basculement ou défaut du 50 MHz physique n'a été observé pendant l'échec R21. |
| POR_RSTN et HW_RSTN existent, actifs bas selon les commentaires de la primitive officielle | MUG1031-1.3.1E p.13 ; prim_sim.v AE350_SOC | Connexions identifiées. Aucune largeur minimale, ordre obligatoire POR/HW, ni définition détaillée de leur synchronisation interne n'a été trouvée dans les passages audités. |
| RTC 32,768 kHz, avant le diviseur du compteur RTC | MUG1031-1.3.1E p.9 et p.11 | Divergence avec l'exemple Sipeed et les trois intégrations à10 MHz. Pas de diviseur fabric entre la sortie PLL10 MHz et RTC_CLK ; aucun prescaler interne10MHz n'est démontré par les sources disponibles. |

## Origine exacte des 20 ms

Dans `/home/michael/gowin/ref/TangMega-138KPro-example/ae350_customized_demo/src/ae350_customized_demo.v:108–115`, l'instance `u_key_debounce_ae350` prend **ddr3_init_completed** comme entrée et produit **ae350_rstn**, connecté simultanément à POR_RSTN et HW_RSTN aux lignes216–217. Son horloge est50 MHz, son rstn est attaché à1.

Le module `key_debounce.v:14` définit `st_const=1000000`. Il échantillonne l'entrée par trois bascules, remet son compteur à zéro lorsqu'une transition est détectée, et copie l'entrée stabilisée vers la sortie quand le compteur atteint ce seuil. C'est bien un choix de filtrage d'environ20 ms appliqué au démarrage du CPU après DDRready dans cet exemple. Le nom « anti-rebond » ne signifie donc pas qu'il ne sert qu'à un bouton.

En revanche, ce code n'énonce aucun minimum constructeur du macro AE350. Son compteur20bits n'est pas saturant ; son seuil est revisité après débordement si l'entrée reste constante. Les registres n'ont pas d'initialisation explicite dans le RTL et rstn est attaché à1 dans cet exemple ; l'état de mise sous tension dépend donc aussi de la synthèse/configuration. Ce code ne doit pas être copié comme une preuve complète du contrat de reset.

La note historique « exemple SDK » doit être précisée comme **exemple FPGA Sipeed AE350 local**. Le lien exact entre cet exemple, la constante20ms et les entrées POR/HW est désormais établi ; il n'est pas une spécification de durée obligatoire.

## Comparaison des intégrations

| Version | Source de POR_N et HW_RSTN | Traitement de PLL LOCK | Horloges et différences pertinentes |
|---|---|---|---|
| Exemple Sipeed | Même signal issu du filtre20ms de DDRready, dans clk50 | Le reset CPU de cet exemple n'est pas directement conditionné par LOCK du PLL système | CORE800, AHB/APB100, RTC10 ; choix d'exemple, pas qualification de chaque réutilisation. |
| Pro Dock G22r0 | DDRready traversant deux bascules AHB80, INIT00 ; CLEAR asynchrone contrôlé par rst_key_n | Le top produit rst_key_n avec deux bascules AHB80 échantillonnant ~PLLLOCK, INIT11 ; assertion et release de ce premier étage synchrones | CORE800, AHB/APB80, DDRbus50, RTC10. Pas de délai ajouté20/50ms dans la chaîneCPU. |
| Analyseur L31r8 sur Neo | DDRready traversant deux bascules clk50, INIT00 ; aucun reset explicite de ces bascules ; rst_key_n inutilisé | `console138k_reset` qualifie LOCK sur2,08ms avec effacement asynchrone, mais sa sortie ne pilote pas directement POR/HW de `ae350_soc` | SOC_BUS_DDR_CLK=1 : AHB/APB du CPU prennent wr_clk, l'horloge utilisateurDDR ; CORE800, DDRbus50, RTC10. La qualificationLOCK du reset général ne doit pas être attribuée auCPU sans suivre ces connexions. |
| Console Neo R19/R21 | trial_release traversant deux bascules AHB80, INIT00 ; même sortie versPOR/HW | Deux bascules de reset AHB avec assertion asynchrone sur perteLOCK. trial_release attend50ms de disponibilité DDR/PLL échantillonnée à50MHz | CORE800, AHB/APB80, DDRbus50, RTC10. R19/R21 ont la même chaînefonctionnelle ; une faiblesse commune ne prouve pas la cause de leur différence matérielle. |

Les sources L31r8 citées et son netlist de synthèse ont été vérifiés contre le manifeste historique : empreintes exactes. Dans ce netlist, le second registre CPU a été fusionné avec `hrst_sync_1_s0`, alimenté par `init_sync[0]`, clocké àclk50, CLEAR=GND et INIT0. Cela confirme la chaîneDDRready→2FFclk50. Aucun déplacement ou changement de cette référence n'a été effectué.

## Contre-exemple proposé, non exécuté

Propriété à vérifier : si le design utilise LOCK pour autoriser le CPU, une nouvelle perte de LOCK doit empêcher une libération fondée sur une qualification devenue périmée.

Le RTL Neo ne garantit pas une surveillance continue de cette perte : `ready_meta` et `delay_done` sont mis à jour seulement aux fronts clk50, alors que `ae350_rst_sync` est remis à11 immédiatement sur le front descendant de LOCK. Une impulsion basse entièrement entre deux fronts clk50 peut être vue par les resets asynchrones et manquer le compteur de qualification.

Trace papier conditionnelle, sans métastabilité modélisée, clocks idéales : état initial LOCK=DDRready=1, delay_done=1, ready_meta=11, holding=0, ae350_rst_sync=00 et init_sync=11. Fronts clk50 à0/20/40/60ns ; fronts AHB à1/13,5/26/38,5/51/63,5ns. LOCK descend à6ns, remonte à14ns ; DDRready reste haut.

1. À6ns, ae350_rst_sync passe11 et init_sync passe00 par assertion asynchrone. delay_done reste1.
2. À13,5ns, LOCK est encore bas ; ae350_rst_sync reste11.
3. À20ns, le premier étage ready_meta voit LOCK déjà haut. Ni ready_meta ni delay_done n'enregistrent la perte.
4. À26ns, ae350_rst_sync passe10 ; à38,5ns il passe00. Au front38,5ns, init_sync voit encore le reset actif avant les mises à jour non bloquantes.
5. À51ns, init_sync passe01 ; à63,5ns il passe11, donc POR/HW remonte seulement49,5ns après le retour deLOCK.

Cette trace est une proposition de stimulus sur le RTL exact, pas un résultat de simulation et pas une observation de l'horloge physique. Il faut notamment vérifier les largeurs d'impulsions acceptables des primitives si on transpose le scénario à un modèle temporel. La note2ms de UG306 fournit l'exigence de qualification ; elle ne fournit pas la durée minimale des impulsions parasites physiques.

Le même risque existe si la perte arrive juste avant la fin du premier délai50ms. Un compteur échantillonné n'est pas une preuve de stabilité continue entre ses fronts. Le correctif éventuel devra être testé séparément, sans conclure que cette propriété explique le refus de démarrage R21.

## Observation discriminante proposée

Hors carte, reprendre exactement `neo_reset_trial.v`, les deux étages de reset du top et les deux bascules init_sync. Injecter cette impulsion, puis une impulsion traversant un front50MHz comme contrôle positif. Observer LOCK, ready_meta, delay_done, ae350_rst_sync, init_sync et la durée depuis la dernière remontéeLOCK jusqu'àPOR/HW. Ne pas substituer un modèle de CPU au macro dur pour prétendre valider son démarrage. Ce test nécessite une autorisation distincte de compilation/simulation ; il n'a pas été exécuté ici.

Sur le bitstream existant, `led_n=~ddr_init` permettrait seulement de savoir si DDRready est haut pendant le noirR21. Ce témoin ne mesure ni LOCK, ni POR/HW, ni le cœur800MHz. Aucun accès en lectureCPU n'est actuellement disponible sur R21 ; il ne faut pas annoncer une observation de ces états sans un chemin autonome réellement accessible.
