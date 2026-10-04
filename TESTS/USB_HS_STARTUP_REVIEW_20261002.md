# USB HS : démarrage, rechargement et phase du diviseur — 2 octobre 2026

Revue centrée sur `gpu_usb_hs33_ready_r2` : contrôleur Gowin 3.3, PHY 3.5
Advance, HS 480 Mbit/s. Elle a été complétée par deux P&R diagnostiques
isolés, lancés par la session principale ; résultats en section 7. Aucun
RTL ou contrainte de production, aucune netlist fournisseur n'a été modifié.
Les images d'audit n'ont pas été chargées. Aucune nouvelle simulation n'a
été lancée. La procédure proposée en section 5 ne constitue pas une preuve
de couverture au-delà des résultats explicitement consignés en section 7.

## Conclusion établie

L'essai de la référence `hs33_ready_r2` a effectivement rechargé le FPGA puis
réénuméré en HS avant l'échec du premier transfert de 64 octets.
L'examen des sources ne révèle pas
un reset initial absent des séquenceurs ouverts ou des FIFO applicatives.
Il reste une question concrète de démarrage interne du PHY : la reprise du
960 MHz, commandée depuis 60 MHz, reconstruit la phase du CLKDIV. Son créneau
de capture et sa propagation physique ne sont pas qualifiés par le rapport
STA courant, qui sépare ces horloges par une exception asynchrone.

Dans l'ancien modèle fonctionnel, avec fronts 60/960 idéalement alignés, cette
phase est calculable : **5 périodes de 960 MHz = 5,208333 ns**, soit la phase
225° de l'horloge divisée par huit. Il s'agit d'un mapping conditionnel précis,
pas d'une mesure sur carte ni d'une qualification du routage HS33 r2.

**État matériel ultérieur :** `hs33_ep0_r1` passe trois rechargements HS et
1 632 300 octets exacts au total, puis 300 contrôles EP0. Ce résultat positif
est séparé de l'audit de phase, qui reste non conclusif ; voir section 8.

## 1. Identité et preuve du rechargement

Référence : `TESTS/usb_ax15_20261002/usb_hs33_ready_r2/result.json`,
`reload_test_tool.py` et `load1/{loader,usb}.log`.

| Élément | Valeur |
| --- | --- |
| Bitstream chargé, SHA-256 | `d5c7370acc70dca2ce7ca2992ecbb1f324ad24e0a9740058384daf298141d21a` |
| Sources figées vérifiées par le chargeur | 98 |
| Plus petite marge du rapport chargé | +0,140 ns |
| Programmateur | série `2023112818`, bus/dev `3:66` |
| Périphérique avant / après | branche `3-7`, adresse 105 → 106 |
| État après | 480 Mbit/s, configuration 1, deux interfaces, autorisé |
| Stress | première séquence de 64 octets en échec |

Le script archivé vérifie le SHA du bitstream, les 98 SHA du manifeste et
l'absence de violations setup/hold avant programmation (lignes 115–134).
Il retrouve le programmateur par son numéro de série, charge en SRAM,
attend `DONE`, puis exige une nouvelle adresse/bus et une configuration
complète avant le stress (lignes 141–167). Aucune requête de contrôle privée
ne prépare le périphérique avant ce test. Le test passe toutefois par les
opérations CDC standard d'ouverture du port.

Le journal signale une insertion à l'index 14 et le dernier octet reporté,
puis des doublons dans une nouvelle identité. Cela exclut l'explication
« le script a réutilisé seulement l'ancien port déjà énuméré ». Cela ne mesure
ni la phase des horloges internes ni d'éventuels événements PLL après
l'énumération.

## 2. Chaîne de reset présente dans les sources réellement compilées

Lire les fichiers figés de `tang/impl/gpu_usb_hs33_ready_r2/source`, et non
les sources de travail susceptibles d'évoluer.

`tang/rtl/console_top.v:99–126` et `tang/rtl/usb/usb_reset_release.v:4–29` :

