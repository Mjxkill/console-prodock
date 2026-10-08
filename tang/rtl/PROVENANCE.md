# PROVENANCE — netlists fermées et IP externes (2026-09-26)

Les fichiers chiffrés/fermés de `tang/rtl/usb/` et `tang/rtl/ddrtest/` viennent du dépôt
officiel Sipeed `TangMega-138KPro-example` (Apache 2.0 / CC BY-SA 4.0), copiés tels quels :

- `usb2_0_softphy.v` — netlist `USB2_0_SoftPHY_Top` (USB2 soft PHY, 9 broches + RC) —
  `usb2_soft/usb_uart_loopback/src/usb2_0_softphy/usb2_0_softphy.v`
- `usb_device_controller.v` — netlist `USB_Device_Controller_Top` (CDC-ACM, 16 EP) —
  `usb2_soft/usb_uart_loopback/src/usb_device_controller/usb_device_controller.v`
- `usb_descriptor.v` — source ouverte, modifiée ? NON : copie exacte de
  `usb2_soft/usb_uart_loopback/src/usb_descriptor.v` (les paramètres strings sont passés par
  l'instanciation, pas modifiés dans le fichier).
- `gowin_pll_f.v`, `gowin_pll_b.v` — PLLs générées par Gowin 1.9.10.03, copiées de l'exemple.
  **PLL_F modifiée localement (E1)** : CLKOUT1/2 activés (100/400 MHz pour le DDR3) — voir le diff.
- `uart/`, `integer_division/` — sources Sipeed/Gowin. Instrumentation
  temporaire L12 dans `uart/usb_uart_config.v` sous `CONSOLE_USB_DIAG` :
  accès de contrôle privé à un instantané de compteurs indépendamment de
  l'UART, sans changer la réponse CDC ordinaire. Les compteurs passifs
  proviennent de `console_top.v` et l'état IN de `sync_fifo/usb_fifo.v`.
  `usb_packet_trace.v` est un observateur UTMI original du projet, utilisé
  par le diagnostic L12 pour mémoriser quatre paquets DATA EP2 utiles
  (paquets non vides ou vides avec une longueur annoncée non nulle).
  Diagnostic r16 : les bits précédemment réservés identifient aussi le
  dernier PID DATA acquitté, observé séparément sur l'entrée UTMI du PHY
  et sur le signal de fin du contrôleur. Les DATA vides participent à cet
  historique des ACK sans effacer les quatre paquets utiles. Cet ajout
  reste passif et n'alimente aucun signal fonctionnel USB.
  Voir `TESTS/TESTS_GPU_L12.md` ; aucune netlist fermée n'est modifiée.
- `sync_fifo/` — sources Sipeed/Gowin ; **modification E2** dans `usb_fifo.v` :
  la validité d'un octet reçu est conditionnée par `i_ep_rx_rdy`, comme la lecture
  FIFO, pour permettre la régulation du débit vers l'UART AE350.
  **Correction de reprise USB IN (29 septembre 2026)** dans `sync_tx_pkt_fifo.v` :
  le pointeur de prélecture `rp_next` est rétabli avec `rp` à la fin d'une
  tentative de paquet. Sans cela, une retransmission à lectures consécutives
  corrompt son deuxième octet. Reproduit par `TESTS/rtl/usb_tx_retry_tb.sv`.
  Dans `usb_fifo.v`, la longueur d'un paquet IN est conservée jusqu'à son
  acquittement (seulement pour un paquet non vide annoncé disponible ;
  aucun paquet réservé lors d'un sondage à vide) : les octets UART arrivés
  entre deux tentatives doivent rester
  dans le paquet suivant. L'autorisation `txcork` et cette longueur sont
  acquises ensemble : le paquet peut s'ouvrir pendant l'attente active de
  données, puis reste stable pendant sa lecture. Un octet tardif ne doit pas
  ouvrir un paquet de longueur nulle. La sélection d'un
  endpoint simultanée au début de transaction reste prise en compte.
  Reproduit par `TESTS/rtl/usb_in_packet_tb.sv`.
  **Candidat L12 r10** : après ACK, masquer la disponibilité le temps que
  le compteur enregistré reflète le nouveau pointeur de paquet. Un sondage
  rapproché ne doit pas réannoncer les octets déjà acquittés. La possibilité
  d'ouverture tardive est conservée ; l'essai de gel à vide r9 a été rejeté
  sur carte. Voir `TESTS_GPU_L12.md` pour les preuves et l'état des essais.
- `ddrtest/ddr3_memory_interface/` — netlist `DDR3_Memory_Interface_Top` (PHY DDR3) —
  `pro_ddr_test/src/ddr3_memory_interface/`.
- `ddrtest/gowin_pll/` — PLL DDR Sipeed (copie).
- `ddrtest/ddr3_test.v`, `fifo.v`, `uart_tx.v` — sources du test Sipeed (copies conformes).
- `video/lcd_timing.v`, `video/gowin_pll_lcd.v` — exemples Sipeed `rgb_screen/800_480_screen`
  (timing 800×480 pour le panneau CJ050QGH50), lcd_timing : **HS/VS ajoutés localement** (E0b).

Règle du projet : ne jamais modifier le contenu chiffré ; les modifications RTL se font dans
les modules du projet (`console_top.v`, machines CDC/DDR3).

## Modification L11 du socle DDR3 (29 septembre 2026)

### Remplacement du pont CPU DDR (3 octobre 2026)

`board/ahb_ddr_cdc.v` est un module original du projet. Il remplace
l'instance du pont Sipeed dans `board/ddr_subsys.v`, sans modifier les
sources fournisseur. Le pont précédent disposait de FIFO de données mais
croisait plusieurs commandes/fins directement entre HCLK 50 MHz et UI
75 MHz, domaines séparés dans le SDC. Deux FIFO du projet transportent
maintenant les commandes complètes et les réponses. Une transaction AHB
reste en vol ; les rafales SEQ sont traitées beat par beat, avec attentes.
La latence CPU change ; le chemin natif du GPU et ses fréquences restent
identiques. Reset commun requis avec abandon des commandes/lectures DDR
aval, comme lors de la calibration actuelle ; ce module ne garantit pas
un reset isolé du CPU laissant des réponses DDR anciennes en vol.
Voir `TESTS/DDR_AHB_CDC_20261003.md` et `tools/check_ahb_ddr_cdc.py`.

`board/ddr_ui_adapt.v` et `board/ddr_arb.v` : l'état « file pleine » de leur
file d'étiquettes est calculé par sélection tardive entre trois comparaisons
des pointeurs courants. Valeur identique à l'expression d'origine sur les
4 096 cas (`TESTS/rtl/ddr_tag_queue_equiv.sv`).

Revue USB/L11 : `board/ddr_arb.v` sélectionne ensuite le maître et les
données indépendamment de `ready`, qui ne conditionne que l'acceptation.
Les priorités, les cycles acceptés, les masques et les étiquettes de lecture
restent identiques sur 4 096 cas (`TESTS/rtl/ddr_arb_equiv.sv`). Cela enlève
le trajet combinatoire DDR ready/reset → sélection d'adresse → rotation
→ tampon CPU de l'arbitre GPU, sans ajouter de cycle.

Revue r9 : `ddr_ui_adapt.v` prépare l'étiquette dans l'emplacement libre
sans attendre `push`. Elle n'est publiée que par l'avance du pointeur ;
aucune écriture à file pleine. Interfaces comparées sur 20 000 cycles
contre r8 (`TESTS/rtl/ddr_ui_equiv.sv`).

## Ajouts E2 — AE350 et diagnostic LED (27 septembre 2026)

- `board/` : socle AE350/DDR3 porté du projet local `logic_analyser_wifi`,
  configuré pour le Pro Dock FPG676, avec DDR3 32 bits. Provenance du pont et
  de ses FIFO détaillée dans `board/sipeed/PROVENANCE.md`.
- `board/riscv_ae350_soc_ext/riscv_ae350_soc.v` : IP AE350 régénérée par Gowin
  1.9.12 avec la configuration `cfg/` et le firmware local d'écho E2.
- `ae350/uart2_to_ep2.v` : pont UART/CDC du projet, corrigé et testé en E2.
- `../ref_demo/` : démonstrateur `ae350_customized_demo` de Sipeed Pro Dock,
  adapté pour le test LED à 800 MHz et bus 80 MHz ; IP AE350 régénérée avec
  `../ref_demo_cfg/` et `fw_console/demo/demo_led.S`.
- Les configurations et wrappers de PLL sont adaptés localement ; le contenu
  chiffré des IP est produit par les outils du fournisseur.

## L12 — moteur affine (30 septembre 2026)

`video/blitter.v` et `video/gpu_accel.v` : extension locale originale de
l'architecture G2/L11 pour les opcodes 12/13 (rotation, échelle X/Y,
cisaillement, transparence). Cache source BSRAM de 16 Kio ; DDR3 conservée.
Voir `video/PROVENANCE.md` et `ARCHI/GPU_L12_AFFINE.md` pour le contrat.

Validation L12 : ajout dans `usb/sync_fifo/usb_fifo.v` (chemin relatif au
dossier `rtl`) d'une qualification du POP des FIFO IN par la présence d'un
payload annoncé (`!CORK && longueur != 0`). Un octet déjà arrivé en RAM
mais pas encore propagé dans la longueur enregistrée ne doit pas être
consommé par le POP d'un sondage à vide. Le banc `usb_in_packet_tb.sv`
reproduit la perte avant correction et la conservation après correction ;
le banc concurrent conserve ses 30 000 octets et 3 685 reprises.

`video/blitter.v`, L12 r4 : préparation anticipée des limites COPY pour
réduire le chemin de masque après l'échec de timing de r3 (−0,111 ns).
Les interfaces, les cycles et les pixels historiques sont conservés par
la comparaison au blitter L11 gelé.

L12 r5 : indicateurs de lecture active/dernier demi-mot préparés dans
`video/gpu_blit_dma.v`, sans décalage des interfaces. Voir la comparaison
DMA au cycle près contre L11 et la référence de pixels indépendante.

L12 r6 : le DMA prépare `write_follow_addr` pendant l'assemblage d'une
rafale ou la préparation de son masque. Le signal READY ne traverse plus
les choix fin de remplissage/fin de ligne avant de valider cette adresse.
Même les valeurs d'adresse entre transactions restent identiques dans le
banc d'équivalence DMA (1 269 391 cycles contre L11).

L12 diagnostic r14 : `usb/usb_reset_release.v` est un module original de
qualification du verrouillage et de libération synchrone des resets.
`console_top.v` l'utilise pour séquencer la PLL B après sa référence 48 MHz,
puis le PHY et le contrôleur USB. Une perte de LOCK réaffirme les resets
sans attendre un front d'horloge. Les ports publics des IP sont utilisés ;
leurs netlists et les fréquences restent inchangées. Candidat motivé par
les échecs d'énumération et d'écho après rechargement du même r13, encore
à valider sur carte ; détails dans `TESTS/TESTS_GPU_L12.md`.

Diagnostic L12 r20 : `tools/build_gpu.py --usb-controller gowin-high`
ou `gowin-full` régénère une variante séparée du **contrôleur** depuis
`IDE/ipcore/USB_DEVICE_CONTROLLER/data` de Gowin 1.9.12. Le compilateur
officiel produit la netlist dans le dossier du build ; aucune netlist
existante n'est éditée ou écrasée. Le manifeste fige les sources fournisseur
inchangées, la configuration et la netlist résultante. Le PHY reste celui
de Sipeed. La configuration reprend UTMI, EP0 64 octets, SELFPOWERED et
les types d'endpoints de la référence ; les deux variantes ne diffèrent
que par HSSUPPORT/FSSUPPORT. Il s'agit d'un essai comparatif, pas d'une
correction validée. Le mode par défaut `reference` conserve l'IP historique.
`console_gpu_usb_fs.v` active les descripteurs Full Speed existants pour
la variante 12 Mbit/s. CPU, bus, GPU et LCD gardent leurs fréquences.


2 octobre, diagnostic L12 r25 : reset applicatif commun dans `console_top.v`
pour les FIFO, UART, configuration CDC et compteurs/trace. Le SET de la
sortie usbrst_o du contrôleur fournisseur est synchrone (DFFSE) ; la FIFO
ne suivait pas le reset système pendant l'arrêt de phy_clk. Le banc avec
le contrôleur `.vo` intact reproduit l'échec ancien et valide le reset commun.
Cette correction n'a pas supprimé les pertes USB du r25 sur carte.

Diagnostic r26 : extension originale de `usb/usb_packet_trace.v` avec ACK
et validation associés au paquet enregistré, RXERROR et état FIFO après
validation. Le compte UTMI occupe 10 bits, six bits servent au marqueur et
aux états du paquet. Aucun signal de transport n'est commandé par la trace.
Voir `TESTS/TESTS_GPU_L12.md` et le banc `usb_packet_trace_tb.sv`.

Diagnostic r27 (2 octobre) : garde de sélection dans `usb/sync_fifo/usb_fifo.v`.
Les sorties CORK/longueur restent fermées jusqu'à ce que l'endpoint courant
corresponde à celui des registres de publication ; POP et réservation du
paquet utilisent la même garde. Cela empêche l'offre EP0 (ouverte, longueur
nulle) de devenir un ZLP EP2 lors du changement d'endpoint. Après ACK perdu,
ce ZLP pouvait être remplacé par une donnée portant le même DATA PID, donc
éliminée comme doublon côté hôte. Reproduit avec le contrôleur et le PHY
fournisseur intacts, corrigé dans les sources ouvertes uniquement.
Comparaison bornée : les trois bancs historiques FIFO/paquets/flux conservent
leurs journaux au cycle près ; les nouvelles assertions de transition
échouent avant et passent après correction. L'équivalence globale n'est
pas revendiquée : le comportement durant la transition est précisément
celui corrigé. Validation matérielle à suivre dans `TESTS/TESTS_GPU_L12.md`.

