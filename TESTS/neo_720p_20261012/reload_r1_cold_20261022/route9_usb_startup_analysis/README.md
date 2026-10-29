# Observation USB du démarrage Neo, sans nouveau bitstream

Le témoin V13 montre maintenant que R9 peut affirmer `ddr_init` tout en
restant inaccessible par DMI. La prochaine observation discriminante est
déjà câblée dans les deux bitstreams : quatre niveaux de démarrage sont
lisibles sur EP0, indépendamment des horloges et resets du CPU. Cela ne
suppose ni le fonctionnement de la console série, ni un accès AHB/DDR.

Les mesures matérielles EP0 restent à faire. L'absence de câble, d'énumération
ou de réponse USB ne permettra aucune conclusion sur la PLL AE350.

## Résultat A/B/A conservé

Le [résultat utilisateur figé](../r9_led_compare_trial/result.json) conserve
`protocol_passed:true`, `led_comparison_conclusive:false` : la réponse finale
ne formulait pas explicitement un nouvel état on/off. Le
[supplément caméra indépendant](../r9_led_compare_trial/camera_observations.json)
consigne séparément les trois JPEG identifiés par SHA, l'identification
initiale de la LED, la confirmation R9 « Oui, allumée en continu », puis la
mire et la même LED revenues après restauration. Aucun résultat n'a été
réécrit pour confondre ces deux modes d'observation.

Les faits associés sont : R9 exact `1593a2…e2fde` chargé avec DONE, LED V13
allumée et écran noir avant DMI ; TAP identifié mais DMI expiré après 30 s ;
N56r8 restauré, CPU de nouveau accessible, +62 images et checksum
`1ff8f800`. L'inférence visuelle, fondée sur la fonction routée
`led_n = !ddr_init`, est `ddr_init=1` pendant l'observation R9. Ce n'est pas
une validation de la mémoire ni une mesure des transitoires ou de la fréquence.

## Preuve de l'observateur déjà présent

[verify_routed_diagnostic.py](verify_routed_diagnostic.py) contrôle les FS et
VO exacts, les sources contre leur manifeste, et 20 primitives complètes
par build, notamment les deux étages de synchronisation des quatre bits,
leur capture EP0, les PLL USB, les sorties de leur séquencement reset,
le FF de reset CPU et les entrées POR/HW de l'AE350.

La [preuve JSON](routed_diagnostic_proof.json), SHA
`544dc367ee0c26a078d92dc92d716a3deda8150789fe52c815ed10a8ba0fa28a`,
contient les chemins absolus, SHA, broches, paramètres et lignes du VO.
Elle passe sur les deux builds. Ce PASS est structurel, pas matériel.

Les sources R9 pertinentes, sous
`tang/impl/console_neo_n56r9_route9_dma_c150/source/`, sont :

| Point | Référence | Conséquence |
|---|---|---|
| PLL USB F puis B | `tang/boards/neo/soft_usb.vh:36–55` | Référence 50 MHz, PLL dédiées, sortie `phy_clk`, sans entrée de reset CPU |
| Reset application USB | `soft_usb.vh:62,78` | `rst_usb | usb_busreset`, sans `vid_hrstn` |
| Identité propre Neo | `soft_usb.vh:189–193` | `359f:2011`, série `NEO00001`, produit `MegaNeo Console` |
| Synchronisation des états | `soft_usb.vh:311–317` | Deux FF sur `phy_clk`, reset USB seulement |
| Placement dans la réponse | `soft_usb.vh:333–335` | États dans les bits 159:156 du snapshot |
| Requête et page diagnostic | `tang/rtl/usb/uart/usb_uart_config.v:83–104` | Clé D1A6, réponse 32 octets |
| Capture au SETUP | `usb_uart_config.v:137–140` | Un snapshot pour chaque nouvelle requête |
| Ordre des octets | `usb_uart_config.v:305–308` | Octet faible d'abord, puis indices croissants |
| Définition des trois bits SoC | `tang/rtl/board/ae350_soc.v:150–155` | STOP DDR, lock DDR filtré, reset CPU commun |

Le contrôleur USB reçoit `rst_usb` et produit son reset bus/PHY. Les resets
des interfaces **AHB** USB/MSC utilisent effectivement `vid_hrstn`, mais
ces interfaces ne participent pas à la réponse de diagnostic EP0.
Le VO confirme `usb_app_reset = rst_usb | PHY_RESET` : `PHY_RESET` est
l'alias routé de la sortie reset du contrôleur, pas le reset du CPU.

## Lecture minimale