1. PLL_F produit 48 MHz depuis 50 MHz ; son entrée reset reste à zéro.
2. `u_usb_ref_start` attend le lock PLL_F synchronisé et 1024 cycles à 48 MHz
   avant de libérer PLL_B.
3. PLL_B produit 960 MHz et 60 MHz. `u_usb_phy_start` attend les deux locks
   et 1024 cycles à 60 MHz.
4. `u_usb_controller_start` attend encore 64 cycles à 60 MHz avant `RESET=0`.

Chaque séquenceur initialise `reset=1`, ses synchroniseurs à zéro et son
compteur à zéro ; l'affirmation sur perte de lock est asynchrone, la
libération enregistrée. La netlist de synthèse conserve ces valeurs INIT et
les trois instances. Elle contient également le GSR fournisseur, relié à
VCC (`impl/gwsynthesis/console_gpu_usb_hs33_ready_r2.vg:129065`). Cette liaison
ne signifie pas que les valeurs d'initialisation FPGA sont absentes ; elle
ne produit pas de pulse de reset utilisateur supplémentaire.

Le reset applicatif vaut `RESET | usb_busreset` : FIFO, configuration CDC,
trace et pont UART y sont raccordés. Cela couvre le défaut antérieur où un
busreset enregistré ne suivait pas immédiatement un reset système lorsque
60 MHz était arrêté. Les tests de reset/CDC précédents couvrent ce mécanisme,
mais ne sont pas une simulation exhaustive du nouveau contrôleur 3.3.

Limites : le séquenceur ne détecte pas un arrêt d'horloge dont le signal lock
resterait haut ; aucun événement de ce type n'est prouvé dans le dernier
essai. Les registres `interface*_alter` ont seulement `RESET`, sans
`usb_busreset` (`console_top.v:207–216`) : différence à garder en revue de
protocole, sans preuve qu'elle explique les corruptions bulk observées.

### L'attente de 64 cycles ne prouve pas une calibration déjà terminée

Le commentaire du top annonce une attente pendant la stabilisation du
diviseur. Le câblage réel est plus précis : le contrôleur reçoit `RESET`, et
son `utmi_reset_o` fournit `PHY_RESET` au PHY (`console_top.v:244–272,290–291`).
Le wrapper contrôleur 3.3 relie `utmi_reset_o` à `usbrst_o`.

Le modèle officiel PHY 3.5 disponible a ses FF de séquenceur effacées par
`rst_i` ; `reset_stop_s2` est effacée et `reset_calib_s2` présélectionnée par
ce même reset. Le séquenceur ne peut donc pas effectuer sa calibration tant
que `PHY_RESET=1`, même si `pll_locked_i` est déjà haut. Les 64 cycles avant
la libération du contrôleur ne constituent pas une preuve de calibration du
PHY pendant cet intervalle. Il manque une trace de la séquence publique
réelle avec le contrôleur 3.3 pour dater cette calibration.

Cette observation ne démontre pas un défaut du contrat Gowin : un contrôleur
peut légitimement attendre la fin du démarrage après sa propre libération.
Elle ne justifie pas à elle seule l'ajout d'un délai ou un reset périodique.

## 3. Comparaison avec l'autre projet USB3

Référence locale lue :
`/home/michael/logic_analyser_wifi/TESTS/TESTS_USB_ANALYSE_2026-09-29.md`,
sections du 2 octobre 16:00 / 16:25, G25b/G26b et 20:01.

Le défaut USB3 établi était `PowerPresent=VCC` associé à un état Compliance
sans nouvelle tentative périodique. Le simple débranchement ne réinitialisait
pas cette machine. G19 ajoute une reprise coordonnée après une seconde
continue en Compliance, sans reset automatique en U0. Ce mécanisme explique
une absence de reprise, distincte d'une corruption après énumération.