Diagnostic r30 : `usb/usb_packet_trace.v` conserve les trois tentatives DATA
précédant le dernier paquet utile, y compris les ZLP et leurs ACK/FIN.
Un historique courant de 192 bits alimente l'instantané de 256 bits déjà
accessible ; les sondages à vide ultérieurs ne peuvent pas effacer cet
instantané. Observation passive, sans sortie vers le transport.
Le banc vérifie le contexte avant correction (FAIL) et après (PASS),
ainsi que la conservation après douze paquets vides et les ACK manquants.

Diagnostic r31 : les quatre bits inutilisés du mot de statut exposent,
après deux registres de synchronisation à 60 MHz, PLL AE350 verrouillée,
DDR_STOP, DDR_LOCK et reset CPU libéré (bits 31 à 28). Lecture vivante même
sur EP0 ; aucun de ces bits ne commande la logique. Ce relevé permet de
distinguer une absence de réponse UART d'une perte USB après émission.
Le format des compteurs et des enregistrements de paquets reste inchangé.

Diagnostic r32 : après refus du timing r31, réduction de l'historique à
une tentative DATA précédente plus le dernier DATA utile. Les deux mots
hauts de l'interface existante sont nuls. Le contexte ZLP/ACK/FIN immédiat
et la rétention pendant les sondages vides sont conservés, avec 256 bits
d'état historique en moins que r30/r31. La fenêtre de diagnostic devient
explicitement plus courte ; ce n'est pas une équivalence des quatre mots.
Transport et firmware inchangés ; tests ciblés consignés dans la fiche L12.

