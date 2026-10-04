# Audit des horloges internes du PHY USB — 2 octobre 2026

Ce lot établit deux faits distincts : les chemins non-Gray du PHY ne satisfont
pas toutes les relations de phase 60/120 MHz envisagées, et le séquenceur de
démarrage reconstruit cette relation en coupant puis reprenant l'horloge rapide.
Il ne mesure pas la phase réelle sur carte et ne démontre pas encore la cause
complète de l'instabilité USB. Aucun RTL de production, PLL, placement ou SDC de
production n'a été modifié par cet audit. Aucun bitstream diagnostic n'a été chargé.

## Timing du routage r29

Résultats complets : `TESTS/usb_phy_phase_r29_20261002.json`.
Préparation et extraction : `tools/check_usb_phy_phase_timing.py`.
Dossier isolé : `tang/impl/gpu_usb_phase_audit_r29_r1`.

Le SDC diagnostic retire les groupes asynchrones et remplace l'horloge de base
`sclk` par huit horloges générées alternatives, division 960/8, phases 0 à 315°
par pas de 45° du 120 MHz. Les fausses voies UART existantes sont conservées ;
aucune fausse voie Gray n'est ajoutée. Le résumé des horloges du rapport confirme
les fronts 0 ; 1,042 ; 2,083 ; 3,125 ; 4,167 ; 5,208 ; 6,250 ; 7,292 ns.
Ces huit horloges représentent huit hypothèses exclusives sur un seul signal.