G25b/G26b corrige aussi une ancienne fin de payload EP0 qui consommait une
nouvelle réponse. G26b énumère complètement, mais son journal à 20:01 conserve
11 EPROTO sur 43 lectures EP0, et ne qualifie pas encore le bulk. On ne peut
donc pas transposer « USB3 corrigé par le rechargement » en preuve qu'un délai
de reset résoudrait notre défaut HS. La méthode utile commune reste : mêmes
identités binaires, vraie réénumération, reset coordonné et preuve de protocole.

## 4. Calcul du mapping phase modèle → hypothèse STA

Sources : `TESTS/rtl/usb_phy_startup_tb.sv`,
`TESTS/usb_phy_startup_r1_20261002.json`,
`TESTS/USB_PHY_PHASE_REVIEW_20261002.md`.
Ce banc utilise le PHY de référence historique, SHA du VO
`0a0eb5da9cb1c9f859d3cba4aafa4a327356984b0a9f3f2477f8e2c81abd8dd3`,
et les primitives officielles 1.9.12, sans modification ni force interne.
Il n'instancie ni PLL réelle, ni contrôleur, ni délais SDF.

Le modèle `prim_sim.v:13131` de DHCE échantillonne `~CEN` sur quatre fronts
descendants, puis ouvre `CLKIN & ce_reg3`. Le CLKDIV `/8`
(`prim_sim.v:12911`) libère son reset interne au premier front HCLK repris ;
dans la séquence observée, sa première montée suit au deuxième front HCLK.

Avec `T=1000/960 ns`, en prenant comme origine la descente de CEN exactement
sur un front montant commun 60/960, l'ordre idéal est :

| Événement | Temps relatif |
| --- | ---: |
| CEN devient 0 | 0 |
| Quatre échantillonnages descendants DHCE | 0,5T ; 1,5T ; 2,5T ; 3,5T |
| Premier front montant HCLK transmis | 4T |
| Premier front montant CLKDIV/CLKOUT | 5T = 5,208333 ns |

La trace arrondie donne CEN à 2358,333 ns et CLKDIV à 2363,542 ns, puis la
même relation après un second reset public. Les resets CLKDIV sont libérés
alors que HCLK est encore arrêté ; ce n'est pas un simple diviseur qui
continuerait librement pendant un changement de phase 60 MHz.

L'option `LOCAL_PHASE_NS=0.520833333` aligne ici les fronts montants 60/960 ;
l'option zéro ne les aligne pas. Il faut conserver ce fait lorsqu'on compare
les anciens résultats. Le choix du cycle absolu de `PHY_RESET` ne suffit
pas à déterminer la phase : le créneau décisif est la reprise CEN produite
ensuite depuis 60 MHz.

Dans l'audit r29, les sources `PHY_CLKOUT` et `fclk_960M` ont des premières
montées nominales à zéro. Sous cette convention idéale, `5T` correspond bien
à `-divide_by 8 -phase 225`, la phase 5. La formulation équivalente documentée
par SUG940 est `-edges {11 19 27}` : montée à 5T, descente à 9T, montée à 13T.
Ces valeurs traduisent un modèle conditionnel ; elles ne sont pas choisies
pour rendre positif un rapport STA.

### Ce qui empêche encore de sélectionner cette phase sur carte

Définir, aux broches considérées :

- `L60` : latence CLKOUT1 → CLK du FF `reset_stop` ;
- `Dce` : clk→Q de ce FF plus trajet Q → DHCE.CEN ;
- `L960` : latence CLKOUT0 → DHCE.CLKIN ;
- `delta` : phase physique CLKOUT0 par rapport au front de référence CLKOUT1.

Poser `r=L60+Dce-L960-delta`. Le premier front descendant admissible de
DHCE a l'indice entier `n` vérifiant `(n+0,5)T > r`, avec les marges setup,
hold et incertitudes réelles à ajouter. Le modèle sans délais a `r=0`, donc
`n=0`. Après les quatre étages et la reprise CLKDIV, le cycle nominal de
sortie devient `(n+5)T`, modulo `8T`.