`console_usb_diag.v` sélectionne la branche mire préexistante de
`console_top.v` pour une comparaison USB avec CPU/DDR conservés. Le build
`--usb-diagnostic` fige cette variante et ses contraintes : mêmes broches
et SDC, placements de cellules retirés dans sa copie seulement. Cette
variante est un outil de diagnostic temporaire, pas une livraison graphique.

Isolation r3 : rétablissement de l'enregistreur à quatre mots du r30.
La réduction à deux mots du r32 n'est pas retenue ; la variante sans GPU
permet de charger la trace étendue avec timing positif. Les sources actuelles
conservent les quatre états carte du r31. Ces ajouts diagnostiques ne sont
pas validés dans un nouveau bitstream GPU complet ; le r29 reste la référence
matérielle graphique de cette investigation, avec son défaut USB connu.


Diagnostic PHY3.4 (2 octobre 2026) : le script de build peut régénérer
l'IP depuis les fichiers officiels Gowin1.9.12 copiés sans modification,
avec les macros UTMI/GW5AT/TX_DELAY_0_BIT d'origine. Source de référence et
SDC conservés. Les entrées de génération et la netlist produite sont figées
par build ; mode réservé au diagnostic sans GPU. Le premier essai matériel
r2 reste défaillant et ne constitue pas une mise à jour de production.


