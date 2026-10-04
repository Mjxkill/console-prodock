# Localisation des erreurs IN à vide — 3 octobre 2026

## État final de cette série

La carte conserve le GPU complet `gpu_l12_usb_hs33_idle_r3`, en SRAM,
avec la démonstration affine animée. Dix chargements ont énuméré en HS480.
Les sept chargements testés avec données passent 140 tours CDC au total,
soit **761 740 octets binaires exacts**, hors échos des suites graphiques.
Trois de ces chargements sont testés directement, sans sondage préalable.
La suite graphique complète passe sur les chargements 4 et 10 : DDR avec
cache, G0–G6, FAST, L11 et L12, environ 55 images/s et aucun underflow.

**Le défaut intermittent ne s'est pas reproduit dans cette série. Sa
cause initiale reste non démontrée.** La modification ajoute une trace
passive indépendante de l'USB et des registres d'entrée aux observateurs ;
elle modifie aussi le placement/routage. Aucun défaut physique du PHY
n'est déclaré corrigé sur cette seule base. Les anciennes erreurs xHCI
et les marges CEN conditionnelles restent consignées ci-dessous.

## Point de départ mesuré

La capture `usb_xhci_cdc_r4_blocks_20261003/analysis.json` comporte 687
erreurs de transaction : EP2 IN80, EP3 IN605, EP02. Douze précèdent le
premier OUT E, dont deux sur EP3 sans producteur. Première erreur à
67,415ms du début des lectures. Aucun nouveau diagnostic EP0 n'est envoyé
avant les échos ; EP0 final échoue et ne donne aucune trace FPGA.

Les revues indépendantes du RTL ouvert n'ont pas trouvé de contre-exemple
sur le chemin EP3 vide stable. L'ancien banc du contrôleur HS3.3 a vérifié
90NAK EP3 mais dure6,697ms, sans PHY ni polling/SOF réaliste sur une longue
durée. Il ne démontre donc pas la validité du chemin matériel observé ici.

## Nouvelle observation passive

`tang/rtl/usb/usb_idle_trace.v` n'a aucune sortie vers le contrôleur,
le PHY ou les FIFO des données du jeu. La fenêtre AHB `0xE9002000` est
accessible par le J-Link506005083 déjà confirmé sur cette Pro Dock.
Le GPU complet, le firmware et les fréquences restent conservés.
L'ajout change le placement/routage : une amélioration de comportement
entre les deux images ne suffirait pas à démontrer une correction USB.

L'observateur vérifie le PID IN69, trois octets UTMI, le CRC5, l'adresse
armée et l'endpoint2/3. Il mesure le délai entre la fin RXACTIVE observée
à60MHz et le premier TXVALID puis la première acceptation TXVALID/TXREADY.
Une acceptation au même front vaut0cycle. La résolution est16,667ns ;
ce délai n'est pas celui mesuré entre EOP et SOP sur le câble.

Le token suivant, même EP0, autre adresse, OUT, SETUP, SOF ou PING,
termine le contexte précédent. L'endpoint est capturé au début TX.
Une réponse EP0 ne peut donc pas être comptée comme réponse EP3.
Les NAK comptés sont exactement un octet5a accepté à UTMI suivi de la fin
TXVALID. Cela ne prouve pas leur émission ou leur réception électrique.

L'absence de début de réponse est relevée après127cycles, une émission
inachevée après1023cycles. Ce sont des seuils d'observation, pas des
temporisations ajoutées au protocole. Ils ne servent pas à juger la
conformité temporelle USB. Les DATA EP2 normaux ont au plus64octets de
payload dans cette intégration. Le premier défaut et quatre événements
récents sont conservés. Les réponses anormales comprennent PID inattendu,
NAK non unitaire, DATA tronqué et DATA EP3 alors que cet endpoint est vide.

Les commandes80→60MHz et les snapshots60→80MHz traversent deux FIFO
double horloge à pointeurs Gray. Reset commun, assertion asynchrone,
maintien local et attente de reprise du domaine distant : aucune ancienne
commande ne doit ressortir après une horloge arrêtée. Chaque commande
renvoie32mots ; la banque devient lisible lorsque busy retombe à0.
Les lectures AHB ont un cycle d'attente local et n'attendent jamais USB.

## Registres et format