[read_ep0_startup.py](read_ep0_startup.py), SHA
`40037e3a8901b9742f26c55e82ba0161264f08ad3fd6996f4ec7936220e412aa`,
prend lui-même `TESTS/neo_board.lock`. Le port physique **et** l'adresse
USB courante sont obligatoires. Il exige l'identité Neo complète et le
debugger unique `2025041420`, rejette la Pro Dock `11252024`, les doublons,
les changements d'adresse et les changements d'identité entre requêtes.
Le lien physique du port choisi doit être identifié par l'opérateur.

Depuis la racine du dépôt, contrôle local sans sysfs/USB/verrou :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_usb_startup_analysis/read_ep0_startup.py --check-only
```

Lecture N56r8, après apparition et identification du port ; remplacer les
deux paramètres par le port sysfs et l'adresse réellement observés :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_usb_startup_analysis/read_ep0_startup.py \
  --usb-port PORT_SYSFS --usb-address BUS:DEV --expected-build n56r8 --samples 3 \
  --out TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_usb_startup_analysis/n56r8_ep0_01.json
```

La seule transaction de contrôle émise est :
`bmRequestType=A0, bRequest=21, wValue=D1A6, wIndex=0000, wLength=32`,
timeout 1 s. Trois lectures espacées de 100 ms par défaut. Aucun CDC ouvert,
aucun détachement/claim de pilote, SET_CONFIGURATION, reset USB, JTAG,
commande GPU ou écriture DDR. L'ouverture usbfs est `O_RDWR`, nécessaire à
`USBDEVFS_CONTROL` même pour une requête IN. Le SETUP sélectionne EP0 et
capture un snapshot : il n'est pas sans effet sur le trafic USB concurrent.

Une réponse doit contenir exactement 32 octets et `raw[23] == 0xd1`.
Le nibble vaut `raw[19] >> 4`, soit `LE32(raw[16:20]) >> 28` :

| Bit du nibble | Champ | Sens exact |
|---|---|---|
| 3 | `pll_ae350_filtered_lock` | Lock filtré par `PLL_INIT`, pas simplement le LOCK brut |
| 2 | `ddr3_stop_enclk2` | Niveau STOP fourni par l'IP et raccordé à ENCLK2 de la PLL DDR ; ne pas inverser son sens au décodage |
| 1 | `pll_ddr_filtered_lock` | Lock filtré de la PLL DDR |
| 0 | `ae350_por_hw_rstn` | `init_sync[1]`, net commun aux entrées POR_N et HW_RSTN de l'AE350 |

Les octets bruts, les huit mots et tous les champs sont archivés même si
leur interprétation est inhabituelle. Un niveau constant n'est pas une
mesure de fréquence ; quatre synchroniseurs distincts ne constituent pas
une photographie atomique des transitoires.

## Interprétation après comparaison avec N56r8

| R9, LED DDRinit allumée | Ce que la mesure départage | Ce qui reste à établir |
|---|---|---|
| Lock AE350=0, reset CPU=0, stables | Le reset CPU est encore affirmé ; le lock filtré n'est pas acquis | LOCK brut, état PLL_INIT et raison de l'absence de lock |
| Lock AE350=1, reset CPU=0, stables | Le lock filtré est affirmé, mais la chaîne de libération CPU n'a pas abouti | Activité réelle bus80, séquence `ae350_rst_sync`, `init_sync`, transitoires/reset physique |
| Lock AE350=1, reset CPU=1, stables | Les niveaux fabric de lock et de libération POR/HW sont affirmés | Core800/RTC/DDR_CLK effectifs, reset interne AE350, domaine DMI et accès debug |
| Lock AE350=0, reset CPU=1, persistants | Combinaison incohérente avec l'état stable attendu du RTL | Capture/CDC/timing/transitoires avant toute interprétation causale |
| Pas de réponse EP0 valide | Aucune mesure de ces quatre états | Câble, port, énumération, alimentation du lien, PHY/contrôleur USB |

La chaîne reste : lock AE350 filtré → deux FF `ae350_rst_sync` sur bus80 →
`rst_key_n` → deux FF `init_sync` sur AHB échantillonnant DDRinit → POR/HW
AE350 → HRESETN du bloc dur → `vid_hrstn` → logique scanout. La LED saute
précisément les étapes entre DDRinit et le reset CPU ; EP0 renseigne leur
entrée lock et leur sortie reset sans modifier le bitstream.

Les [comparaisons statiques déjà conservées](../route9_startup_analysis/README.md)
ne prouvent pas une cause physique : primitives ciblées identiques,
horloges AE350 déclarées identiques et routes PLL→CORE/AHB/APB identiques ;
pas de hausse particulière du délai max reset CPU propre à R9. Ces résultats
n'excluent ni un transitoire, ni une violation de marge, ni un problème de
démarrage interne. Les échecs setup/recovery R9 sont conservés et ne sont
pas transformés en preuve de panne DMI.