Diagnostic première tentative : `usb_packet_trace.v` ajoute le paramètre
CAPTURE_FIRST (défaut0, équivalence cycle par cycle vérifiée) et l'entrée
passive new_packet. Le wrapper `console_usb_first.v` sélectionne le mode1
uniquement dans les variantes de diagnostic sans GPU. La garde top reprend
exactement la première admission POP EP2 et la priorité FIN de la FIFO.
Aucun signal de transport ne dépend de la trace. `gpu_usb_first.cst` ne
s'applique qu'à cette variante : placement du OU de reset après refus timing
r1, emplacement corrigé après refus r2 ; r3 passe à+0,189ns. Le doublon USB
persiste, désormais observable dès la première tentative.

Diagnostic RX Advance (2 octobre 2026) : `tools/build_gpu.py` expose
`--usb-phy-rx-mode advance`, uniquement avec régénération Gowin du PHY et
variante de diagnostic sans GPU. Ce choix ajoute `V_120` au fichier de
configuration de génération ; les trois fichiers fournisseur sont copiés
intacts. Le mode Normal par défaut conserve exactement les macros précédentes.
Le guide officiel IPUG781-1.7E, page16, documente RX_Mode Normal à60MHz et
Advance à120MHz pour Arora V, avec contraintes timing plus strictes. TX_DELAY,
PLL, brochage et SDC de production ne changent pas. La configuration et les
sources sont figées dans chaque build ; ce mode reste expérimental tant que
les tests matériels de la fiche L12 ne le qualifient pas.