| Offset AHB | Rôle |
|---|---|
| 00 | ID55544e41, «UTNA» |
| 04 | bit0 busy ; bit1 commande refusée pendant busy |
| 08 | Nombre de banques complètes reçues |
| 0c | Commande : bit0 clear+arm ; bit2 disarm ; adresse USB bits14:8 |
| 40..bc | 32mots du snapshot |

Toute commande renvoie un snapshot ; la valeur2 sert au snapshot seul.
Le clear+arm renvoie l'état **avant** clear, puis arme les compteurs.
Ne lire les32mots qu'après busy=0, sans lancer une nouvelle commande.

| Mot | Valeur |
|---|---|
| 0..2 | ID, format1, commande ayant demandé le snapshot |
| 3 | Cycles depuis l'armement |
| 4..5 | IN reçus valides EP2/EP3 à l'adresse armée |
| 6..7 | NAK unitaires acceptés EP2/EP3 |
| 8..9 | Réponses de PID DATA EP2/EP3 |
| 10..11 | IN sans réponse terminée EP2/EP3 |
| 12 | Réponses anormales |
| 13 | Cycles RXERROR, tous endpoints |
| 14 | Tokens de PID IN avec erreur de forme/CRC/RX, avant filtre adresse |
| 15..17 | Fronts reset USB, SOF, cycles TXVALID sans TXREADY tous endpoints |
| 18..19 | Dernier token brut ; dernière réponse avec endpoint/longueur/PID |
| 20 | Maximum délai NAK offert bits7:0, accepté bits15:8, saturation255 |
| 21..28 | Quatre événements64bits, plus récent en premier |
| 29..30 | Premier défaut64bits |
| 31 | Adresse bits6:0, pending bit9, armed bit10 |

Événement64bits : timestamp token[63:32], valid31, absence30,
réponse anormale29, CORK28, endpoint27:24, PID23:16,
délai accepté15:8 saturé255, longueur acceptée7:0 saturée255.
DATA et réponse anormale peuvent se recouvrir : un DATA EP3 est à la fois
compté comme DATA3 et signalé comme défaut.

## Validation et protocole matériel

`usb_idle_trace_r3_20261003/result.json` : PASS quatre rapports/phases,
dont80/60MHz, inversé et125/124,5MHz. Cas : CRC incorrect, erreur RX,
mauvaise adresse, NAK avec attente TXREADY, DATA, absence de réponse,
NAK mal formé, réponse EP0 intercalée, réponse au front token_end,
PID ACK inattendu, TXVALID bloqué, snapshot stable, refus commande
concurrente, lectures AHB consécutives et reset avec chacune des horloges
arrêtée. Revue indépendante CDC/AHB et protocole effectuée.
ABI USBDEVFS_URB du script hôte comparée à l'en-tête Linux natif : PASS.

`tools/check_usb_idle_board.py` identifie exactement359f:2011/11252024
à480Mbit/s et vérifie l'ID de la trace avant toute écriture MMIO. Il
détache temporairement cdc_acm, arme viaJ-Link, sonde les seuls endpoints
demandés pendant1s, puis récupère le snapshot et réattache cdc_acm.
Aucun OUT, EP0 privé, clear-halt, changement de configuration ou resetUSB.
Les URB IN vides doivent rester pending sous NAK ; leur annulation en
fin de fenêtre est normale. Le statut retourné par usbfs distingue une
erreur de protocole d'une simple absence de données.

Chaque comparaison EP3 seul / EP2 seul / les deux doit partir d'un
rechargement indépendant du même bitstream, avec répétition si nécessaire.
Interprétation : token absent à UTMI ne distingue pas encore absence sur
le câble et réception PHY défaillante ; token reçu sans réponse acceptée
cible le contrôleur/handshake ; NAK correct remis au PHY avec erreur hôte
cible son émission, sa qualité ou son timing. Aucun de ces compteurs ne
remplace une capture électrique.

La trace survit au reset du bus USB mais pas à la perte de LOCK/rst_usb
ni au reset système. Une nouvelle adresse USB impose un nouvel armement.
Les compteurs32bits peuvent déborder ; les durées de test sont courtes.

L'historique ci-dessous conserve les trois routages et leurs résultats.
Seul `gpu_l12_usb_hs33_idle_r3`, conforme aux vérifications de timing
décrites, a été chargé sur la carte.