Pour garantir le même créneau `n`, tout l'intervalle min/max de `r` doit
tenir strictement entre `(n-0,5)T + hold` et `(n+0,5)T - setup`, après prise
en compte des incertitudes. Pour `n=0`, la frontière nominale supérieure
n'est qu'à **0,520833 ns**. Traverser cette frontière sélectionne un autre
cycle 960 ; attendre davantage avant le démarrage ne supprime pas ce trajet.
Les quatre étages DHCE permettent la propagation de l'activation, mais ne
prouvent pas quel premier front l'accepte.

Les paramètres PLL_B fixent les phases coarse/fine et DT_STEP de CLKOUT0/1
à zéro (`gowin_pll_b.v:102–128`) ; ils ne mesurent pas les latences ci-dessus,
la gigue, ni le contrat physique de capture CEN. Il faut aussi vérifier la
libération RESETN pendant l'arrêt HCLK et le nombre de fronts de reprise
pour la version 3.5 exacte, dont les valeurs initiales ont changé.

### Convention de latence réellement visible dans l'ancien STA

Dans `gpu_usb_phase_audit_r29_r1/impl/pnr/source.tr`, le pire chemin de la
phase 5 part à 13,542 ns de `CLKDIV/CLKOUT`, tCL=0, puis ajoute 3,954 ns vers
IDES16/PCLK. La capture part de PLL_B/CLKOUT1 à 16,667 ns, tCL=0, puis ajoute
3,847 ns vers la FF 60 MHz. La propagation antérieure
PLL_B/CLKOUT0 → DHCE → CLKDIV/CLKOUT n'est pas explicitée dans ces lignes.

Il faut donc vérifier la convention du moteur Gowin et, si nécessaire,
représenter séparément cette latence source amont. Les 3,954/3,847 ns de
distribution aval sont déjà comptées ; les ajouter à nouveau à la waveform
serait incorrect. La trace modèle compare des ports locaux sans ces délais.

L'ancien audit r29 donne −2,226 ns de setup non-Gray à phase 5 et +3,861 ns
de hold. Il ne vaut pas pour le nouveau routage HS33 r2. La marge +0,140 ns
du dernier build ne qualifie pas ces CDC : son SDC déclare encore sclk comme
horloge de base et coupe les relations 60/120/960 par `set_clock_groups`.

## 5. Audit isolé proposé pour resserrer la preuve

L'IP PHY exacte HS33 r2 a pour SHA VG
`2e622a5615b0bb114a6ee44b88fee89ac9302854d5216bf1786389f37a54cd7c`.
Son intérieur est protégé dans la netlist de synthèse. Le VO officiel 3.5
déjà exporté provient d'une autre génération, avec la même configuration,
mais n'est pas un export de ce VG exact : ne pas en affirmer l'identité.

Dans ce VO officiel 3.5 (`gpu_usb_phy35_model_r1/reference/usb2_0_softphy.vo`),
les éléments à résoudre dans la copie HS33 r2 sont, sous le préfixe
`u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs` :

| Élément | Broches à examiner | Preuve disponible |
| --- | --- | --- |
| `u_oser_rst/reset_stop_s2` | CLK, Q | DFFCE, source 60, VO:1633 |
| `dhcen_inst` | CEN, CLKIN, CLKOUT | DHCE, VO:1297 |
| `u_oser_rst/reset_calib_s2` | CLK, Q | DFFPE, VO:1641 |
| `clkdiv_inst` | HCLKIN, RESETN, CLKOUT | CLKDIV `/8`, VO:1302 |
| `u_pll_b/PLL_inst` | CLKOUT0, CLKOUT1 | PLL du top exact |

Le rapport du build exact confirme `clkdiv_inst/CLKOUT` et le scope
`u_oser_rst`, mais pas les broches CEN/reset_stop. Leur résolution doit être
vérifiée par l'outil avant de présenter les rapports comme mesurés sur HS33.