Diagnostic PHY 3.5 : `--usb-phy-ide` sélectionne l'installation fournisseur
utilisée pour ses fichiers intacts et sa synthèse d'IP. Les outils AE350 et
console restent inchangés. Le manifeste fige aussi l'ipspec et le JSON
consigne version, installation et RX_Mode. L'adaptation Qt/FreeType requise
par l'installation 1.9.12.03 est limitée à l'environnement du sous-processus ;
elle ne modifie ni outil installé ni source/netlist. Les macros de configuration
3.5 doivent être confrontées au générateur officiel avant validation matérielle.

Correctif EP0 (2 octobre 2026) : `console_top.v` présente désormais
`rxrdy=1` au contrôleur lorsque l'endpoint sélectionné est zéro ; les autres
endpoints conservent le signal de la FIFO. Le contrôleur régénéré 3.2
renvoyait NAK au ZLP OUT de statut après GET_DESCRIPTOR malgré des données
correctes. Le banc A/B prouve NAK avec zéro et ACK avec un pour les longueurs
8/18/64 ; neuf lectures complètes passent après correction. Sur l'ancien
contrôleur Sipeed, les 17 événements de réponse du scénario 18 octets ont
des timestamps et contenus identiques avec zéro et un. Cette comparaison
est limitée au scénario et ne constitue pas une équivalence globale.
Le témoin FS dédié r2 avec cette seule ligne modifiée passe ensuite
l'énumération et son premier essai matériel ; validation console HS distincte.


PHY Full Speed dédié (2 octobre 2026) : `usb/fs_phy/usb_softphy.v`, son IPC
et son modèle d'instanciation proviennent sans modification de
`TangMega-138KPro-example`, commit `d3cebf1703f1bcd06dca8a53bf2b660c86a5ec16`,
`usb2_soft/usb_uart_loopback/src/usb_softphy/`. SHA de la netlist :
`b7bfe336d7ce1a5d4f275ec5ab6cf12df28a565995fc430d85ddd8bf54f0c660`.
IP `usb_11_softphy` 1.0, horloge 60 MHz, broches T19/U19, pullup M19.
Les mentions fournisseur sont conservées ; aucun corps de netlist n'est édité.

La branche `CONSOLE_USB_FS_PHY` de `console_top.v` reprend les raccordements
du témoin FS r2 testé trois fois sur carte. Le contrôleur doit être généré
avec FSSUPPORT et le descripteur annonce HSSUPPORT=0. Le build sélectionne
l'ensemble via `--usb-controller gowin-full --usb-phy sipeed-full` ; toutes
les sources et contraintes dérivées sont figées. Les quatre ports HS et
les horloges sclk/960 MHz absentes sont retirés de cette seule variante,
avec conservation des contraintes des autres domaines. Le prétraitement
prouve la branche HS inchangée après cet ajout. Les tests du témoin seul
ne valent pas validation de l'intégration CPU/GPU, en cours.


