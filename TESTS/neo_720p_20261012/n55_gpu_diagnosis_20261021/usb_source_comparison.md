# SOFT-USB Neo : comparaison des sources figées, 21 octobre 2026

Audit en lecture seule, sans accès à aucune carte et sans modification du RTL,
des contraintes ou des builds. Le résultat reproductible est
`usb_source_audit.json`, produit par `usb_source_audit.py`.

## Écart établi dans les IP réellement compilées

La synthèse `console_neo_n56_observe` utilise les fichiers
`source/tang/rtl/usb/usb2_0_softphy.v` et `usb_device_controller.v` : les deux
entrées sont présentes dans `build.tcl` **et** dans le journal de synthèse.
N56r1/r2/r3 réutilisent cette même netlist de synthèse.

Ces deux fichiers Neo sont identiques octet par octet aux IP de l'exemple
Sipeed local `TangMega-138KPro-example/usb2_soft/usb_uart_loopback`.
Leurs en-têtes indiquent Gowin V1.9.10.03 et novembre 2024. Les `.ipc` de cet
exemple indiquent `target_device=gw5ast138b-007`.

La référence Pro Dock G22r0 contient des artefacts régénérés sous V1.9.12.03
le 8 octobre 2026, à partir du chantier `gpu_sdusb_c28`. Ses métadonnées
archivées indiquent Controller 3.3 et SoftPHY 3.5. Les empreintes diffèrent :

| IP | Neo N56 | Pro Dock G22r0 |
| --- | --- | --- |
| SoftPHY | `9b66def6f3a9d00b3cfa847c4a47d2477256aa960e03aea550b513b28aca12b8` | `7cd9b5e94609641dd416983a828167f67a550ff93df743535187c553c3332865` |
| Controller | `e853517d97ebe55617c4b8cf0fb82b398d33f9af87a4f082e2c079ef4a142a49` | `2c56657ab783f8d79faee0587d66c9dd8d88bbd146966cc41765b3d5b9f11c7b` |

La phrase de `soft_usb.vh` affirmant que les modules sont les mêmes que sur
Pro Dock ne décrit donc pas ces deux artefacts. Cela établit une divergence
d'intégration/version ; cela **ne prouve ni un défaut de ces IP ni leur
incompatibilité avec le 138C**, et ne démontre pas la cause de l'absence
d'énumération. Le contenu chiffré n'a pas été déchiffré.

## Horloges, resets et raccordement

Les sources des PLL F et B sont identiques à celles de G22r0. Elles génèrent
48 MHz depuis l'entrée 50 MHz, puis 960 MHz et 60 MHz. Les trois blocs
suivants sont identiques après retrait des commentaires et des espaces :

- séquence PLL F / attente 104000 cycles / PLL B / attente 104000 cycles /
  libération locale du contrôleur après 64 cycles à 60 MHz ;
- instanciation complète du contrôleur USB ;
- instanciation complète du PHY HS, dont `rst_i=PHY_RESET|rst_usb` et
  `pll_locked_i=~rst_usb`.

Les constantes et définitions de N56 activent le PHY HS et la trace USB ;
aucun `CONSOLE_USB_FS_PHY`, `CONSOLE_USB_FULL_SPEED` ou
`CONSOLE_NO_USB_TRACE` n'est activé dans ce build. La déclaration USB est
359f:2011, numéro de série NEO00001. Un indicateur interne `highspeed` n'est
pas une preuve de vitesse négociée par l'hôte.

Le brochage Neo figé et le rapport PnR N56r1 concordent : TX J19/H19,
RXDP H17/H18, RXDN H20/G20, pullup M17, terminaisons J16/AB16. Il correspond
au relevé antérieur des schémas Sipeed 32001A/C consigné dans
`TESTS/NEO_720P_20261012.md`. Cet audit n'a pas rouvert indépendamment les PDF.
Les broches USB hôtes manettes M15/M16 et H13/G13 sont distinctes.

PLL F est sur R[2], PLL B sur R[1], comme dans G22r0 ; l'exemple Sipeed
utilise R[1]/R[0], car il n'intègre pas le même SoC. Les contraintes Neo
réservent BUFG2/3/4/7 aux horloges PHY60/960/48/sclk120. Ces différences de
ressources ne suffisent pas à conclure à un défaut.

## Autres différences et limites

Seize fichiers du répertoire USB sont identiques entre Neo et G22r0 ; trois
diffèrent : les deux IP ci-dessus et `usb_msc_port.v`. Ce dernier remplace
des distributions directes du reset par les releases locales `hr[2]` et
`ur[2]`. Les FIFO/descriptor/guard/reset-release sont identiques.

L'exemple Sipeed fixe aussi les deux IDES8 sur les entrées RX et un groupe
de registres DRU. Ni la référence G22r0 ni le CST Neo ne recopient ce groupe
DRU à l'identique ; G22r0 ajoute cependant des placements ciblés de FIFO et
du récepteur HS. Ce fait appelle une lecture des chemins et de leur contexte,
pas une transplantation de coordonnées entre boîtiers.

La source seule ne donne pas l'état physique des verrous PLL, de la sortie
pullup, du reset PHY ni des entrées UTMI. L'absence de périphérique dans
`lsusb` et l'ancien état MMIO 0x46 avec trace nulle sont des constats fournis
par le parent et les journaux historiques ; aucune nouvelle mesure n'a été
effectuée dans cet audit. Avant un nouveau routage USB, il faut identifier
quel de ces étages ne progresse pas, puis isoler l'alignement des IP avec
la référence Pro Dock dans un candidat Neo figé distinct.