### Premier routage et isolation de l’observation

idle_r1 n’a pas été chargé :199violations dans PHY_CLKOUT, minimum
-4,643ns. Le chemin critique entre testmode du contrôleur et CE du PID
de la trace passe par la boucle combinatoire TXVALID→PHY→TXREADY,
puis4,990ns de fil et la logique du nouvel observateur. Tous les autres
domaines ont zéro violation dans ce rapport.

Pour idle_r2, les28signaux UTMI/état sont échantillonnés ensemble dans
un registre avant leur analyse. La sortie de ce registre n’alimente
que l’observateur. RX et TX subissent exactement le même retard d’un
cycle, sans changer les délais relatifs mesurés ni le protocole USB.
Les quatre simulations repassent (`usb_idle_trace_r3_20261003`).
Le GPU complet idle_r2 a ensuite été compilé ; SDC inchangé.

### Piste CEN : faits et limites du SDF exact cdc_r4

Le wrapper PLL_B est identique octet pour octet à Sipeed : SHA256
`eebf97752d1453b6297d6526d0dbe04c46db4545dd0107046d3526df22caa521`.
Sorties960/60MHz, ODIV0=1/ODIV1=16, phases statiques0. Le guide officiel
[UG306](https://cdn.gowinsemi.com.cn/UG306E.pdf), §4.1/4.3/5.1, ne donne
pas de nouvelle recette garantissant le créneau d'acquisition de CEN
issu d'une bascule60MHz.

SDF routé exact cdc_r4, délais min/typ/max en ns : CLKOUT1→CLK reset_stop
1,433/2,630/3,828 ; CLK→Q0,141/0,262/0,382 ; Q→DHCE.CEN
0,414/0,910/1,405. Sommes corrélées1,988/3,802/5,615. Les contraintes
setup et hold CEN descendant sont0,162/0,174/0,186. Sous l'hypothèse
d'alignement des sorties PLL et du trajet CLKOUT0→DHCE.CLKIN nul tel
qu'exporté, les marges calculées sont hold typ-0,018ns et setup max
-0,072ns. Ce sont des marges conditionnelles : les arcs PLL sont aussi
exportés àzéro et ne certifient ni phase physique ni incertitude.

Rapprocher la bascule pourrait changer le créneau de démarrage du
CLKDIV ; une amélioration de trois points PVT ne prouverait pas un
créneau stable pour toutes les conditions. Aucun changement arbitraire
de phase, placement CEN ou fréquence n'est appliqué sur cette hypothèse.

### Vérification de l'accès J-Link

Sur le cdc_r4 toujours chargé, J-Link506005083 lit E9000000=47505531
(ID GPU), puis reprend le cœur. Journal ax15 :
`TESTS/usb_idle_jlink_precheck_20261003/read.log`. Cet accès AHB fonctionne
même sur le chargement où le diagnostic EP0 a échoué. Il ne valide pas
encore la nouvelle fenêtre UTNA, qui doit être testée après chargement.

### Deuxième routage

idle_r2 : la nouvelle trace n'a plus de chemin en violation dans le
rapport. Restent16violations sur les registres tail de l'ancien
`usb_packet_trace`, marge minimum-0,129ns. L'image n'est pas chargée.
Le même pipeline d'entrée, portant tous les signaux et événements
ensemble, est ajouté en option à cet observateur et activé dans le top.
Le mode par défaut garde le comportement direct. Les historiques des
deux modes CAPTURE_FIRST0/1 sont comparés à chaque cycle : même contenu
avec un cycle de retard, resets inclus. Preuve :
`usb_packet_trace_pipeline_20261003.json`. Ce changement définit idle_r3.

### Routage final idle_r3 et première observation sur carte

idle_r3 passe :110chemins détaillés, minimum+0,138ns, zéro violation
setup/hold.100sources figées vérifiées. SHA256 bitstream :
`0de67614918e1c7b6e67d86886de7334dbaba00dd9bb1d92d0ba7e699fa30483`.
SDF exact :18bits Gray de la trace, maximum CLK→Q+fil1,363ns et écart
conservateur0,871ns ;12bits du pont DDR, maximum1,446ns et écart0,946ns.
Fils des deux synchroniseurs de reprise d'horloge : max0,901 et0,783ns.
Cela vérifie leur borne de propagation, pas une MTBF analogique ni les
traversées internes du PHY fermé. SDC production inchangé.

Chargement SRAM identifié FTDI2023112818, DONE puis nouvelle énumération
HS480. L'ID UTNA et les snapshots sont lisibles via J-Link. Le premier
essai utilisait à tort le devnum Linux8 comme filtre : il observe SOF
et activité TX, mais zéro IN sélectionné. **Ce résultat est inconcluant.**
Le noyau distingue devnum et devaddr sous xHCI ; références primaires :
[hub.c choose_devnum](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/core/hub.c)
et [xhci.c xhci_setup_device](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/usb/host/xhci.c).

Le script balaie désormais passivement les filtres d'adresse du seul
observateur pendant des IN sur les endpoints demandés. Cela n'envoie
aucun SET_ADDRESS ni commande à un autre périphérique. L'adresse unique
observée est42, pas8. Le mode --wire-address permet d'éviter ce balayage
lorsque l'adresse réelle est connue ; un snapshot sans aucun IN
sélectionné est désormais rejeté.

Sur ce premier chargement, après découverte, fenêtre EP3 seul d'une
seconde :8006IN et8006NAK unitaires, zéro DATA3, zéro absence de réponse,
zéro réponse anormale, zéro RXERROR et zéro token IN invalide. Délai
maximal offert3cycles60MHz, accepté7cycles. Aucune completion usbfs
pendant la fenêtre ; annulation finale normale(-2). Pas de preuve
d'absence de récupérations xHCI internes ni de stabilité entre démarrages.
Preuves : `usb_ax15_20261002/usb_idle_r3_ep3_boot1_20261003/` (filtre erroné)
et `usb_idle_r3_ep3_boot1_wire_20261003/` (adresse corrigée).

### Chargements 2 à 4 et premiers transferts CDC

Chaque chargement est effectué en SRAM sur FTDI2023112818, avec
vérification du SHA et nouvelle énumération HS480. Fenêtres d'une seconde :

| Chargement | Adresse sur le bus | Endpoints | IN / NAK |
|---|---:|---|---:|
| 2 | 43 | EP3 seul | 8 006 / 8 006 |
| 3 | 41 | EP2 seul | 46 716 / 46 716 |
| 4 | 44 | EP2 et EP3 | EP2 : 46 437 / 46 437 ; EP3 : 8 006 / 8 006 |

Dans ces trois fenêtres : aucun DATA, aucune réponse absente ou anormale,
aucun RXERROR, aucun IN invalide et aucun reset bus. Les URB restent en
attente puis sont annulées normalement. L'adresse 44 supposée au chargement
3 ne correspondait pas à l'adresse réelle : ce premier essai est rejeté
comme inconcluant ; le balayage passif trouve ensuite 41. L'adresse sur le
bus ne se déduit donc ni du devnum Linux ni d'un incrément attendu.

Au chargement 4, les 20 tours CDC (tailles 1, 64, 256, 1 024, 4 096)
reçoivent **108 820 octets binaires exacts**. La trace armée avant le test
et lue par J-Link après indique 557 511 IN2, 447 498 NAK2, 110 013 DATA2,
76 812 IN3/NAK3, zéro absence de réponse, réponse anormale, RXERROR,
IN invalide ou reset bus. La séquence passe de 257 à 258 (armement), puis
259 (snapshot et désarmement). Le snapshot décrit l'état avant désarmement,
d'où `armed=true` dans son contenu. Ces résultats ne prouvent pas encore
l'absence d'erreurs internes récupérées par xHCI ni la stabilité durable.

Preuves sous `usb_ax15_20261002/` :
`usb_idle_r3_ep3_boot2_20261003`, `usb_idle_r3_ep2_boot3_wire_20261003`,
`usb_idle_r3_mixed_boot4_20261003`, `usb_idle_r3_cdc_boot4_20261003`.

### Comparaison CEN après routage idle_r3

Revue indépendante, sans changement de sources : les paramètres PLL_B et
les arcs internes DHCE/CLKDIV restent identiques. Arrivée CEN min/typ/max :
cdc_r4 = 1,988 / 3,802 / 5,615 ns ; idle_r3 = 1,852 / 3,578 / 5,303 ns.
Le routage avance donc CEN de 136 / 224 / 312 ps, principalement par le
trajet reset_stop.Q vers CEN. Sous les hypothèses conditionnelles précisées
plus haut, la marge minimale typique passe de -18 ps hold à -106 ps setup,
de part et d'autre du front descendant idéal à 3,645833 ns.

Le nouveau routage pourrait changer le créneau acquis au démarrage ;
**il ne ferme pas cette marge conditionnelle** et ne prouve pas une phase
physique correcte. L'amélioration des essais à vide ne suffit donc pas à
attribuer ou déclarer résolu le défaut USB. Aucun réglage arbitraire de
phase, fréquence ou placement CEN n'est appliqué.

### GPU complet sur le chargement 4

`usb_ax15_20261002/usb_idle_r3_gpu_boot4_20261003/` : suite complète
`check_gpu_console.py` réussie, code de retour 0. Tests DDR avec cache
(masques, adresses et trois passes de 1 Mio), G0 à G6, FAST, L11 et L12 :
16 surfaces complètes, 64 sprites, triangles, tuiles, course et affine,
images de référence et gardes exactes, accès CPU à la DDR en parallèle,
aucun underflow. Course 55,08 à 55,41 images/s ; affine 54,94 à 54,99.

Trace UTMI pendant toute la suite : 3 533 087 IN2, 3 510 685 NAK2,
22 402 DATA2 ; 604 909 IN3 et autant de NAK3. Aucun RXERROR, IN invalide,
reset bus, absence de réponse ou réponse anormale. Le compteur de temps
32 bits à 60 MHz a fait un tour pendant ce test ; les nombres de paquets
et la séquence de snapshot restent valides. L'animation affine est
relancée par le test, avant la série de rechargements suivante.

### Rechargements 5 à 7 avec trace indépendante

`usb_ax15_20261002/usb_idle_r3_cdc_boots5_7_20261003/` contient le script
exact utilisé, chaque rapport de chargement, les captures J-Link et les
résultats CDC. Les trois chargements passent, chacun en HS480 et avec
20 tours CDC, soit 108 820 octets exacts par chargement.

| Chargement | Adresse sur le bus | IN2 | NAK2 | DATA2 | IN3 = NAK3 |
|---|---:|---:|---:|---:|---:|
| 5 | 45 | 555 006 | 444 973 | 110 033 | 76 811 |
| 6 | 50 | 559 865 | 449 832 | 110 033 | 76 794 |
| 7 | 51 | 552 222 | 442 189 | 110 033 | 76 811 |

Tous les compteurs d'anomalie et `first_fault` restent à zéro. Avant chaque
stress, le sondage EP2+EP3 d'une seconde ne produit aucune completion
inattendue. Les identités, commandes et séquences de snapshot sont
vérifiées ; aucun reset ni changement d'adresse ne survient pendant le
stress. Ces essais incluent une découverte d'adresse et un détachement /
rattachement du pilote CDC avant les données. Une dernière série lance
donc le stress directement après chargement, pour vérifier aussi le chemin
d'utilisation normal sans ce sondage préalable.

### Rechargements 8 à 10, usage direct sans sondage

`usb_ax15_20261002/usb_idle_r3_direct_boots8_10_20261003/result.json` :
PASS. Chaque chargement vérifie l'identité FTDI, le SHA du bitstream,
les 100 sources figées, le rapport de timing et une nouvelle configuration
HS480. Le stress commence dès la détection du port CDC, sans J-Link,
sondage brut, découverte d'adresse ni requête EP0 privée préalable.
20 tours et 108 820 octets exacts pour chacun des trois chargements.

La suite GPU complète repasse après le dernier chargement. L'animation
affine reste active à la fin. Port `/dev/ttyACM1`, topologie 3-7,
devnum Linux 18 ; l'adresse sur le bus n'a pas été recherchée et ne doit
pas être supposée égale à 18. Les traces UTMI détaillées des chargements
4 à 7 ne doivent pas être attribuées à cette dernière série directe.

Aucune nouvelle capture xHCI privilégiée ni coupure d'alimentation n'a
été effectuée sur idle_r3. En cas de récidive, conserver d'abord le
chargement fautif pour récupérer la trace J-Link ; éviter de remplacer
immédiatement le bitstream et de perdre l'état utile au diagnostic.