Sélection du contrôleur fournisseur (2 octobre 2026) : les options
`--usb-controller-ide` et `--usb-controller-system-freetype` permettent de
régénérer l'IP avec une autre installation officielle, selon les mêmes
précautions que pour le PHY. L'ipspec/version est figé avec les entrées et
le JSON du build. Le défaut reste 1.9.12 / contrôleur 3.2 ; une expérience
3.3 utilise 1.9.12.03 avec contrôleur HS et PHY 3.5 Advance. La note officielle
RN100-1.9.12.03E annonce des signaux finish/debug et une optimisation du
timing externe pour le contrôleur 3.3 ; elle ne promet pas de corriger le
symptôme de cette carte. Aucun fichier fermé n'est édité.

Reprise des réponses de classe EP0 (2 octobre 2026) : modification ciblée de
la source ouverte Sipeed/Gowin `usb/uart/usb_uart_config.v`. Le module reçoit
désormais `usb_txpktfin` ; un bit `endpt0_pending` conserve la réponse jusqu'à
l'acquittement accepté. TXVAL retombe toujours au dernier POP pour terminer
une tentative, puis l'index, l'octet initial et l'offre sont réarmés lorsque
TXACT devient inactif sans acquittement. L'instantané diagnostic n'est pas
recapturé sur retry. Un nouveau SETUP et le reset abandonnent la réponse.
`console_top.v` raccorde FIN ; les quatre tops historiques sont adaptés au
même port, sans changer leurs horloges ou leur PHY.

Preuve avant/après dans `TESTS/USB_HS_RECOVERY_REVIEW_20261002.md` et
`TESTS/usb_hs_ep0_*_20261002.json` : le contrôleur HS Sipeed intact renvoyait
un DATA1 ZLP après ACK perdu, pour CDC7 comme pour diagnostic32. Après fix,
les réponses sont retransmises avec PID/contenu/CRC/status exacts. Le journal
de la séquence normale avant/après est strictement identique, timestamps
compris ; cette équivalence reste limitée à la séquence testée. Le banc
applicatif couvre reprises partielles/répétées, snapshot gelé, FIN d'un autre
endpoint, préemption et reset avec horloge arrêtée. Il ne prouve pas la
correction du défaut bulk physique ni le timing d'un nouveau bitstream.

Confirmation HS3.3 avec l'export officiel intact dans
`tang/impl/gpu_usb_controller33_hs_model_r1` : deux FAIL attendus avant fix
(CDC7/diagnostic32), quatre PASS après fix (deux reprises et deux préemptions),
six rapports avec sources inchangées. Les séquences normales avant/après ont
des timestamps et paquets identiques. Résumé :
`TESTS/usb_hs33_ep0_summary_20261002.json` ; archive de reproduction :
`TESTS/usb_hs33_ep0_recovery_20261002.tar.gz`. Le modèle `.vo` a pour SHA
`aa94743bb6922840761dfb2d6ba84f9c522f5b8b220f5feda95ca61a173dbaae`.
Le wrapper d'export inclut la ROM réelle pour réduire les I/O et lie les
entrées BOS à zéro ; aucune requête BOS n'appartient aux tests. Les entrées
de génération du contrôleur du build console corrigé sont identiques à
celles du VG exporté, sans revendiquer une équivalence de routage.


