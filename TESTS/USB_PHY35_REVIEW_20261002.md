# Revue du PHY USB 2.0 Gowin 3.5 — 2 octobre 2026

## Périmètre et statut

Le PHY 3.5 Advance est exporté depuis **une copie intacte du VG de
`tang/impl/gpu_usb_phy35_r3/usb_phy_ip`**. Les netlists fermées, les primitives,
le banc, le firmware et les contraintes de production ne sont pas modifiés
par cette comparaison. Aucun chargement sur carte n'est effectué ici.

**Configuration confirmée par le GUI officiel 3.5** : pour GW5AST-138B,
UTMI, Single, Advance et TX Delay 0, les defines réellement émises sont
`module_name USB2_0_SoftPHY_Top`, `GW5AT`, `UTMI`, `TX_DELAY_0_BIT`, `V_120`.
Elles sont identiques à celles du build r3, à l'ordre près. Les nouvelles macros
`DEF_DHCE` et `DEF_DHCEN` ne sont pas émises pour ce composant. Les trois fichiers
vendor compilés par r3 sont aussi identiques aux fichiers lus par le GUI.
Les résultats ci-dessous qualifient exactement ce VG, pas toutes les
configurations 3.5.

La session GUI a utilisé un écran Xvfb privé et ses propres répertoires XDG,
sous `tang/impl/gpu_usb_phy35_gui_r1`. IPC, fichier de defines, projet de synthèse
et captures y sont conservés ; cette GUI et son Xvfb sont arrêtés. Aucun réglage
de session utilisateur n'a été volontairement modifié. Preuve et empreintes :
[`usb_phy35_gui_configuration_20261002.json`](usb_phy35_gui_configuration_20261002.json).

## Mise à jour officielle et export

L'installation `/home/michael/gowin/IDE` déclare l'IP **3.5** dans
`ipcore/USBTwoSoftPHY/usbtwosoftphy.ipspec`. La note locale
`doc/RN100-1.9.12.03E_Gowin Software Release Note.pdf`, page imprimée 3,
annonce l'ajout du GW3A-20 et un ajustement des paramètres de délai d'E/S.

Les clés de configuration publiques restent `rx_mode`, `lvds_mode`,
`interface` et `tx_delay`. Les chaînes de macros supplémentaires du générateur
concernent les familles et le gating ; aucune nouvelle option utilisateur de
garde RX ou de phase n'a été identifiée. Cette observation sur les interfaces
publiques ne prétend pas décrire le contenu RTL chiffré.

L'export utilise Gowin `gw_sh` 1.9.12 et son option officielle
`set_option -gen_verilog_sim_netlist 1`, dans le projet isolé
`tang/impl/gpu_usb_phy35_model_r1`. Le P&R de ce petit projet permet l'export
fonctionnel ; il ne représente pas le placement de la carte complète.

| Objet | SHA-256 |
|---|---|
| VG matériel r3, copie de travail et companion `.v` | `a612c6417caa5795fc975eb611b16ed9298c4d4d03822dfea2197d54aea6818c` |
| VO officiel exporté | `efff800d24f2fe86b307b6845dd2e026ed0054d5e27fbdf69d0f4995396d7cb8` |

Procédure, sources et empreintes :
[`usb_phy35_model_generation_20261002.json`](usb_phy35_model_generation_20261002.json).

## Mini-banc PHY seul

Le banc `rtl/usb_phy_turnaround_tb.sv` est repris sans changement, phase locale
nulle. Il vérifie d'abord la réception exacte d'un ACK au repos, puis émet le
même DATA0 `c3 ea c1 30` et présente un ACK après la fin électrique du paquet.

| Cas | 3.4 Advance | 3.5 Advance |
|---|---|---|
| ACK au repos | reçu, octet `d2` exact | reçu, octet `d2` exact |
| ACK après 40 ns | perdu | perdu |
| ACK après 100 ns | perdu | perdu |
| ACK après 200 ns | reçu | reçu |
| ACK après 340 ns | reçu | reçu |
| Collision/OEN actif pendant l'ACK, X, désaccord de ligne observés | 0 | 0 |
| Écarts de framing sur quatre TX | 5 | 5 |

Les trois ACK reçus apparaissent **16,667 ns plus tôt à l'UTMI** en 3.5.
Les horodatages TX, la largeur de la première K et la fin d'EOP sont identiques
dans ce témoin. Le 3.5 a aussi été exécuté avec les primitives officielles
1.9.12.03 : sa sortie est identique à celle obtenue avec les primitives 1.9.12.
Toutes les empreintes de sources avant/après concordent.

