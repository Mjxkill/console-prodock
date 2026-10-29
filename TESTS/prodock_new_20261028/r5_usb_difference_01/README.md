# USB G22 / R3 / R5 : comparaison hors carte des implémentations exactes

La comparaison ne révèle **aucun changement de paramètres des deux PLL USB,
du CLKDIV ou des sérialiseurs/entrées-sorties critiques**. Il existe néanmoins
des différences réelles de netlist et de délais publiés. Elles ne permettent
pas encore d'attribuer la panne à une cause précise.

Root a communiqué les observations matérielles suivantes sur la nouvelle
Pro Dock 2025071717 : G22 exact négocie 480 Mbit/s, 10 lectures EP0 et une réponse
CPU de 87 octets passent; R5 n'émet aucun événement attach pendant deux essais
de 120 s; R3, avec ancienne IP/ROM, échoue aussi pendant 60 s. Ces résultats
appartiennent au protocole matériel root, pas à cet audit sans matériel.
Le retour final à G22 reproduit le PASS USB/CPU une deuxième fois. Les
preuves matérielles sont dans [le rapport root](../r5_hardware_01/README.md).
Ils montrent que la nouvelle ROM/IP régénérée n'est pas nécessaire à l'échec.
Ils ne prouvent ni une cause de timing, ni une panne intrinsèque de FPGA.

## Identités et méthode

| VO post-routage | SHA256 |
|---|---|
| G22 exact | `0d8715a85d66b6029460dd87b83fb3cc5db1c9a6fe63fea9de508b406bc0025e` |
| R3 | `753ee718dc02141ac174313687e129a8f7b4bb8928cc48841eb95c514e9e6a1c` |
| R5 | `7d6150318d7d69d81c6e7f58438dea3f149fd8157ab63c7916cbdf1931052e23` |

`extract.py` lit les primitives publiques des branches USB et PLL_F/PLL_B,
leurs ports et leurs defparams. Il conserve les différences littérales,
sans confondre renommage et équivalence. `physical_evidence.py` compare les
arcs INTERCONNECT publiés, options et tableaux de broches. Aucun fichier
RTL, contrainte ou construction n'a été modifié; aucun Gowin n'a été lancé.

Les **18 008 primitives USB/PLL de R3 et R5 sont exactement identiques** par
nom, type, ports et paramètres (`r3_r5_usb_comparison.json`). Cette égalité
de graphe public ne prétend pas extraire les routes physiques chiffrées.

## Paramètres, broches et resets

Les 14 primitives critiques communes sont : PLL×2, IBUF×2, IOBUF×2,
ELVDS_IOBUF, TBUF, CLKDIV, DHCE, IDES8×2, IDES16 et OSER16. Tous leurs
paramètres explicites concordent, notamment diviseurs, phases/configurations
PLL, DIV_MODE=8 du CLKDIV et modes sérialiseurs. Aucun changement de paramètre
de calibration n'apparaît dans ces primitives. Cela n'observe pas la valeur
effective d'un compteur ou d'un état de calibration sur la carte.

Deux connexions critiques changent de nom/construction :

- Le TBUF de pull-up reçoit dans G22 un OR(`rst_usb`,`PHY_RESET`) suivi d'un
  inverseur; dans R5 il reçoit le NOR direct des mêmes deux signaux. La
  fonction booléenne est identique, mais le nombre de LUT et la route du
  signal ne le sont pas. OEN du TBUF garde le même net nommé.
- RESETN du CLKDIV change de nom de net et de LUT. Les deux LUT1 INIT=1
  calculent `!reset_calib_Z`. HCLKIN, CALIB, CLKOUT et DIV_MODE sont inchangés.

Les cellules FF des séquenceurs `u_usb_ref_start`, `u_usb_phy_start`,
`u_usb_controller_start` et `u_oser_rst` ne présentent pas de différence
de ports/paramètres dans cette comparaison. Les garde-reset des périphériques
MSC/UTNA analysés dans `../r5_qualification_01/usb_cdc_review` ne deviennent
pas automatiquement une explication de la panne d'énumération.

Les 9 lignes USB du tableau **All Package Pins** sont identiques : sites,
IO_TYPE, niveaux de bank, résistances, drive et CTLE. Les 18 lignes globales
restent identiques, dont les régions PRIMARY des clocks et les deux régions
HCLK 960 MHz. Le tableau «par port» de l'ancienne version omet les deux entrées
LVDS : cette différence de format n'est pas une différence de brochage.

Les contraintes INS_LOC des PLL restent F=PLL_R[2], B=PLL_R[1]. Ce sont des
placements imposés; l'export public ne donne pas toutes les coordonnées
des cellules/branches. Les fichiers .p/.pr contiennent les blocs chiffrés
du fournisseur. Aucune tentative de déchiffrement n'a été effectuée.

## Différences de netlist qui restent bornées

G22 et R5 comptent chacun 18 008 cellules sélectionnées. Pour les noms communs,
927 cellules diffèrent littéralement ; 15 noms disparaissent et 15 apparaissent.