Procédure proposée, sans toucher aux contraintes de production :

1. Copier netlist synthétisée, contraintes résolues et paramètres du build
   exact dans un dossier neuf. Établir les SHA de départ. Préférer une
   réanalyse du routage chargé si l'interface officielle le permet ; sinon
   un P&R diagnostic n'est attribuable au matériel que si le `.bin` obtenu
   est identique au `.bin` du build chargé. L'ancien audit r29 avait satisfait
   cette comparaison ; elle n'est pas encore faite pour HS33 r2.
2. Enlever dans cette copie uniquement la coupe 60/120/960 nécessaire à
   l'analyse. Ne pas masquer le trajet CEN ni ajouter d'exception non-Gray.
   Vérifier explicitement que toutes les broches demandées existent.
3. Demander setup et hold de `reset_stop_s2/Q` vers `dhcen_inst/CEN`, avec
   lancement `PHY_CLKOUT` et capture descendante `fclk_960M`. SUG940 5.5.1
   documente `report_timing`, `-from`, `-to`, `-from_clock` et
   `-fall_to_clock`. Le détail doit exposer L60, clk→Q, trajet CEN, L960 et
   l'arc setup/hold de la primitive. Si CEN n'est pas un endpoint temporisé
   par la bibliothèque, « aucun chemin » doit être classé **non couvert**,
   jamais PASS. Relever également les délais disponibles entre broches,
   sans inventer un arc de contrôle absent.
4. Demander recovery/removal de `reset_calib_s2/Q` vers `clkdiv_inst/RESETN`
   et vérifier la latence de HCLK vers CLKDIV. Un résultat STA périodique
   doit être interprété avec la séquence où HCLK est réellement arrêté ;
   il ne remplace pas cette preuve séquentielle.
5. Calculer les créneaux `n` compatibles avec les bornes min/max rapportées.
   Si une frontière reste franchissable, conserver plusieurs hypothèses et
   rapporter cette ambiguïté. Si un seul créneau est garanti, créer la
   relation sclk correspondante dans l'audit, avec une convention explicite
   pour la latence source amont, puis exposer setup/hold 60↔120 non-Gray.
   Les pointeurs Gray restent séparés dans le classement ; leurs marges
   synchrones ne prouvent pas la sécurité de leur synchronisation.
6. Pour rattacher le calcul fonctionnel au PHY exact, exporter officiellement
   son VG intact puis observer la séquence avec les resets publics réels,
   les deux fronts de PLL et les broches de reprise. Un modèle fonctionnel,
   même exact, restera sans preuve de gigue, métastabilité ou délais silicium.

Syntaxe de départ pour l'étape 3, à utiliser seulement après résolution des
broches dans la copie diagnostique :

```tcl
report_timing -setup -from_clock [get_clocks {PHY_CLKOUT}] -fall_to_clock [get_clocks {fclk_960M}] -from [get_pins {PREFIX/u_oser_rst/reset_stop_s2/Q}] -to [get_pins {PREFIX/dhcen_inst/CEN}] -max_paths 20 -max_common_paths 20
report_timing -hold -from_clock [get_clocks {PHY_CLKOUT}] -fall_to_clock [get_clocks {fclk_960M}] -from [get_pins {PREFIX/u_oser_rst/reset_stop_s2/Q}] -to [get_pins {PREFIX/dhcen_inst/CEN}] -max_paths 20 -max_common_paths 20
```

Ces commandes sont une proposition vérifiable, pas une garantie que Gowin
publie les arcs internes nécessaires. Le rapport à produire devra conserver
les avertissements de broches non trouvées et les chemins non couverts.

## 6. ACK courts et framing : portée par rapport au démarrage