Résultats complets et commandes :
[`usb_phy_turnaround_35_advance_r1_20261002.json`](usb_phy_turnaround_35_advance_r1_20261002.json).

## Réponses du contrôleur intégré

Une simulation utilise le snapshot `gpu_usb_phy35_r3/source`, le companion VG
identique et le VO exporté : ACK après 20 cycles UTMI, hôte et carte nominaux,
phase hôte 0,317 ns, phase locale 0, OUT intercalés. Le banc et le contrôleur de
référence sont ceux du test 3.4 Advance. Les observateurs internes spécifiques
au PHY Normal sont automatiquement désactivés ; les horodatages de ligne
restent actifs et aucun stimulus n'est changé par cette désactivation.

| Mesure | 3.4 Advance | 3.5 Advance |
|---|---:|---:|
| Réponses reliées à leur transaction hôte | 273 | 272 |
| EOP hôte → première K device | 372,078–376,245 ns | 355,411–359,579 ns |
| Réponses au-delà du budget nominal 192 bits / 400 ns | 0 | 0 |
| Données IN / OUT exactes | 131 / 524 | 131 / 524 |
| ZLP | 0 | 0 |
| Écarts de framing | 280 | 279 |
| Verdict global du banc | FAIL | FAIL |

Le gain de 16,667 ns est cohérent avec la réception UTMI plus précoce du
mini-banc. Les réponses incluent les DATA0/DATA1 et NAK d'EP2 IN, et les ACK
des DATA0/DATA1 OUT. La différence d'une réponse provient du sondage adaptatif
du banc ; les deux sorties ne sont pas des listes de transactions identiques.

Preuve complète :
[`usb_controller_response_phy35_advance_r1_20261002.json`](usb_controller_response_phy35_advance_r1_20261002.json).
Comparateur :
[`usb_controller_response_advance_r1_20261002.json`](usb_controller_response_advance_r1_20261002.json).

## Lecture structurelle et limites

Dans le VO 3.5, lignes 1297–1315, `DHCE.CLKIN=fclk_i` et
`CEN=reset_stop_Z`, puis le CLKDIV `/8` reçoit cette horloge et
`RESETN=!reset_calib_Z`, comme en 3.4. Le compteur `q_tx_cnt0` est toujours
cadencé par `sclk` (lignes 4643–4698) et le terme de seuil utilisant les bits
4/5 avec `LUT INIT=0007` reste présent (lignes 3459–3466). Cette observation
est cohérente avec la garde qui perd encore les deux ACK courts dans le modèle.

Il s'agit de simulations fonctionnelles sans SDF, sans modèle analogique du
réseau RC et sans mesure de la PLL physique. Le VO a une résolution de 100 ps ;
les décimales supplémentaires des journaux sont des horodatages du simulateur.
Les modèles présentent toujours des écarts de framing et une sensibilité de
phase déjà documentée. La comparaison ne démontre donc ni la conformité USB
physique, ni l'absence d'amélioration des délais d'E/S sur silicium. Elle montre
un gain de latence de réception, et **aucune suppression de la perte d'ACK à
40/100 ns dans ce modèle**.

## Résultat matériel transmis par la session principale

Après cette validation des macros, la session principale a chargé r3 sur la
Pro Dock, série `2023112818`. Le chargement SRAM est terminé, la liaison
négocie 480 Mbit/s et le timing enregistré a une marge minimale de +0,139 ns.
Le test échoue cependant dès le premier tour de 64 octets : deux insertions
(indices 21 et 58 dans la séquence attendue), puis les deux derniers octets
reportés après la lecture. La bannière présente également des doublons.

Le bitstream essayé est identifié par SHA-256
`f3c5797e6a2acd0762f6c891f1478f3e799f86105bf0d765110df03fb6569e52`
et 94 sources figées. Voir
[`usb_phy35_r3/result.json`](usb_ax15_20261002/usb_phy35_r3/result.json)
et le journal `usb_ax15_20261002/usb_phy35_r3/load1/usb.log`.

**Le PHY 3.5 Advance, correctement configuré, ne corrige donc pas l'instabilité
matérielle observée.** Le gain de latence fonctionnelle ne suffit pas à établir
la cause de ces erreurs. Tous les processus de cette revue sont terminés ;
les chargements, mesures et restaurations de la carte sont gérés séparément
par la session principale.