## Validation locale

`python3 -B .../test_read_ep0_startup.py` : **5 tests PASS**, sans matériel.
Ils couvrent les 16 combinaisons du nibble, signature et longueurs invalides,
transaction IN exacte et timeout, réponse tronquée, refus Pro Dock/adresse/
doublon/traversée de chemin, et `--check-only` sans découverte matérielle.
Le contrôle local des identités de preuve et fichiers figés passe également.
Aucun nouveau routage ni build, aucune modification des outils communs.

## Si N56r8 ne s'énumère pas : observateur AHB existant

N56r8 conserve `u_usb_idle_trace` dans le VO. `CONSOLE_NO_USB_TRACE` n'est
pas défini. La fenêtre E9002000 offre ID `55544e41`, statut à +04 (busy bit0,
commande rejetée bit1), compteur de captures à +08, banque de 32 mots à
+40..BC. Une lecture seule ne déclenche pas de capture. Depuis reset, la
banque vaut zéro et l'observateur n'est pas armé.

**ID zéro ne signifie pas forcément module absent.** Dans
`usb_idle_trace.v:25–34`, le reset local AHB reste affirmé tant que les deux
domaines AHB et PHY n'ont pas échangé leur libération de reset. Le reset
d'entrée est `vid_hrstn && !rst_usb`. Un ID zéro avec CPU/mire fonctionnels
peut donc résulter d'un `rst_usb` affirmé, d'un domaine PHY inactif ou d'un
échange des libérations non abouti. Il ne mesure pas la PLL AE350.

[probe_n56r8_usb_ahb.py](probe_n56r8_usb_ahb.py), SHA
`e19e9bdb38c89e9c681e02cd61e6ae2076ce93cf293de67db7dc828644f63f72`,
est préparé mais non exécuté par son auteur. Il vérifie les SHA de l'ancre
A/B/A, les fichiers figés, Neo/ESP uniques, puis garde CPU garé en M/satp0,
ROM parking exacte, géométrie et mire N56r8. Il prend le verrou Neo,
utilise 100 kHz et borne chaque processus OpenOCD à 30 s. `--read-only`
effectue seulement les trois lectures ID/statut/compteur après la garde.

Sans `--read-only`, il exige ID correct et statut idle, écrit seulement
E900200C=1 (clear/arm cible0), attend 1 s, écrit 2 (snapshot), puis 4
(disarm). Chaque commande doit produire une nouvelle banque cohérente et
incrémenter le compteur. ID absent, busy ou rejected interdisent la
commande ; aucun reset ne masque ces états. Une erreur après mutation
tente seulement un disarm de cet observateur s'il est identifié et idle.
Un timeout/interruption tue et attend son propre processus avant cette
tentative, également bornée à 30 s. Le CPU n'est jamais repris.

| Mot de banque | Adresse | Observation |
|---|---|---|
| 3 | E900204C | Ticks PHY pendant l'armement |
| 13 | E9002074 | Cycles RXERROR, pas nombre de paquets |
| 14 | E9002078 | Tokens IN malformés |
| 15 | E900207C | Fronts de reset bus USB |
| 16 | E9002080 | Pulses SOF décodées |
| 17 | E9002084 | Cycles TXVALID sans TXREADY |
| 18 | E9002088 | Dernier token sélectionné par l'observateur |
| 19 | E900208C | Dernière réponse EP2/EP3 observée |
| 31 | E90020BC | Armed bit10, pending bit9, cible bits6:0 |

La cible0 sélectionne uniquement les IN EP2/EP3 pour les compteurs de
transactions ; ticks, resets, SOF et RXERROR ne sont pas filtrés par cette
adresse. Ce diagnostic ne capture donc pas intégralement les transactions
d'énumération EP0. Les captures renvoient l'état **avant** l'effet de la
commande : la banque du disarm peut encore porter armed=1 ; la commande4
acquittée établit sa désactivation selon le RTL vérifié.

`test_usb_ahb.py` : **3 tests PASS** en 0,023 s, exécutant le Tcl exact
contre un faux MMIO : lecture seule même pour ID0/busy, refus avant écriture
si ID absent/busy/rejected, commandes1/2/4 limitées à E900200C et parsing.
`--check-only --read-only` passe sans accès matériel. Le lecteur n'est pas
un remplaçant de la qualification matérielle ni une mesure disponible sur
R9 lorsque son DMI reste inaccessible.