Les mini-bancs 3.4/3.5 démarrent, attendent, reçoivent correctement un ACK
isolé, puis envoient quatre paquets successifs. Les ACK à 40/100 ns sont
perdus, ceux à 200/340 ns acceptés ; aucune collision de pilotage ni X de
ligne n'est observée dans les points échantillonnés. La garde se réarme
après chaque TX : cette observation ne se réduit pas à un premier paquet
envoyé trop tôt après reset.

La première K est allongée sur le premier TX seulement, mais les ACK courts
échouent aussi après un TX dont la première K a la durée nominale. Le modèle
a d'autres différences de framing et certaines phases locales ne passent
pas même le témoin ACK isolé. Il n'établit donc pas à lui seul le signal
électrique réellement reçu par le PC.

Les mesures intégrées précédentes donnent un délai de réponse supérieur à
400 ns pour le PHY Normal 3.4, réduit avec Advance ; Advance reste défaillant
sur carte. Ces bancs n'utilisent pas le nouveau contrôleur 3.3 ni la chaîne
PLL physique complète. Les résultats soutiennent un examen de la réception,
du retournement et des CDC ; ils ne démontrent pas une cause unique et ne
justifient pas un déphasage matériel choisi sans mesure.

## 7. Exécution de l'audit isolé et limite constatée

Deux stages nouveaux ont été créés, sans modification de HS33 r2 :
`gpu_usb_cen_audit_hs33_r1` et `gpu_usb_cen_audit_hs33_r2`. Les VG synthétisés,
CST résolus et fichiers `.p` de référence ont été copiés avec SHA vérifiés.
Le Tcl demande un P&R incrémental depuis cette copie et l'export officiel VO.
Seule la coupe asynchrone USB 60/120/960 est retirée dans le SDC diagnostic.
Les autres contraintes restent conservées.

Les premiers lancements ont rencontré successivement l'absence du backend
Qt xcb utilisable, puis l'impossibilité de vérifier le hostid de licence
dans la sandbox (`AF_NETLINK`). L'exécution effective a été reprise hors
sandbox par la session principale, avec les bibliothèques de l'installation
Gowin 1.9.12 et `QT_QPA_PLATFORM=offscreen`. Aucun autre processus Gowin n'a
été géré par cet audit.

### r1 : arrêt au début du STA

Placement et routage atteignent 90 %, puis `run pnr` retourne le code 1
au début de l'analyse temporelle, sans erreur nommée dans le journal.
Les filtres `-mod_ins` et `-fall_to_clock` sont documentés dans le guide
SUG940 livré avec cette installation. Le journal ne permet pas d'attribuer
l'arrêt à l'un d'eux, à un endpoint de clock/reset ou à leur combinaison.
Aucun `.bin`, rapport `.tr` ou modèle `.vo` final n'est disponible.
Preuve : `TESTS/usb_cen_audit_hs33_r1_20261002.json`.

### r2 : P&R terminé, broches exactes, aucun chemin CEN rapporté

Le même Tcl et les mêmes copies d'entrées sont conservés dans un nouveau
stage. Les rapports personnalisés sont limités à deux commandes simples,
setup et hold, depuis `reset_stop_s2/Q` vers `dhcen_inst/CEN`, sans filtre de
front ou de module. Cette exécution termine avec le code 0 et produit le
VO officiel, SHA-256
`a59c6ae26d40eee82994a88fa681d1363175d8528efb8114dc3b207d7edf6fc3`.

L'export `impl/pnr/source.vo` établit désormais les noms et connexions de
l'IP exacte de départ :

- ligne 63893 : DHCE reçoit `fclk_960m` sur CLKIN et `reset_stop_Z` sur CEN ;
- ligne 64229 : `u_oser_rst/reset_stop_s2` est une DFFCE, cadencée par
  `phy_clk`, effacée par `PHY_RESET`, dont Q pilote directement ce CEN ;
- lignes 63898–63909 : CLKDIV divise par huit, son HCLKIN vient du DHCE,
  CALIB vaut zéro et RESETN vient de l'inverseur de `reset_calib_Z` ;
