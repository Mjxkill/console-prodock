# Comparaison CPU/JTAG R19 et R21r1

Lecture seule des netlists et SDF. Cellules et paramètres CPU, PLL, séquence50ms et synchroniseurs reset identiques. Les délais ci-dessous sont les maxima du modèle SDF, pas des mesures carte.

| Destination | R19 (ns) | R21r1 (ns) |
|---|---:|---:|
|I|1.892|1.892|
|AHB_CLK|3.442|3.442|
|APB_CLK|3.451|3.451|
|CORE_CLK|0.0|0.0|
|DBG_TCK|2.677|2.677|
|HW_RSTN|9.531|9.733|
|POR_N|9.531|9.733|
|RTC_CLK|2.224|2.535|
|TDI_IN|5.319|5.319|
|TMS_IN|2.668|2.777|

CORE_CLK est fourni avec un arc0:0:0 dans les deux SDF : cela ne mesure pas un délai physique nul. Les autres clocks obligatoires conservent leurs classes PRIMARY. Aucun nouveau chemin CPU/resettrial négatif dans les tableaux STA ; la violation PLL vers diag_board est un observateur USB.

Observables existants sans accèsCPU : LED_n = inverse DDR init ; caméra HDMI = fonctionnement du sous-ensemble vidéo, pas de preuve du800MHz. Si SOFT-USB énumère, EP0 diag_board[3:0] rapporte PLL_AE350lock, DDRstop, DDRlock, CPUreset_n (deux FF dans le domaineUSB). Ces niveaux sont dans les bits159:156 du bloc diagnostic512bits. Aucun GAO n’est intégré à R19/R21 : les fichiers .gao dans source sont historiques et ne constituent pas une capture disponible.

Le premier retour R19 à1MHz a mal lu IDCODE ; parent a ensuite confirmé le même R19 à100kHz sans nouveau chargement. Cette observation sépare une défaillance de transport JTAG possible d’une conclusion prématurée sur le démarrageCPU. Aucun essai carte effectué par ce comparateur.