Qualification PLL USB (2 octobre 2026) : le top attend désormais 104000 cycles
de la référence carte 50 MHz pour chaque LOCK, conformément à la fenêtre
minimale de 2 ms indiquée dans [UG306-1.0.9E, tableau 5-2](https://cdn.gowinsemi.com.cn/UG306E.pdf#page=49).
La libération finale reste dans phy_clk60 ; le PHY reçoit `~rst_usb` comme
LOCK qualifié et `PHY_RESET|rst_usb` pour affirmer son reset même sans horloge.
Seul le câblage public change ; aucun module propriétaire n’est édité.
Tests numériques et limites : `TESTS/USB_PLL_LOCK_WINDOW_20261002.md`.

## Trace USB IN/NAK — 2026-10-03

`usb/usb_idle_trace.v` : observateur original, indépendant de l'IP fermée,
UTMI échantillonné sur un registre commun28bits puis analyse tokens et
réponses. Deux FIFO `board/ddr_dcfifo.v` portent commandes AHB et snapshots
entre80 et60MHz ; fenêtre E9002000 pour J-Link. Aucun contrôle du protocole
USB. Simulation à quatre rapports/phases, interruptions d'horloge et
reset : `TESTS/usb_idle_trace_r3_20261003/result.json`. Contrat/limites et
validation matérielle dans `TESTS/USB_IDLE_TRACE_20261003.md`.

## L13/L14/L15 — 2026-10-03

`video/gpu_raster.v` et `video/gpu_rgb_reader.v` sont des créations propres
à cette console : alpha RGB565, triangles texturés affines, Z16 et affichage
direct. Intégration dans `blitter.v`, `gpu_accel.v` et `gpu_scanout.v`, avec
les domaines d'horloge et les contraintes existants. La génération AE350
incorpore le firmware de démonstration et de comparaison couleur/profondeur.
Les IP USB/DDR restent inchangées. Le détail des adaptations et du défaut
de synthèse corrigé est dans `video/PROVENANCE.md` ; validation matérielle
`gpu_l1315_r3` dans `TESTS/TESTS_GPU_L13_L15.md`.

## Perspective et composition RGB565 / indexée — 2026-10-03

`video/gpu_perspective.v` est un diviseur original pour les plans rationnels
UQ/Q et VQ/Q. Le moteur de fragments conserve alpha et Z16. Le compositeur
ajoute une couverture par pixel pour les couches indexées sur fond RGB565 ;
son lecteur DDR peut anticiper les lectures du fond. Les registres de
diagnostic mesurent l'image composée et le temps total par ligne.
Les adaptations détaillées figurent dans `video/PROVENANCE.md`, les preuves
et le statut physique dans `TESTS/TESTS_GPU_PERSPECTIVE.md`. Les IP fermées,
les domaines d'horloge et les contraintes de timing restent inchangés.

R10 : `board/ddr_gpu_arb.v` prépare la comparaison « un emplacement libre »
à partir des pointeurs stables, puis applique push/pop au drapeau plein.
Un push et un pop simultanés conservent l'occupation. Deux bancs comparent
toutes les sorties, les pointeurs et le plein à la référence ouverte :
77 670 748 cycles de composition et 2 490 566 cycles de dessin identiques.
Le CST rapproche une bascule de commande USB de sa logique, sur la base
du rapport officiel r9 ; la logique fermée n'est pas modifiée.

### GPU V1 — 4 octobre 2026, R31 validé

Sources originales du projet : `gpu_v1.v` (cibles, scissor, plans, matériau,
RGB565/ARGB4444, alpha/additif, Gouraud, brouillard), `gpu_texture_cache.v`
(cache lecture DDR de 2 Kio), `gpu_copy565.v` (copie rectangulaire avec recouvrement).
Le générateur de spans et les diviseurs perspective existants sont réutilisés.
`gpu_accel.v` et `blitter.v` routent les nouveaux opcodes 22–30 ; les opcodes
1–21 conservent leurs moteurs. `gpu_scanout.v`/`gpu_rgb_reader.v` ajoutent
l'agrandissement ×2 et le pas RGB565, engagés au vblank. Aucune netlist
fournisseur ni contrainte d'horloge n'est modifiée.
Le tampon CPU de `board/ddr_gpu_arb.v` capture sa charge utile lorsqu'il est
vide, avant de figer une requête acceptée. `board/ahb_exts_bridge.v` sépare
capture privée et acceptation, produit HREADY sans enable tardif et conserve
les cycles visibles. Les comparaisons d'équivalence et les placements CST
des registres de contrôle sont décrits dans `video/PROVENANCE.md`.

R31 passe simulations, timing, deux rechargements USB HS, suite graphique
complète et 30 minutes d'endurance (58 680 images). Les trois scènes sont
confirmées visuellement. Image et sources archivées ; preuves et limites
de charge dans `TESTS/TESTS_GPU_V1.md` et `ARCHI/GPU_V1.md`.

### Carte SD et disque USB — 5 octobre 2026, en cours de validation

Carte SD : aucune logique nouvelle. `board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v`
active le contrôleur SPI optionnel de l'IP AE350 (`AE350_APB_SPI_EN`) et retire
`AE350_GPIO_IOPORT_EN` (GPIO en ports séparés) ; l'IP est régénérée par le
build, sa netlist n'est pas éditée. `board/ae350_soc.v` et `console_top.v`
relient SPI et deux GPIO aux broches microSD du dock (`constr/gpu.cst`).
Le système de fichiers `fw_console/fatfs/` est FatFs R0.11a (ChaN), copié du
SDK AE350 (`ff.c`, `ff.h`, `diskio.h`, `integer.h`) ; `integer.h` y définit
LONG/DWORD sur 32 bits pour la compilation sur PC 64 bits, `ffconf.h` et
`diskio.c` sont propres au projet.

Disque USB : sources ouvertes Gowin/Sipeed modifiées, netlists du contrôleur
et du PHY inchangées.
- `usb/sync_fifo/usb_fifo.v` : EP1 IN et OUT activés ; mode `EP1_IN_PACKET`
  (longueur proposée = min(validé − acquitté, taille de paquet), purge EP1).
  Les chemins EP2/EP3 ne sont pas réécrits : les cinq bancs USB existants
  donnent des journaux identiques à ceux des sources précédentes.
- `usb/usb_descriptor.v` : paramètre `MSC` (composite CDC + stockage de masse) ;
  `MSC = 0` conserve les octets d'origine.
- `usb/uart/usb_uart_config.v` : paramètre `MSC` (Get Max LUN, signalement du
  Bulk-Only Reset) ; sans lui l'automate EP0 est inchangé.
- Sources originales du projet : `usb/usb_msc_port.v` (port AHB du firmware,
  FIFO double horloge `ddr_dcfifo`, passage de main) et `usb/usb_msc_empty.v`
  (lecteur sans carte servi par le matériel).
Contrat dans `ARCHI/SD_USB_DISQUE.md`, preuves et limites dans
`TESTS/TESTS_SD_USB.md`.

### Reprise vidéo / SD / USB — 7 octobre 2026

C22 est qualifié sur carte le 8 octobre : trois rechargements HS, échos et
EP0, SD en lecture, douze reprises BOT et disque DDR en écriture/lecture.
Archive `bitstreams/console_gpu_sdusb_800.fs`, preuves et limites dans la
fiche de reprise. Les netlists fournisseur n'ont pas été modifiées.

Les corrections des sources ouvertes sont détaillées et suivies dans
`TESTS/TESTS_REPRISE_20261007.md`. `usb/usb_msc_port.v` acquitte la purge
aller-retour entre AHB et USB avant de libérer le port, y compris si
l'horloge USB s'arrête. Son indicateur d'indisponibilité est enregistré ;
la charge utile TX, sa validation et le compteur de données engagées sont
retardés ensemble d'un cycle USB. Les FIFO restent à deux horloges.
Les essais couvrent resets, horloges décalées/arrêtées, ACK perdus et
débordement du compteur 16 bits. L'audit SDF contrôle séparément les
84 liaisons Gray et les cinq liaisons d'acquittement de purge.

`console_top.v` factorise la sélection AHB du GPU : son attente locale est
déjà traitée dans `gpu_accel`, sans reboucler par le multiplexeur global.
Les attentes des autres esclaves restent prises en compte, avec priorité
au sous-espace USB. Preuves : 512 combinaisons de sélection et comparaison
intégrée au cycle près avec plus de 1,2 million de cycles d'attente.
Les modifications vidéo sont décrites dans `video/PROVENANCE.md`.

Les changements CST retirent des placements hérités devenus pénalisants
et rapprochent les décodages ITCM et le multiplexeur HREADY de leurs
destinations, d'après les chemins routés. Les fréquences et le SDC sont
conservés. Les IP fermées ne sont pas éditées : AE350, contrôleur et PHY
USB sont générés par les outils officiels. Les simulations réussies ne
valident pas à elles seules un nouveau bitstream sur carte ; consulter
la fiche de reprise pour le dernier état de qualification.