- ligne 64237 : `reset_calib_s2` est une DFFPE avec PRESET=`PHY_RESET`.

Ces connexions confirment les noms utilisés : aucun avertissement de broche
introuvable n'est présent. Le `.tr:2620–2621` marque les deux demandes
`TC_REPORT_TIMING Actived`. Pourtant les tables `.tr:128–132` indiquent
`Nothing to report!`, et les détails `.tr:210–214` indiquent respectivement
`No setup paths to report!` et `No hold paths to report!`.

**Interprétation limitée :** le moteur ne fournit aucun chemin temporisé CEN
avec cette requête et ce modèle de primitive. Ce n'est pas une faute de nom
établie, ni la preuve d'une marge positive. L'export fonctionnel explicite
les quatre étages internes du DHCE via la primitive, mais cela ne garantit
pas qu'un arc setup/hold de contrôle soit exposé par le moteur STA.
L'absence d'arc exploitable et une limitation de résolution/requête du
moteur ne peuvent pas être départagées davantage par ces sorties. Aucun
délai min/max CEN, aucune fenêtre physique de capture n'est donc mesuré.

L'identité de configuration requise échoue également :

| Fichier `.bin` | SHA-256 |
| --- | --- |
| Référence HS33 r2 | `8b00121f27c153707a278cb70e27a72c3e69adaa262108ae9571ed430527eef0` |
| Audit CEN r2 | `aad2249943b9fb1e82cad9dd4dac30f9c95a93eb02ef40ac60745d52b0247158` |

Les deux fichiers font 4 958 100 octets ; 11 135 octets et 24 666 bits
diffèrent. L'option de reprise incrémentale n'a donc pas préservé l'identité
de la configuration. Les délais du routage diagnostic ne seraient pas
attribuables directement au bitstream de référence, même si CEN était
rapporté. Aucun SDF n'a été produit ; l'export VO n'apporte pas les bornes
physiques manquantes.

Extraction reproductible :

```sh
python3 tools/check_usb_cen_timing.py tang/impl/gpu_usb_cen_audit_hs33_r2 --output TESTS/usb_cen_audit_hs33_r2_20261002.json
```

Le JSON conserve SHA, avertissements, demandes actives, messages de chemins
absents, connexions VO et différence binaire. Son état `routing_differs`
signifie que l'identité requise n'est pas satisfaite ; les deux couvertures
CEN restent explicitement fausses. Aucun balayage de phase supplémentaire
n'a été lancé et aucune phase physique n'a été sélectionnée à partir de
ce résultat. La limite est archivée pour une éventuelle demande fournisseur
sur les arcs temporels CEN du DHCE et la réanalyse du routage exact.

## 8. Nouvelle validation matérielle, distincte de la preuve de phase

La session principale a ensuite testé `gpu_usb_hs33_ep0_r1`, SHA du bitstream
`e838aa90263c34df3521d495f9c819b70162fb1aa02dfeb3370d1e487b80360e`,
marge minimale +0,139 ns. Les résultats archivés établissent :

- trois rechargements SRAM, nouvelles adresses 107, 108 et 109, chacun
  à 480 Mbit/s, configuration 1, deux interfaces ;
- pour chacun, 100 tours de stress et 544 100 octets binaires exacts,
  soit 1 632 300 octets pour les trois essais ;
- après le troisième chargement, 300 requêtes EP0 consécutives réussies.

Preuves : `TESTS/usb_ax15_20261002/usb_hs33_ep0_r1/result.json`, ses journaux
`load*/usb.log`, et `usb_hs33_ep0_r1_controls/result.json`.

Cette amélioration est démontrée pour la nouvelle image et les séquences
testées. Elle n'identifie pas à elle seule la part du correctif logique EP0
et celle des changements de placement/routage. Elle ne transforme pas le
mapping fonctionnel 5T en mesure de phase physique et ne qualifie pas
automatiquement l'ensemble de la console vidéo.
