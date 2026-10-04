# Comparaison officielle PHY 3.4 Normal / Advance

Le mode Advance réduit la latence de décodage du modèle, mais **ne corrige pas
les ACK courts perdus après émission** dans le mini-banc. Aucune modification
du PHY fermé, de ses primitives, du firmware, des PLL ou du SDC de production.
Aucun accès à la carte pour ce lot ; tous les processus sont terminés.

## Configuration et identité

Le [guide officiel IPUG781-1.7E](https://www.gowinsemi.com/upload/database_doc/2125/document/687a7263eb932.pdf)
documente RX_Mode Normal à 60 MHz et Advance à 120 MHz, ce dernier destiné aux
Arora V avec des exigences de timing accrues. TX Delay 0/1/2 règle l'activation
de sortie ; ce n'est pas un réglage documenté de la fenêtre de reprise RX.
Le générateur installé expose Normal/Advance, la clé `rx_mode` et la macro
`V_120`. L'ajout de cette macro est la seule différence de configuration ;
TX_DELAY_0_BIT, UTMI, GW5AT et le mode Single LVDS sont conservés.

Génération et commandes : `TESTS/usb_phy_advance_model_generation_20261002.json`.
Le dossier isolé est `tang/impl/gpu_usb_phy34_advance_model_r1`.
La synthèse indépendante ayant produit un SHA différent, le modèle effectivement
testé provient d'une **copie intacte du VG matériel** dans `hardware_reference`,
suivie de l'export officiel Gowin avec `-gen_verilog_sim_netlist 1`.

- VG de `gpu_usb_advance_r1/usb_phy_ip` et copie utilisée :
  `363d18af0556baeaff5dd5b0d0ed1da5a7a1298fb7803dd9c865db0fb49728a9`.
- VO officiel exporté et testé :
  `c35605a5684c8c2d2b1305ff32188e029b33f29a78a8756ad7a8451eb2f7d686`.

Cette identité rattache la logique du modèle au PHY de l'image matérielle.
Le placement PHY seul et l'absence de SDF ne représentent pas le timing de
l'image complète.

## Mini-banc et résultats

Banc : `TESTS/rtl/usb_phy_turnaround_tb.sv`.
Rapport final : `TESTS/usb_phy_turnaround_advance_r4_20261002.json`.
Commandes exactes, SHA avant/après, sorties et résultats par cas sont conservés.
Chaque run utile simule 38,446 µs ; aucune énumération ni contrôleur USB.
Seuls les ports publics pilotent le PHY. L'OEN de la primitive originale est
observé sans forçage interne.

Avec phase locale 0, le témoin ACK isolé fournit exactement `d2` à UTMI dans
les deux modes. Chaque émission donne exactement `c3 ea c1 30`, CRC compris.

| Délai ACK depuis le retour électrique SE0 | Normal | Advance |
| ---: | --- | --- |
| 40 ns | Aucun octet RX | Aucun octet RX |
| 100 ns | Aucun octet RX | Aucun octet RX |
| 200 ns | `d2` exact | `d2` exact |
| 340 ns | `d2` exact | `d2` exact |

La latence du témoin ACK isolé diminue de 83,333 ns avec Advance. Le code de
retour zéro des runs utiles signifie que les contrôles de données du banc ont
abouti ; il ne signifie pas conformité complète USB, puisque deux ACK sont
perdus et des différences de tramage restent présentes.

La lecture du VO Advance explique pourquoi doubler la fréquence ne suffit pas :
`q_tx_cnt0` est cadencé par sclk120 (lignes 4679–4734), mais son seuil utilise
les bits 5/4, soit 48, via `n3096_s6` INIT `0007` (lignes 3302–3309).
Le modèle Normal utilise un seuil 24 à 60 MHz. Le budget temporel de cette
temporisation est donc conservé ; seule la fréquence du compteur ne permettait
pas de prédire une reprise RX plus rapide.

## Pilotage du bus et tramage

La primitive officielle `ELVDS_IOBUF` (`prim_sim.v:927`) emploie `bufif0` /
`notif0` : OEN=1 libère la paire. Dans les quatre cas, cette libération coïncide
avec le retour SE0 mesuré ; à l'envoi de l'ACK, OEN vaut 1 depuis exactement
40/100/200/340 ns. Aucun échantillon ne constate un pilotage simultané, un X ou
une valeur des broches différente de celle de l'hôte. L'ACK à 40 ns reste perdu.
Le modèle ne maintient donc pas le driver actif pendant 200 ns après EOP.

L'observation des conflits est échantillonnée à 960 MHz, 50 ps après le front
pour éviter les courses avec les arrondis du stimulus. Elle ne prouve pas
l'absence de tout événement arbitrairement bref. Le rapport r3 comptait douze
écarts de comparaison au voisinage des transitions du cas 100 ns, sans X ni
OEN actif ; leur disparition après déplacement de la seule sonde est consignée
par r4, sans modification des stimulus ou du PHY.

Dans les deux modes, la première K dure 6,25 ns sur la première émission, puis
environ 2,083 ns sur les suivantes. Le retour SE0 arrive environ 12,5 ns après
la fin EOP attendue par le décodeur. Cela donne cinq différences de tramage
pour quatre paquets, identiques entre Normal et Advance. Ces différences
interdisent de qualifier tout le lien à partir des seuls octets corrects.

## Limites de phase et de précision

À phase locale 0, les témoins passent comme décrit. En décalant seulement
960 MHz de 0,520833333 ns, **le témoin ACK isolé échoue dans les deux modes**,
même après 30 µs d'attente. Le premier rapport r1 utilisait cette phase et une
attente plus courte : cet échec initial ne distinguait donc pas les modes.
Cette sensibilité du modèle/banc reste à expliquer avant d'extrapoler au
silicium. Aucun verdict physique ne découle de cette seule comparaison.

Le VO officiel est à résolution 100 ps ; les primitives utilisent 1 ps.
Les nombreuses décimales des traces sont des horodatages du simulateur et ne
constituent pas une précision électrique démontrée. Aucun réseau RC, délai
analogique de comparateur, SDF, métastabilité ou PLL réelle n'est simulé.

## Indice distinct : délai de réponse du contrôleur

Extraction : `TESTS/usb_phy_normal_response_latency_extract_20261002.json`.
Dans les huit premiers IN du précédent log Normal3.4 ACK20, les tokens
`69 07 41` permettent de reconstruire EOP depuis SOP+64 bits. Le premier octet
TX accepté par UTMI arrive 358,016 ou 374,683 ns après cet EOP.

Le présent mini-banc mesure ensuite 64,062 à 68,229 ns entre ce premier octet
accepté et la première K. Combiner ces deux observations suggère une réponse
vers 422–443 ns, mais **ce n'est pas une mesure directe du délai intégré** :
le log ancien ne contient pas la première K. Le prochain test intégré devra
horodater explicitement EOP hôte et SOP FPGA, et vérifier la limite applicable,
avant d'attribuer les erreurs xHCI à ce délai.

Le prochain réglage TX_DELAY peut évaluer le début de tramage. Aucun réglage
officiel identifié ici ne permet de raccourcir explicitement la temporisation
RX. Une amélioration partielle du modèle ne constituerait pas une correction
définitive sans reproduction du symptôme et validation sur carte.