- 835 différences touchent uniquement I3 d'ALU : 592 en mode ADD 0 et 243 en mode SUB 1.
  Le modèle officiel ne lit pas I3 dans ces modes. L'indépendance est testée
  exhaustivement sur I0/I1/CIN/I3. Cette conclusion ne s'étend pas à ADDSUB 2.
- 92 autres cellules diffèrent, avec 105 ports différents, dont 8 LUT aux INIT ou
  permutations d'entrées différentes. Certaines différences sont des
  inversions absorbées/renommages, mais **l'équivalence séquentielle globale
  de ces 92 cellules n'est pas revendiquée**. Les données brutes sont conservées.

La contre-analyse DeepSeek confirme les deux fonctions critiques ci-dessus,
avec deux mutations d'INIT qui doivent rendre les fonctions différentes,
et détecte une mutation ODIV0_SEL de la PLL. Elle n'affirme pas que le reste
du graphe, les délais ou la calibration analogique seraient qualifiés.

## Délais et options : ne pas mélanger les niveaux de preuve

Les SDF n'emploient pas exactement le même outil/modèle :

| | G22 | R5 |
|---|---|---|
| Gowin | V1.9.12 | V1.9.12.03 |
| Voltage SDF min:nom:max |0.94:0.90:0.85 |0.93:0.90:0.87 |
| Température |85:25:0 |85:25:0 |

Parmi 65 911 arcs USB communs par endpoints, 54 586 triplets diffèrent, dont
8 237 arcs vers CLK/PCLK/FCLK/CLKIN. Exemples **nominal SDF en ns** :

| Arc | G22 | R5 |
|---|---:|---:|
| Pullup enable LUT → TBUF/OEN |1,079|1,916|
| Clock board IBUF → PLL_F/CLKIN |3,639|3,275|
| PLL_F/CLKOUT0 → PLL_B/CLKIN |2,501|2,251|
| DHCE/CLKOUT → OSER16/FCLK |2,777|2,499|
| PLL_B/CLKOUT1 → controller reset FF/CLK |2,697|2,428|
| phy_lock_reset FF/Q → controller reset FF/PRESET |1,576|1,630|

Ce sont des valeurs annotées du fournisseur, pas des mesures carte. Un delta
peut refléter des branches/routages ou des modèles modifiés; cette comparaison
seule ne sépare pas ces effets. Les régions d'horloge identiques ne prouvent
pas l'identité de chaque branche. Aucun faux chemin n'a été ajouté et aucune
violation n'a été effacée du rapport.

Après retrait des chemins d'identité, les options PnR sont les mêmes. R5
emploie en plus son ancre PR R4 incrémentale. Différence unique de device.cfg :
G22 contient `set background_programming = off`, ligne absente dans R5.
Le comportement implicite de la version récente et son éventuel effet ne
sont pas établis ici; l'absence de cette ligne n'est pas déclarée causale.

## Mission externe et correction du banc

DeepSeek V4.1 Flash, une session OpenCode exécution, 54 requêtes, 92 outils,
427,547 s. Le statut enregistré reste **FAILED** : 4 tests agent et 2 tests
superviseur en échec. Les copies temporaires créées par le banc héritaient
du mode 0444 des entrées protégées; le test de mutation ne pouvait donc pas
les modifier. **Ce défaut du contrat/banc est de notre responsabilité,
pas un défaut fonctionnel du modèle.** Aucune nouvelle session n'a été lancée.

Le code/rapport final, les métriques et les échecs restent intacts. Le banc
indépendant `owner_review/validate_fixed.py` ajoute seulement chmod 0600 aux
copies temporaires avant mutation, sans changer les assertions : PASS sur
le code final inchangé. Sa provenance et son journal sont enregistrés.
La revue indépendante vérifie aussi les 32 combinaisons des équations ALU
mode 0/1 contre un calcul direct. Elle relève une limite générique du parseur
DeepSeek : la priorité de `&` et `^` est inversée pour une expression mixte
sans parenthèses. Ce cas ne figure pas dans les équations officielles 0/1 ni
dans les deux cônes LUT évalués. Le contre-exemple reste consigné dans
`owner_review/evaluation.json`; cet analyseur n’est pas promu comme moteur
d’équivalence Verilog général.

Tous les processus de la mission sont terminés. Les nouvelles sources font
moins de 1 000 lignes. Pas de score de qualité automatique.

## Prochain contrôle utile sans nouveau bitstream

Le comparatif matériel G22/R3/R5 est déjà discriminant contre l'hypothèse
«nouvelle ROM uniquement». Pour relier la panne à une étape précise, il faut
maintenant observer sur un candidat défaillant des états **existants** :
locks PLL, rst_usb, reset_calib et enable pull-up, puis préciser ce que ces
observables mesurent. Selon les moyens réellement accessibles à root,
lecture d'un diagnostic existant ou mesure du pull-up est préférable à
une nouvelle variante de placement. Ne pas supposer que des compteurs UTNA
nuls prouvent l'absence de clock ni que CPU bloqué implique PLL_USB bloquée.

Cette fiche ne prescrit ni nouveau bitstream, ni modification de routage,
ni patch de reset avant cette localisation. Les limites STA historiques
et celles de R5 restent séparées de la preuve de la cause matérielle.