La génération diagnostic refait le placement/routage avec les options de
l'audit de référence. Son binaire est **strictement identique au r29** :
`97e5fb5985cb6f156deac2565a2e0455d9e2831ed2b04084f3af43fb0f80b7dc`.
Cette identité rattache les délais rapportés au routage r29 ; elle ne démontre
ni la phase physique du diviseur ni que r29 est toujours chargé sur la carte.
Le SHA-256 du SDC de production est resté
`c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.

| Phase, pas de 960 MHz | Pire setup non-Gray (ns) | Pire hold non-Gray (ns) |
| ---: | ---: | ---: |
| 0 | +2,983 | +0,736 |
| 1 | −3,200 | +2,071 |
| 2 | −2,159 | +3,113 |
| 3 | −1,117 | +4,154 |
| 4 | −1,184 | +4,903 |
| 5 | −2,226 | +3,861 |
| 6 | −3,267 | +2,819 |
| 7 | −4,309 | +1,778 |

La phase 0 est la seule des huit hypothèses avec setup et hold non négatifs
pour les chemins non-Gray rapportés. Ce résultat ne constitue pas une fenêtre
continue de phase et n'identifie pas la phase obtenue dans le FPGA.

Les chemins setup les plus sensibles sont :

- 60 → 120 MHz : `rx_en_s0/Q` vers `fifo_rx/fifo_4to8_sub_inst/Full_s0/D`,
  délai 4,260 ns ; pire marge −3,200 ns pour la phase 1.
- 120 → 60 MHz : `DRU_500M_Top/uut_ides16/Q15` vers `s_state_0_s1/CE`,
  délai 4,898 ns ; pire marge −4,309 ns pour la phase 7.

Ces chemins sont sous
`u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx`.

Chaque phase couvre 80 paires non-Gray distinctes en setup et 84 en hold.
Les 19 paires du précédent relevé non-Gray sont toutes présentes en setup ;
16 paires exactes sur 19 en hold, avec les 19 destinations couvertes. Le tri
retient d'autres sources pour trois destinations en hold. Le plafond global
20 000 chemins n'est pas atteint, mais le plafond de 20 chemins communs
empêche de présenter l'inventaire comme une énumération exhaustive des sources.
Les 22 traversées Gray vers le premier étage de synchronisation sont présentes
séparément, en setup et hold, à chaque phase. Leur marge synchrone n'est pas une
qualification de la CDC asynchrone.

## Chronologie du diviseur dans le modèle officiel

Banc : `TESTS/rtl/usb_phy_startup_tb.sv`.
Commandes exactes, sorties et SHA : `TESTS/usb_phy_startup_r1_20261002.json`.
Quatre exécutions de 22,1003 µs simulées, environ 2,7 secondes au total,
répètent une fois le reset public. Aucun contrôleur USB, paquet, signal interne
forcé ou modification de netlist. Les sources sont stables pendant les runs.

Dans la netlist officielle originale `usb2_0_softphy.vo` :

- lignes 1486–1502 : `reset_stop_Z` pilote DHCE.CEN ;
  CLKDIV.HCLKIN vient de DHCE, CLKDIV.RESETN est `!reset_calib_Z`, CALIB vaut 0,
  DIV_MODE vaut 8 ;
- lignes 1743–1854 : les registres du séquenceur, `reset_stop_Z` et
  `reset_calib_Z` sont cadencés par `clk_i`, donc 60 MHz, et effacés par `rst_i`.

Dans les primitives officielles `gw5a/prim_sim.v` de Gowin 1.9.12 :

- ligne 13131 : DHCE.CEN est **actif bas** ; quatre registres sur fronts
  descendants de CLKIN propagent son inverse avant d'ouvrir la porte ;
- ligne 12911 : CLKDIV remet son état interne à zéro de façon asynchrone via
  RESETN, puis libère son reset interne au premier front montant HCLK ;
  en division par 8, le premier front montant de sortie après cette libération
  intervient au deuxième front HCLK repris dans cette séquence observée.

Première séquence observée, identique pour les quatre déphasages d'entrée :

| Événement | Temps depuis le début du banc (ns) |
| --- | ---: |
| Reset public relâché | 200,300 |
| Premier changement d'état | 208,333 |
| `reset_calib_Z=1` : reset diviseur affirmé | 358,333 |
| `reset_stop_Z=1` : coupure HCLK demandée | 758,333 |
| `reset_calib_Z=0` : reset diviseur relâché, HCLK encore coupé | 1291,667 |
| `reset_stop_Z=0` : reprise HCLK demandée | 2358,333 |
| Séquenceur dans son état terminal | 4491,667 |

Le reset du diviseur est donc libéré plus d'une microseconde **avant** la
reprise de HCLK. La première arête utile dépend de la reprise par DHCE, pilotée
depuis 60 MHz. Un déphasage PLL de 60 MHz peut déplacer ce point de reprise et
reconstruire la phase de sclk : il ne faut pas supposer sclk libre et inchangée.

Avec des fronts montants 60/960 MHz idéalement alignés à l'entrée du modèle,
la première arête sclk après reprise suit celle de 60 MHz de 5,209 ns,
soit environ cinq périodes 960 MHz. Les autres décalages d'entrée testés donnent
4,948 ou 5,729 ns ; décaler 960 MHz de quatre périodes complètes conserve
la phase relative sclk/60 après calibration. Le deuxième reset retrouve ces
relations idéales. Il n'y a pas de mesure silicium dans ces chiffres.

Les **5,209 ns du banc ne sélectionnent pas directement la phase 5 du STA**.
Le banc compare le front de `clk_i` à l'entrée du PHY avec le front de sortie
CLKDIV, à délais de propagation nuls, avec des horloges créées directement par
deux processus et sans modèle PLL. Le STA définit `PHY_CLKOUT` à la sortie
CLKOUT1 de PLL_B et les phases de sclk depuis CLKOUT0 de PLL_B, puis applique
les latences de distribution et le skew de chaque chemin. Un décalage mesuré
entre broches internes après propagation n'est donc pas automatiquement le
décalage nominal à déclarer entre ces sources d'horloge.

La correspondance « phase 5 » ne serait justifiée qu'après avoir confirmé :
la relation des fronts CLKOUT0/CLKOUT1 de la PLL réelle avec ses paramètres et
son démarrage ; les arrivées de 60 et 960 MHz aux primitives concernées ; le
délai clk→Q plus routage de `reset_stop_Z` vers CEN, qui détermine quel front
descendant accepte la commande ; le contrat physique de reprise DHCE/CLKDIV ;
et la convention de latence source propagée retenue dans ce rapport STA.
Les paramètres PLL de phase nulle ne suffisent pas à établir ces éléments.
Le nombre cinq reste ainsi une hypothèse cohérente du modèle idéal, pas une
phase physique identifiée ni une violation matérielle directement démontrée.

## Ce qu'il reste à établir

La relation obtenue par ce modèle ne peut pas être attribuée au matériel avec
les seuls paramètres de PLL : il manque les délais réels de distribution,
clk→Q et chemin CEN, le comportement physique de DHCE/CLKDIV et la phase au
redémarrage. Le banc n'applique aucun SDF et ne modélise ni métastabilité ni
marges de reprise du clock gate. Une simulation de données sans délais ne peut
pas détecter les violations setup de la table STA.

Une capture GAO à 60/120 MHz peut confirmer les étapes du séquenceur et leur
répétabilité, mais ne résout pas à elle seule les pas de 1,042 ns entre fronts.
Pour conclure sur la phase physique, il faut soit une mesure de deux horloges
avec une résolution et des délais de sondage connus, soit un contrat Gowin
sur la reprise DHCE/CLKDIV accompagné de rapports de latence et de timing des
commandes reset/CEN. Le STA seul fournit des délais de routage ; il ne prouve
pas l'état initial effectif du diviseur.

Avant ces preuves, aucun changement de phase PLL ni nouvelle exception timing
n'est justifié comme correction définitive. La capture matérielle des échanges
USB reste nécessaire pour relier ces hypothèses aux pertes constatées.

## Modèle PHY 3.4

La procédure officielle de production du modèle, ses SHA-256, les tentatives
IPC non concluantes et la comparaison ACK court/long sont consignés séparément
dans `TESTS/usb_phy34_model_generation_20261002.json`.
Le modèle 3.4 conserve une période de retour à l'écoute après émission qui
ignore les ACK courts du banc ; les ACK longs passent les contrôles de données.
Les différences de tramage interdisent de considérer ces essais comme une
qualification complète du lien ou comme une preuve de la cause matérielle.

Tous les jobs de ce lot sont terminés ; aucun accès matériel n'a été effectué.
