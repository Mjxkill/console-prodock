# L12 — validation du moteur affine

Travail du 30 septembre 2026. Base de comparaison : commit `f383ac5`,
instantané matériel L11 `tang/impl/gpu_l11_usb_r13/source`.

**Statut : simulations, référence hôte et diagnostic graphique complet r13
passés ; fiabilité USB au redémarrage encore en cours de correction.** Le bitstream L11 archivé
reste le point de retour. Aucun bitstream L12 n'est publié comme validé.

## Simulation

```sh
python3 TESTS/test_gpu_accel.py --affine --out /tmp/console_l12_affine_r2
python3 TESTS/test_gpu_accel.py \
  --equiv-blitter-root tang/impl/gpu_l11_usb_r13/source \
  --equiv-dma-delay 0 --out /tmp/console_l12_equiv_r1
```

- 604 commandes : pages entières et gardes exactes, lectures/écritures
  DDR avec attentes et trafic CPU/LCD simultané.
- Rotation des axes, retournements, pas fractionnaires, cisaillements,
  clipping, coordonnées extrêmes, transparence zéro et hors source.
- Régions source de tailles paires/impaires, origine paire/impaire,
  bords de page, source 1×1 et 128×128.
- Copies avec chevauchement sur la même page, réutilisation d'une matrice,
  absence de matrice après reset et configurations/descripteurs refusés.
- Les 541 commandes historiques conservent les interfaces du blitter
  pendant 1 269 390 cycles et 94 260 mots. Le DMA conserve ses interfaces
  pendant 1 269 391 cycles, sans nouveau décalage d'acquittement.

## Hôte et firmware

`tools/render_gpu_affine.py` compile les préparateurs C réels avec UBSan,
parcourt les 256 angles, puis échantillonne les commandes avec des produits
entiers Python indépendants. Les quatre images sont dans `TESTS/images/`.

Firmware : 57 696 octets incorporés dans l'ITCM de 65 536 octets,
BSS 28 992 octets, confirmés sur r13.

## Validation physique à compléter

Le build doit satisfaire le timing sans modification des fréquences,
des contraintes SDC ou des IP fermées. Après identification de la Pro Dock
série `2023112818`, chargement SRAM, diagnostics G0–G6/FAST/L11/L12,
endurance USB, comparaison hôte des poses et confirmation visuelle.

L'archivage du `.fs`, de son SHA-256, des ressources, du timing et des journaux
sera effectué uniquement pour le build retenu après ces contrôles.

## Premier build et défaut USB observé

- `gpu_l12_r1` : arrêté par l'accès réseau restreint au mécanisme de licence
  Gowin ; aucun résultat FPGA à valider.
- `gpu_l12_r2` : timing conforme, 110 chemins détaillés, minimum +0,138 ns,
  24 lignes TNS nulles. Console complète : 30 969 unités logiques,
  22 163 registres, 225 BSRAM, 25 DSP, 8/8 PRIMARY.
- Deux chargements de r2 exposent un défaut USB (délai à 4096 octets, puis
  suppression de 5 octets sur 64). Cette version n'est pas retenue.
- Le bitstream L11 archivé rechargé sur la même carte passe 100 séries
  supplémentaires, 544 100 octets exacts.
- Un sondage vide consommant un octet non encore annoncé est reproduit
  et corrigé en simulation ; voir [le dossier USB](TESTS_USB_REPRISE.md).
  `gpu_l12_r3` intègre cette correction.

- `gpu_l12_r3` : correction USB compilée, mais timing rejeté à −0,111 ns
  sur la parité de copie → activation des banques de ligne ; non chargé.
- `gpu_l12_r4` : préparation des deux limites de copie avant lecture DDR ;
  les deux simulations repassent avec les mêmes journaux, cycles et pixels.
  Le timing est ensuite contrôlé ci-dessous.

- `gpu_l12_r4` : le chemin de copie est corrigé, mais la fin de lecture
  DMA → blitter échoue à −0,167 ns ; non chargé.
- `gpu_l12_r5` prépare les indicateurs S en parallèle des changements
  d'état, sans ajouter de cycle de lecture.

- `gpu_l12_r5` : indicateurs S équivalents, mais arbitrage vidéo → adresse
  DMA échoue au timing à −0,855 ns ; non chargé.
- `gpu_l12_r6` prépare l'adresse suivante avant l'acceptation DDR. Les
  simulations conservent exactement les cycles, adresses et pixels ;
  timing conforme : 110 chemins détaillés, minimum +0,140 ns, TNS nul.

## Essais r6 et diagnostic indépendant

`gpu_l12_r6` : 30 650 unités logiques, 22 192 registres, 225 BSRAM,
25 DSP, 8/8 PRIMARY ; firmware 57 696 octets, BSS 28 992 octets.
SHA-256 : `103a7870a875d92f83ac27372c817a5807dbc448dec2f50f8942f73723f8f72b`.

- Test USB : la réponse `THREED PAUSED` arrive, puis l'identification
  attendue manque. Des commandes séparées ne rétablissent pas la liaison.
- Un reset USB seul ne rétablit pas les réponses. Après un rechargement
  SRAM, la première identification est complète, mais les suivantes manquent.
- En envoyant `I` comme toute première commande après un autre chargement,
  les poses 0, 1 et 2 passent leur comparaison intégrale CPU et leur hash LCD :
  `3369f9e2`, `9bbe3479`, `18407cb2`. Coûts de dessin : 6 096 625,
  6 216 867 et 6 216 050 cycles CPU, soit 7,62–7,78 ms.
- La pose 3 et `AFFINE READY` ne sont pas reçues. Ce résultat partiel ne
  valide ni les quatre poses ni l'animation. Les commandes ultérieures ne
  produisent aucune réponse ; la cause exacte reste à mesurer.
- Le contrôle USB `GET_LINE_CODING` répond encore `00c20100000008` lorsque
  le CDC ne renvoie plus de texte. Le changement d'endpoint seul ne suffit
  pas à rétablir la console.
- Confirmation visuelle de l'utilisateur : les six anneaux sont affichés,
  dont deux animés. La commande `Z` atteint donc le CPU et l'animation
  continue malgré le silence du CDC. Le trajet de retour CPU → PC reste
  à isoler ; les quatre poses et l'endurance ne sont toujours pas validées.

Journaux : [échec USB r6](gpu_l12_r6_usb_failure.txt),
[poses r6 partielles](gpu_l12_r6_affine_partial.txt).

Instrumentation temporaire `CONSOLE_USB_DIAG` : compteurs passifs des octets
USB OUT, des octets livrés au pont UART et des octets émis par le CPU ; POP,
ACK, état/longueur du paquet IN et erreurs PHY. Leur instantané de 32 octets
est lu par une requête de contrôle privée (`bmRequestType=0xa0`, requête
`0x21`, valeur `0xd1a6`, longueur 32), sans détachement de `cdc_acm`.
Le script `tools/usb_control_probe.py` identifie uniquement la console série
`11252024`. Une requête de contrôle change l'endpoint sélectionné : tenir
compte de cet effet d'observation lors du diagnostic.

Le banc `usb_control_diag_tb.sv` vérifie les sept octets CDC ordinaires,
l'instantané diagnostic de 32 octets et le retour au protocole ordinaire.
Les netlists USB fournisseur restent intactes.

- `gpu_l12_diag_r7` : rejeté au timing, −0,162 ns sur le multiplexage de
  données du lecteur vidéo et −0,989 ns sur le reset interne PHY ; **non chargé**.
- `gpu_l12_diag_r8` : placement du reset PHY repris de r6 et décodeur du
  multiplexeur vidéo rapproché de ses données ; **timing conforme**, 110
  chemins, minimum +0,140 ns. SHA-256 :
  `28451793adb364ac63f9697c149908803221e1ffa533c414f3785400af094d0a`.
  Chargé uniquement pour diagnostic ; le défaut USB persiste.

### Résultat des compteurs et de la capture hôte r8

Les commandes arrivent toutes au pont UART. Pour deux demandes `?`, le
compteur CPU progresse de 57 à 114 octets : les réponses sont bien émises.
Le retour USB en perd une partie ou laisse des octets en attente ; le
compteur d'erreurs RX PHY reste nul pendant cette séquence. Cela ne suffit
pas à exclure un problème d'émission physique.

La capture USBmon, filtrée sur la seule console, contient **304 complétions
bulk IN en erreur `-71` (`EPROTO`)** et 18 complétions réussies. Linux
réessaie ses lectures avec des délais après ces erreurs. Une deuxième
identification de 57 octets est retirée de la FIFO et acquittée côté FPGA,
sans être délivrée au programme hôte. Ce constat seul ne permet pas de
distinguer un paquet rejeté comme doublon des autres erreurs du contrôleur.

Comparaison : le bitstream L11 archivé est rechargé, puis les mêmes commandes
`?`, `?`, `X`, `?` sont espacées de trois secondes. Les quatre réponses sont
exactes ; **122 complétions bulk IN réussies et aucune erreur** dans cette
capture, y compris les périodes sans données.

Journaux : [compteurs r8](usb_l12_control_probe.txt),
[séquence r8](usb_l12_control_trace.txt), [USBmon r8](usb_l12_host_trace.txt),
[séquence L11](usb_l12_l11_idle_comparison.txt),
[USBmon L11](usb_l12_l11_idle_trace.txt).

### Candidat r9 : ne pas ouvrir tardivement un sondage vide

Hypothèse à vérifier sur carte : le contrôleur a déjà échantillonné CORK
pour un sondage vide lorsque la logique r13/r8 ouvre ce paquet avec un
octet UART tardif. Le test ajouté fige la décision du consommateur et
injecte un POP tardif ; r8 change la longueur de ce sondage.

r9 garde longueur et CORK fixes pendant `txact`, même pour un sondage vide.
Les données tardives deviennent disponibles au sondage suivant. La sélection
simultanée d'endpoint reste prise en compte. Les deux protections contre
la mémorisation et la consommation d'un paquet zéro restent actives : elles
manquaient lors de l'ancien essai L11 r11, donc ce candidat est distinct.

- [Scénario avant correction](usb_empty_transaction_before.txt).
- [Paquets corrigés](usb_empty_transaction_simulation.txt) : données tardives,
  sondage vide, reprises, limite 64, sélection et reset.
- [Flux concurrent](usb_empty_stream_simulation.txt) : 30 000 octets,
  14 733 paquets et 3 685 reprises, identiques au résultat antérieur.
- `gpu_l12_diag_r9` : timing conforme, +0,140 ns ; chargé, mais rejeté
  sur carte : première identification exacte, puis la deuxième écriture
  hôte reste en attente et expire. Les compteurs confirment qu'un seul
  octet de commande est arrivé au CPU. Le gel à vide n'est donc pas retenu.
  [Échec](usb_l12_r9_idle_failure.txt), [compteurs](usb_l12_r9_failure_counters.txt).

### Candidat r10 : compteur périmé immédiatement après ACK

Un scénario indépendant montre que le pointeur de paquet est acquitté
immédiatement, tandis que le nombre d'octets disponibles traverse encore
`wrnum`, puis `wrnum_d0`, puis le registre de longueur. Un nouveau sondage
peut donc annoncer à nouveau un octet déjà retiré de la FIFO.

r10 masque la disponibilité pendant la propagation de cet acquittement,
puis publie le compteur mis à jour. L'ouverture avec données tardives est
rétablie : l'essai r9 l'a montrée nécessaire sur cette carte. Le test vérifie
aussi un paquet suivant déjà en attente, qui ne doit pas inclure les octets
acquittés dans sa longueur.

- [Avant correction](usb_retire_before.txt) : longueur périmée de 1 octet.
- [Paquets corrigés](usb_retire_simulation.txt) : sondages rapprochés,
  file vide et paquet déjà en attente, plus les scénarios de reprise.
- [Flux concurrent](usb_retire_stream_simulation.txt) : 30 000 octets
  exacts, 14 733 paquets, 3 685 reprises, résultat historique conservé.
- `gpu_l12_diag_r10` : arrêté avant placement, car Gowin renomme le
  décodeur `n777_s3` en `n777_s5`. Aucun bitstream n'est chargé.
- Le résolveur de contraintes accepte maintenant `via=I2` : il retrouve
  le sélecteur du multiplexeur depuis la bascule stable
  `source_write_data_205_s0`. Vérifié sur les netlists r8 et r10.
- `gpu_l12_diag_r11` : même correction USB, contrainte résolue
  automatiquement ; **timing conforme**, 110 chemins, minimum +0,140 ns.
  SHA-256 : `b727af234a2679b40a762ff9c6e7948b54e0245eea6b9b8b713d8793ae088fbd`.
  Après chargement, seule la première des quatre commandes reçoit sa
  réponse. Les compteurs donnent 4 octets USB OUT, 4 livrés à l'UART,
  187 émis par le CPU, 188 POP, 26 ACK et une FIFO vide. La correction
  de compteur est donc insuffisante pour rétablir la communication.
  [Séquence r11](usb_l12_r11_idle_failure.txt),
  [capture r11](usb_l12_r11_idle_trace.txt).

### Trace des paquets émis — r12

`usb_packet_trace.v` observe passivement l'interface UTMI vers le PHY.
Il conserve les quatre derniers paquets émis pour EP2 : premier octet
(PID), nombre d'octets acceptés par `TXREADY`, deux derniers octets,
endpoint, CORK, `txact` et longueur annoncée au début du paquet.
Il n'insère aucun registre dans le trajet de transmission.

La valeur privée `0xd1a7` renvoie cet historique ; `0xd1a6` conserve les
compteurs. Chaque réponse fait 32 octets, pris en instantané au début du
SETUP. Les paquets des autres endpoints ne remplacent pas l'historique EP2.

Les bancs vérifient les attentes `TXREADY`, le comptage, les paquets de
longueur nulle, NAK, le filtrage d'endpoint, les deux pages de diagnostic et
la conservation des réponses CDC ordinaires :
[trace](usb_packet_trace_simulation.txt), [contrôle](usb_control_diag_simulation.txt).

`gpu_l12_diag_r12` passe le timing : 110 chemins, minimum +0,138 ns.
SHA-256 : `759fc5dcf6bacedb559212f524df851bbf140e02decbe185402e1be8bb8eb4ee`.
Après chargement, deux identifications complètes arrivent, puis une lecture
privée de diagnostic rend zéro octet au lieu de 32. Sans ces lectures, les
quatre commandes ordinaires `? ? X ?` reçoivent toutes leur réponse.
Le test USB intensif échoue néanmoins dès la première série : **804/1024
octets**, préfixe exact, puis aucune réponse au sondage immédiat. Les
compteurs montrent que le CPU continue d'émettre ; les identifications
suivantes peuvent revenir après réouverture et requête de contrôle.
La communication n'est donc pas validée.

- [Lecture de trace r12](usb_l12_r12_packet_probe.txt).
- [Commandes ordinaires r12](usb_l12_r12_idle_probe.txt).
- [Échec intensif r12](usb_l12_r12_stress_failure.txt).
- [Compteurs après échec](usb_l12_r12_failure_counters.txt).

Limite de la première trace : les NAK des sondages à vide effacent très
vite les paquets de données. Le candidat `gpu_l12_diag_r13` conserve donc
uniquement DATA0 et DATA1, y compris les paquets vides ; NAK et ACK ne
modifient plus cet historique. Le banc vérifie cette conservation pendant
des sondages répétés. La logique de transmission reste identique à r12.

Observation utilisateur sur r6 : six anneaux visibles, dont deux animés.
Cela correspond à la scène : deux rotations et quatre transformations
fixes. Cette observation ne valide pas à elle seule les échanges USB,
les quatre comparaisons de pixels ou la cadence mesurée.

### r13 : résultat dépendant du démarrage

Timing conforme : 110 chemins, minimum +0,140 ns. SHA-256 :
`37d510d39e4d8d938a7e30951a7c273aab06543dfb840cea100ac24f1785e2de`.
Console complète : 31 353 unités logiques, 23 189 registres, 225 BSRAM,
25 DSP et 8 PRIMARY. Firmware inchangé : 57 696 octets d'ITCM, BSS 28 992.

Au premier chargement, **100 séries USB / 544 100 octets exacts** passent,
puis **G0–G6/FAST/L11/L12 passent intégralement**. Les quatre poses affines
valent `3369f9e2`, `9bbe3479`, `18407cb2`, `06febe75`, chacune avec 13
commandes et zéro sous-alimentation. Les quatre références Python les
confirment. Animation : 54,87–54,96 images/s, dessin moyen 6 177 517 à
6 177 757 cycles CPU, maximum observé 6 220 029 cycles (7,78 ms).

- [Résultat USB initial](usb_l12_r13_stress_initial.txt).
- [Diagnostic graphique initial complet](gpu_l12_r13_uart_initial.txt).

**Le rechargement du même bitstream invalide la conclusion de fiabilité.**
Au deuxième chargement, la console ne s'énumère plus : erreurs noyau −71
pendant l'adresse et les descripteurs, avant toute commande utilisateur.
Au troisième chargement, l'énumération réussit mais le diagnostic ordinaire,
sans requête privée préalable, ne reçoit que **49/256 octets** à l'écho.
Ce build n'est donc pas publié comme version validée.

- [Énumération Linux, deux chargements](usb_l12_r13_enumeration.txt).
- [Absence de port](usb_l12_r13_cold_failure.txt).
- [Perte à l'écho](usb_l12_r13_cold_echo_failure.txt).
- [Trace après échec](usb_l12_r13_cold_packets.txt) : les paquets DATA vides
  effacent à leur tour les paquets utiles ; l'historique doit les filtrer.

### Candidat r14 : séquence de démarrage USB

Le montage précédent lançait les deux PLL en même temps et utilisait
directement leur signal combiné LOCK pour libérer le contrôleur. Le
candidat attend 1 024 cycles stables à 48 MHz avant de libérer la PLL B,
puis 1 024 cycles stables à 60 MHz avant d'annoncer le verrouillage au PHY,
puis 64 cycles à 60 MHz avant de libérer le contrôleur. Chaque attente
comprend aussi deux bascules de synchronisation. Une perte de verrouillage
réaffirme le reset de manière asynchrone, même si l'horloge s'arrête.
Le reset système maintient également le reset PHY. Les fréquences, les
contraintes SDC et les netlists fournisseur restent inchangées.

Le banc [usb_reset_release_tb.sv](rtl/usb_reset_release_tb.sv) vérifie
délai exact, stabilité, perte de verrouillage, arrêt d'horloge et impulsion
de verrouillage trop courte ([journal](usb_reset_release_simulation.txt)).
Cette séquence est un **candidat à tester sur plusieurs rechargements**,
pas encore une cause prouvée de la panne.

La trace r14 ignore aussi un DATA vide annoncé vide. Elle conserve les
paquets non vides et un DATA vide qui annoncerait à tort une longueur non
nulle. Les deux cas sont vérifiés dans le banc de trace.

`gpu_l12_diag_r14` : **rejeté au timing, non chargé**, −2,244 ns sur le
reset fourni par le contrôleur vers les bascules du PHY. Le OU ajouté
avec le reset système allonge ce trajet (9,045 ns de routage). Le candidat
`gpu_l12_diag_r15` retire ce OU redondant : le contrôleur fournit de nouveau
directement le reset PHY, tout en conservant la qualification des PLL et
la libération retardée du contrôleur. Les contraintes SDC ne changent pas.

`gpu_l12_diag_r15` : timing conforme, 110 chemins, minimum +0,143 ns,
SHA-256 `7c543a6d746bff5d2429dc24a81c5f658e02f87664a7cf2fba9595fbcbf081eb`.
Le test automatisé de rechargement s'arrête au **premier** essai : la
console s'énumère mais l'identification n'arrive pas. Le séquenceur est
donc insuffisant ; aucune conclusion de correction n'est tirée.

La nouvelle trace conserve cette fois les paquets utiles : DATA0 avec
64 octets, puis DATA1 avec 9 octets, ce dernier réémis à l'identique.
Les longueurs UTMI (67 et 12) et les CRC (respectivement `68f0` et `6b42`
dans l'ordre des octets transmis) correspondent exactement aux réponses
UART attendues pour `X?`. Les compteurs donnent 73 octets CPU, 2 commandes
livrées, 82 POP (73 + 9 repris) et une FIFO vide. Le trajet avant le PHY
produit donc les longueurs et CRC attendus sur cette séquence, tandis que
la réception PC reste défaillante. Une lecture privée échoue elle aussi
avec `EPROTO`. Le lien physique et le comportement après le PHY restent
à départager.

- [Résultat arrêté au premier échec](usb_l12_r15_reloads.json).
- [Échec d'identification](usb_l12_r15_failure.txt).
- [Paquets UTMI](usb_l12_r15_packets.txt), [CRC recalculés](usb_l12_r15_crc_check.txt).
- [Compteurs](usb_l12_r15_counters.txt).

`tools/check_gpu_reloads.py` vérifie l'empreinte du bitstream, les sources
figées et le timing, puis identifie la Pro Dock `2023112818` avant chaque
chargement SRAM. Il attend `DONE`, l'énumération de `11252024`, puis teste
l'USB sans requête privée préalable. Toute erreur arrête la série ; une
relance n'est jamais comptée comme réussite. La sélection parmi plusieurs
FTDI et le refus des cibles absentes/ambiguës sont contrôlés :
[journal de sélection](usb_reload_target_validation.txt).

### Comparaison L11 après redémarrage du PC

Après reprise de la session, la Pro Dock est toujours `2023112818`, mais
son adresse FTDI est devenue **3:4** (l'autre FTDI `2025041420` est 3:7).
Le SOFT-USB reste sur la branche **3-4.4.4**, derrière deux hubs. Tous les
chargements utilisent l'identité série, jamais l'ancienne adresse 3:73.

Le bitstream L11 archivé est rechargé sans recompilation : ses 79 sources
figées, son empreinte `163203fd…e800d` et son timing +0,093 ns sont vérifiés.
Il échoue lui aussi au premier tour USB : **173/256 octets**, préfixe exact,
puis aucune réponse. Une autre ouverture plusieurs minutes après
l'énumération expire dès l'identification. Ce résultat montre que les
défauts observés dans les conditions actuelles ne sont pas propres à L12.

- [Résultat L11 inchangé](usb_l12_l11_reload_failure.json).
- [Échec L11 inchangé](usb_l12_l11_reload_failure.txt).

Le port est actif (`power/control=on`, temps suspendu nul), et `fuser` ne
trouve aucun autre lecteur au moment de son contrôle. ModemManager annonce
le périphérique non pris en charge ; cela n'établit pas à lui seul qu'il
n'a effectué aucun sondage antérieur. Aucune modification de ce service,
du contrôleur USB hôte ou des autres cartes n'est effectuée.

Un essai avec le SOFT-USB directement branché au PC, si possible avec un
autre câble, a été demandé à l'utilisateur pour départager le lien et le
FPGA. Le **1er octobre 2026**, l'utilisateur indique avoir déplacé le
matériel vers le PC **`michael@ax15`**, l'ancien PC ayant trop de
périphériques et de perturbations. La topologie USB sur ce nouveau PC et
le résultat de la comparaison restent à mesurer ; ce déplacement n'est
pas encore une preuve de résolution.

La reprise prévoit de comparer les bitstreams L11 archivé et L12 r13
inchangés, avec contrôle des empreintes, sources figées et rapports de
timing avant tout chargement. L11 était le dernier bitstream chargé avant
le déplacement. Aucun L12 n'est archivé comme fiable et les modifications
L12 restent non committées. Les résultats graphiques complets obtenus sur
r13 restent conservés, séparément de cette réserve USB.

### Comparaison sur ax15, 1er octobre 2026

La connexion SSH et les droits USB sont opérationnels. Les tests sont
installés dans `/home/michael/console-validation-20261001` sur ax15, avec
un chargeur openFPGALoader 1.1.1 autonome. Les empreintes des bitstreams,
les sources figées et les rapports de timing sont vérifiés avant chargement.
La règle udev est limitée au FTDI `2023112818` et au CDC `11252024`.

Au moment de ces essais, le JTAG est en **3-3.2**, le SOFT-USB en **3-3.1**,
derrière le même hub `05e3:0610`. Le SOFT-USB fonctionne à 480 Mbit/s et
apparaît en `/dev/ttyACM1`. Le port `/dev/ttyACM0` appartient au J-Link et
n'est pas utilisé. Les chargements restent exclusivement en SRAM.

| Bitstream inchangé | Résultat des rechargements | Premier défaut |
| --- | --- | --- |
| L11 `gpu_l11_usb_r13` | Arrêt au premier chargement | Écho 256/256 octets mais un octet dupliqué et un autre perdu ; identification suivante également altérée |
| L12 `gpu_l12_diag_r13` | Deux chargements avec 100 tours USB réussis chacun ; troisième en échec | Écho 1024/1024 octets altéré, avec duplications et pertes ; cinq octets supplémentaires reçus ensuite |
| L12 `gpu_l12_diag_r15` | Arrêt au premier chargement | Écho 1020/1024 octets ; deux suppressions de deux octets |

Les deux réussites r13 représentent **1 088 200 octets binaires exacts**.
Elles ne valident pas la série de trois rechargements, arrêtée au premier
défaut comme prévu. La suite graphique automatique n'a donc pas été lancée
sur ax15 : elle ne démarre qu'après la réussite de toute la série USB.

Après les échecs r13 et r15, les compteurs indiquent 1 475 octets reçus du
CPU, 1 360 octets USB OUT livrés au pont UART, aucune erreur signalée sur
la réception PHY, et aucune donnée restante dans la FIFO IN. La lecture
de ces compteurs intervient **après** les tests ordinaires ; aucune
requête de contrôle privée n'a précédé les échos de validation. Le nombre
nul d'erreurs de réception PHY ne valide pas le trajet d'émission vers le PC.

Les journaux complets, octets attendus/reçus, réponses suivant les échecs
et résultats JSON sont conservés dans [usb_ax15_20261001](usb_ax15_20261001/).
Les sondages après échec sont également conservés. `fuser` ne trouve pas
d'autre lecteur au moment du contrôle ; ModemManager annonce la console
non prise en charge, sans que cela prouve l'absence de tout sondage passé.

**Conclusion limitée : le changement de PC seul ne résout pas le défaut.**
Le candidat de séquencement r15 ne suffit pas non plus dans ces conditions.
L'utilisateur confirme la présence du hub et prévoit de le retirer le soir
du 1er octobre, étant actuellement à distance. La prochaine comparaison
portera sur le SOFT-USB directement branché sur ax15, idéalement avec un
autre câble de données. En attente de cette intervention, r15 reste chargé ;
aucun résultat L12 n'est promu en version fiable, aucune recompilation
spéculative n'est lancée. La présence du hub ne suffit pas à établir qu'il
est responsable du défaut.

### SOFT-USB directement sur ax15, soirée du 1er octobre

Après intervention de l'utilisateur, la console `11252024` est vérifiée
sur **3-7**, directement sous le contrôleur xHCI, à 480 Mbit/s. Le JTAG
`2023112818` reste sur 3-3.2, ce qui ne place plus de hub sur le trajet
SOFT-USB testé. Les mêmes bitstreams et le même test de trois rechargements
avec 100 tours USB sont utilisés ; chaque série s'arrête au premier défaut.

| Bitstream inchangé | Résultat sans hub |
| --- | --- |
| L11 `gpu_l11_usb_r13` | Premier chargement : identification avec caractères dupliqués, écho 64/64 altéré puis octets supplémentaires |
| L12 `gpu_l12_diag_r13` | Premier chargement : pas de port CDC dans les 25 secondes ; Linux reconnaît le périphérique mais échoue à `SET_CONFIGURATION` (`can't set config #1, error -71`) |
| L12 `gpu_l12_diag_r15` | Premier chargement : identification tronquée puis écho 254/256, deux octets manquants |

Le retrait du hub ne suffit donc pas à résoudre le défaut. Les journaux
et données sont dans les dossiers `*_direct` de
[usb_ax15_20261001](usb_ax15_20261001/). Aucun de ces essais ne valide
une série complète ni ne déclenche la suite graphique.

Un diagnostic r15 envoie ensuite des commandes d'écho d'un seul octet.
Le premier essai utilise un délai court et ne suffit pas à exclure une
réponse tardive. Un second garde le même descripteur série ouvert pendant
une seconde d'attente puis une seconde supplémentaire, sans requête de
contrôle privée avant le constat d'échec. L'itération 499 attend `5c` et
ne reçoit rien ; la commande suivante reçoit correctement `24`.

La trace UTMI conserve un DATA0 (`c3`), longueur utile annoncée 1,
4 octets transmis avant le PHY, CRC `4086` dans l'ordre du fil. Ce CRC
correspond à `5c`, et à aucun autre des 256 payloads d'un octet possibles.
Les trois paquets précédents correspondent aussi aux trois octets attendus.
Le compteur UART indique `last_uart=92` (`5c`), la FIFO est vide et aucun
paquet n'est en attente. Cela confirme le paquet attendu à l'entrée du
PHY, mais n'identifie pas encore la cause de son absence côté hôte.

- [Diagnostic avec attente prolongée](usb_ax15_20261001/l12_r15_ax15_direct/single_byte_long_probe.txt).
- [Vérification indépendante des CRC](usb_ax15_20261001/l12_r15_ax15_direct/crc_check.txt).

### Diagnostic r16 : numéros DATA des acquittements

L'observateur passif `usb_packet_trace.v` conserve désormais, au début de
chaque paquet enregistré, le PID DATA du dernier acquittement observé
séparément sur l'entrée UTMI et sur `usb_txpktfin`. La reconnaissance UTMI
exige un paquet reçu d'un seul octet `d2`, sans erreur PHY et relatif au
dernier DATA EP2 émis. Les paquets DATA vides participent à cet état des
acquittements même lorsqu'ils ne sont pas conservés dans les quatre
enregistrements utiles.

Les bits 62/61 portent la validité et le bit DATA1 du dernier ACK UTMI ;
60/59 portent la validité et le bit DATA1 de la dernière fin du contrôleur.
Le bit 58 vaut 1 pour reconnaître ce format ; les autres champs sont
inchangés. L'outil hôte reste compatible avec les anciens enregistrements.
Cet ajout n'alimente aucun signal fonctionnel USB.

Le banc vérifie séparément les deux sources d'acquittement, les retries,
les ACK malformés ou signalés erronés, les autres endpoints, les DATA vides
et le reset : [simulation](usb_packet_ack_trace_simulation.txt).
`tools/check_usb_isolated.py` rend le diagnostic d'échos unitaires
reproductible : délai d'une seconde, seconde supplémentaire sur anomalie,
même ouverture série, captures privées seulement après l'échec. Il ne
remplace pas les tests d'endurance ordinaires.

`gpu_l12_diag_r16` est rejeté au timing : −1,367 ns entre `gi` et les
registres d'état du blitter, avec 5,145 ns de routage sur un décodage partagé
à 45 charges. Il n'est pas chargé. r17 place ce décodage près de la machine
d'état ; les netlists synthétisées du blitter r16 et r17 sont identiques.

`gpu_l12_diag_r17` ne conserve qu'un chemin de setup négatif, −0,320 ns
entre `sp_xa` et `rw[1]`, dont 2,996 ns entre le multiplexeur final et son
registre de destination. Il n'est pas chargé non plus. r18 rapproche ce
multiplexeur des registres de largeur, en le retrouvant depuis la broche D
stable de `rw_1_s2`. Aucun changement de fréquence, de SDC ou de logique
graphique n'accompagne ces contraintes de placement.

r18 corrige ces trajets mais son placement expose un autre chemin négatif,
−1,335 ns sur `copy_left`. Il n'est pas chargé. r19 conserve la position
du décodage de fin de ligne et, pour `rw[1]`, place seulement la bascule
de destination entre son multiplexeur et ses consommateurs, au lieu de
fixer le multiplexeur près des registres. **r19 passe le timing** : 110 chemins
détaillés, minimum +0,140 ns, TNS nul. SHA-256 :
`4c087f65fc9269dade60c460624e753790d743a41bbfd76d1e60279fef236471`.
Ses 83 sources figées sont vérifiées avant transfert vers ax15. Le contenu
complet du module `blitter` synthétisé est identique entre r16 et r19.

Pendant ces compilations, le nouvel outil hôte passe une séquence de
1 024 octets isolés sur le r15 toujours chargé. Ce résultat est conservé
dans `l12_r15_ax15_direct/isolated_tool` ; il ne remplace pas les pertes
précédentes et confirme que le défaut n'est pas permanent.

### Observations r19 sur ax15, câble direct inchangé

r19 est chargé en SRAM après ces vérifications. Le test ordinaire échoue
au premier tour : identification altérée, puis 60/64 octets à l'écho, avec
deux suppressions de deux octets. La série s'arrête, sans validation GPU.

Le diagnostic isolé observe ensuite `11`, `5a`, `a3` reçus correctement,
puis **`ec` manquant après 2,016 secondes** sur la même ouverture série.
Les quatre enregistrements UTMI donnent exactement les CRC de ces quatre
octets, chacun dans un paquet de longueur utile 1. Pour chacun, le PID
émis alterne par rapport au dernier PID acquitté, avec accord entre
l'observation UTMI de l'ACK et la fin fournie par le contrôleur. La trace
ne confirme donc pas l'hypothèse d'un numéro DATA déjà acquitté réutilisé
pour ces quatre paquets. Elle décrit l'état **avant leur émission**, pas
une capture électrique du câble ni l'acquittement ultérieur du dernier.

Après l'échec, `last_uart=236` (`ec`), 199 octets UART, 90 octets OUT
livrés, FIFO vide, aucun paquet en attente et zéro erreur de réception
PHY signalée. Le paquet utile attendu est bien présent à l'entrée du PHY ;
la cause exacte de son absence côté hôte reste indéterminée.

- [Résultat des rechargements](usb_ax15_20261001/l12_r19_ax15_direct/result.json).
- [Écho ordinaire en défaut](usb_ax15_20261001/l12_r19_ax15_direct/load1/usb.log).
- [Diagnostic isolé](usb_ax15_20261001/l12_r19_ax15_direct/isolated/result.json)
  et [trace des ACK](usb_ax15_20261001/l12_r19_ax15_direct/isolated/diagnostic.txt).
- [CRC recalculés](usb_ax15_20261001/l12_r19_ax15_direct/crc_check.txt).

L'utilisateur confirme que le câble SOFT-USB n'a pas été remplacé lors
du retrait du hub. Un essai avec un autre câble de données, sur le même
port direct, est demandé. r19 reste chargé pour comparer d'abord ce seul
changement. Aucun de ces diagnostics n'établit que le câble est en cause ;
aucune version L12 n'est publiée comme fiable.

### Tentative après remplacement du câble

L'utilisateur indique avoir effectué le remplacement. Le premier test,
prévu sans rechargement, ne démarre pas : aucune console `359f:2011`
n'est détectée. Le FTDI a aussi changé de connexion : `2023112818` est
désormais sur **3-3.1**, bus:dev **3:65** lors du contrôle. L'état SRAM
après ces manipulations n'étant pas établi, le même r19 est rechargé.

Le chargeur termine avec succès et `DONE`, mais aucun port SOFT-USB
n'apparaît dans les 25 secondes. Linux ne signale pas de nouvelle
tentative de connexion SOFT-USB après ce chargement ; seul le FTDI est
visible. Les reconnexions et erreurs FTDI plus anciennes dans le journal
ont lieu pendant les manipulations, avant le chargement de 21:05, et ne
sont pas attribuées au nouveau firmware.

Cet essai **ne permet pas de comparer la fiabilité des deux câbles** :
aucun écho n'a pu être envoyé avec le nouveau branchement. La vérification
du connecteur SOFT-USB, du port direct et du câble de données est demandée.
r19 reste chargé, sans nouveau build ni test matériel en cours.

- [Tentative sans rechargement](usb_ax15_20261001/l12_r19_new_cable/usb.log).
- [Chargement et attente d'énumération](usb_ax15_20261001/l12_r19_new_cable_reloads/result.json).
- [Journal noyau](usb_ax15_20261001/l12_r19_new_cable_reloads/enumeration.txt)
  et [topologie](usb_ax15_20261001/l12_r19_new_cable_reloads/topology.txt).

### Nouveau câble connecté : défaut reproduit, y compris sans cdc_acm

Après la dernière reconnexion confirmée par l'utilisateur, la console revient
sur **3-7**, directement sur ax15, à **480 Mbit/s**, `/dev/ttyACM1`, série
`11252024`. Le test reprend **sans recharger le r19** déjà présent :

- identification initiale exacte ;
- premier tour, écho de 64 octets : **62 reçus**, suppression des positions
  13 et 14 ; la réponse d'identification suivante est aussi altérée ;
- diagnostic isolé : le premier octet `11` manque encore après **2,022 s**,
  avec le même descripteur série ouvert pendant toute l'attente ;
- trace UTMI : DATA1 (`4b`), longueur utile 1, quatre octets acceptés,
  CRC `80b3`, correspondant à `11`. Le dernier ACK précédent est DATA0
  dans les deux observations. `last_uart=17`, FIFO vide et aucun paquet
  en attente après le défaut.

Le remplacement du câble n'a donc pas suffi. Il ne démontre pas à lui
seul que toute la liaison physique ou son alimentation est correcte.

`tools/check_usb_bulk.py` ajoute une comparaison **sans le pilote série** :
sélection stricte du périphérique, vérification de l'absence de lecteur,
détachement temporaire de `cdc_acm`, accès usbfs direct à EP2 OUT/IN,
lectures IN continues dans un thread, puis libération des interfaces et
rattachement du pilote dans le bloc de nettoyage. Aucun reset USB, changement
de configuration ou rechargement FPGA n'est effectué. Le rythme des IN
diffère de celui du pilote CDC : un succès ne prouverait pas l'absence
du défaut CDC.

Deux essais rencontrent une **erreur de protocole usbfs `EPROTO` (71)** :

| Essai | Échos unitaires exacts avant arrêt | Dernier octet | Observation |
|---|---:|---|---|
| `direct_bulk` | 91 | `bb` | Octet reçu ; erreur 71 du lecteur IN pendant la garde suivante |
| `direct_bulk_repeat` | 119 | `b7` | Octet reçu ; erreur 71 environ 0,31 ms plus tard |

Les quatre derniers paquets utiles UTMI sont chaque fois des répétitions
du dernier octet avec le même DATA1 et son CRC exact (`00cc` pour `bb`,
`00c9` pour `b7`), après un dernier ACK DATA0 observé. Ce sont des indices
sur les reprises, pas une capture des signaux électriques sur D+/D−.
La cause précise de l'erreur reste à déterminer ; elle se manifeste aussi
à l'interface usbfs sans `cdc_acm` et ne peut pas être attribuée seulement
à pyserial.

Le premier JSON a un libellé `late` inadéquat : `received` contient déjà
`bb` et `reader_errors` contient l'erreur 71. Le script a été corrigé pour
classer prioritairement ce cas `usb_error` et dater les erreurs ; le second
essai utilise cette version. La première preuve brute est conservée intacte.
Les deux nettoyages finissent sans erreur et `cdc_rebound=true`.

Résultats : [écho CDC](usb_ax15_20261001/l12_r19_new_cable_connected/usb.log),
[octet isolé](usb_ax15_20261001/l12_r19_new_cable_connected/isolated/result.json),
[USB direct 1](usb_ax15_20261001/l12_r19_new_cable_connected/direct_bulk/result.json),
[USB direct 2](usb_ax15_20261001/l12_r19_new_cable_connected/direct_bulk_repeat/result.json).

### Vérification des pistes alimentation et MS5351

L'utilisateur confirme que la carte est alimentée par le **jack 12 V**.
Il précise ensuite que le nouveau câble mesure **50 cm**. Sipeed recommande
une alimentation auxiliaire et un câble de moins d'un mètre, idéalement
0,5 m, dans la [FAQ officielle SOFT-USB](https://github.com/sipeed/TangMega-138KPro-example/blob/main/usb2_soft/readme.md).
Le branchement 12 V ne constitue pas une mesure de la tension ou de son bruit.

Les deux MS5351 ne pilotent pas l'horloge de **ce design**. Le CST fixe
`clk` sur **P16** et le top relie cette référence 50 MHz à `Gowin_PLL_F`
(48 MHz), puis à `Gowin_PLL_B` (60 et 960 MHz). L'exemple USB Sipeed utilise
également P16. L'[arbre d'horloges Sipeed](https://github.com/sipeed/TangMega-138KPro-example/blob/main/sfp%2B/docs/SET_5351.md)
relie les MS5351 aux références SERDES et à `USR_CLK_IN` **V22**.
Il n'y a donc pas de configuration MS5351 manquante à ajouter pour ce
trajet USB. Cette vérification de câblage ne mesure ni la gigue ni la
qualité électrique de P16 ou des PLL internes.

### Comparaison avec l'ancienne image E0b minimale

L'image archivée `console_e0b_validé_mire800x480_cdc.fs` (USB en boucle
UART + mire, sans CPU ni DDR3 actifs) est chargée temporairement, puis
le r19 est restauré. Les deux charges identifient de nouveau le FTDI
`2023112818` sur `3:66` et se terminent par `DONE`, code 0.

E0b correspond exactement à `tang/impl/pnr/console_e0b.fs` : SHA-256
`9b844eeb0e65c55244920b98f07b1a770a48b7070bb522b4fcb0fbc8caf86614`.
Son rapport associé contient 110 chemins détaillés, minimum +0,147 ns,
TNS nul. Ce rapport historique contraint le LCD à 10,5 MHz et indique
un Fmax LCD de 207,738 MHz ; ce n'est pas une nouvelle validation du LCD.
Le timing USB 60/120 MHz est non négatif. Aucune contrainte n'est modifiée.

Après 48 échos unitaires exacts, le suivant échoue : **un `c1` envoyé,
deux `c1` reçus** ; aucun autre octet pendant la seconde de grâce.
Ce résultat n'est pas imputable aux commandes GPU ou à la nouvelle logique
affine, absentes de cette image. E0b emploie néanmoins l'ancienne FIFO USB,
avec ses défauts de reprise connus : il ne permet donc pas de distinguer
à lui seul le PHY, ses horloges, la liaison électrique et la logique USB.

Le r19 est ensuite restauré, après vérification de son empreinte, de ses
83 sources figées et de son timing. Le test CDC d'un tour échoue à son tour :
**253/256 octets**, pertes et insertion, identification altérée.
r19 reste chargé, la flash est intacte, aucun test matériel ne tourne.

[Résultat comparatif](usb_ax15_20261001/l12_r19_new_cable_connected/baseline_comparison/result.json),
[test après restauration](usb_ax15_20261001/l12_r19_new_cable_connected/baseline_comparison/r19_usb.log).

### Comparaison du contrôleur régénéré, High Speed / Full Speed

Après confirmation du câble de 50 cm et du jack 12 V, deux builds de
diagnostic sont préparés :

```sh
python3 tools/build_gpu.py --name gpu_l12_diag_r20 --usb-controller gowin-high
python3 tools/build_gpu.py --name gpu_l12_diag_r21_fs --usb-controller gowin-full
```

La netlist Sipeed du contrôleur est une configuration High Speed figée.
Changer `HSSUPPORT` dans la ROM de descripteurs ne change pas ce choix
matériel. Les variantes sont donc générées avec `GowinSynthesis` depuis
l'IP de Gowin **1.9.12**, dans le dossier propre à chaque build. L'original
Sipeed 1.9.10.03 reste intact. Les fichiers fournisseur sont copiés sans
modification ; seuls le projet de génération et les macros de configuration
sont créés. Les sources, macros et netlist produite sont figées et hachées.
`--usb-controller reference`, par défaut, conserve le contrôleur historique.

Les configurations High/Full diffèrent uniquement par HSSUPPORT/FSSUPPORT.
EP0 64 octets, UTMI, SELFPOWERED et les types d'endpoints restent ceux de
la configuration Sipeed. Le wrapper `console_gpu_usb_fs.v` sélectionne
également les descripteurs Full Speed existants. Le PHY et les fréquences
CPU/bus/GPU/LCD sont conservés. Le contrôleur changeant aussi de version
par rapport au r19, il faut tester d'abord le r20 à 480 Mbit/s : un succès
du seul r21 ne suffirait pas à attribuer l'amélioration à la vitesse USB.

Contrôles avant carte : le firmware binaire et le PHY ont les mêmes
empreintes que r19. Les modules synthétisés complets `blitter`,
`gpu_blit_dma`, `gpu_accel`, `usb_fifo` et `usb_packet_trace` sont identiques
entre r19 et r20. Cela n'est pas une preuve d'équivalence du contrôleur
fournisseur, qui est précisément la partie soumise à l'essai.

Le redémarrage de la session a interrompu le suivi des commandes, mais
les deux processus `gw_sh` continuent dans leurs dossiers respectifs.
Aucune seconde compilation n'est lancée dans ces dossiers. Les résultats
finaux doivent encore passer le contrôle des marges et des empreintes
avant toute programmation. L'outil de rechargement accepte désormais
`--expected-usb-speed 480` ou `12`, vérifie `/sys/bus/usb/devices` après
chaque énumération et consigne cette valeur dans le résultat JSON.

Le r20 termine avec **110 chemins détaillés, minimum +0,140 ns, TNS nul**.
Ses 89 entrées de manifeste sont vérifiées avant transfert et chargement.
SHA-256 : `e47c5523f38c4aabecd4749429720d247b35fbb2de1794e80416b165759df8ac`.
Ressources : 31 398 cellules logiques, 23 285 registres, 225 BSRAM,
25 DSP, 8 horloges PRIMARY.

Chargement SRAM réussi sur le FTDI `2023112818`, `3:66`, mais **échec
d'énumération** : Linux détecte plusieurs tentatives High Speed sur 3-7,
avec `device descriptor read/all, error -71`, puis abandonne. Aucun port
CDC ne s'ouvre dans les 25 secondes et le test s'arrête avant les échos
et avant le GPU. L'essai ne valide donc pas le nouveau contrôleur HS.
Voir [résultat r20](usb_ax15_20261001/l12_r20_new_controller_hs/result.json)
et [journal noyau](usb_ax15_20261001/l12_r20_new_controller_hs/enumeration.txt).

Le r21 FS possède les mêmes sources GPU, le même firmware et le même
fichier PHY que r20, mais la synthèse n'est **pas identique** : les
constantes différentes changent les optimisations et les noms des cellules.
La comparaison exacte des netlists r19/r20 ne s'étend donc pas au r21.
Il reste à valider son timing et son fonctionnement sur carte.

Le r21 termine finalement en **échec de timing, minimum −1,051 ns**.
Il n'est ni transféré ni chargé. Les chemins négatifs détaillés partagent
le calcul de largeur de span du moteur de triangles. Le trajet de
`line_right_6_s0` en R32C174 vers `n8485_s` en R36C122 coûte 2,748 ns.
Le r22 FS fixe cette première cellule de retenue près du bord calculé,
en R33C174. Ce complément est réservé au mode `gowin-full`, dans
`tang/constr/gpu_usb_fs.cst` ; le CST de référence reste intact.
Le build fige le CST de base, le complément et leur copie assemblée.
Il n'y a aucun changement de RTL du GPU, de fréquence ou de SDC.

Le r22 échoue également : **minimum −0,764 ns**, 11 extrémités setup
en défaut, TNS −4,512 ns, aucune violation hold. Les chemins détaillés
négatifs restent dans `gpu_triangle`. Il n'est pas chargé sur carte.
La contrainte de r22 concerne en réalité le bit 6 de la soustraction,
pas la première cellule de toute la chaîne de retenue.

Le r23 FS rapproche cette chaîne des bords écrêtés, désormais placés
vers les colonnes 142–147 dans r22 : `n8485_s` passe de R33C174 à R33C148.
Le trajet d'entrée de la soustraction valait encore 1,551 ns dans r22.
Il s'agit d'un nouvel essai de placement, dont le résultat de timing et
le test matériel restent à établir. Les autres compilations Gowin du PC
sont laissées intactes ; seuls les dossiers de ce projet sont utilisés.

Le **r23 passe le timing** : 110 chemins détaillés, minimum **+0,140 ns**,
TNS nul. Ses 91 fichiers figés sont vérifiés, ainsi que son bitstream :
`cf4bfbddf96f0cd5b6a50d12eefd502917be74a3b3f28410a5ea53d003fd602f`.
Ressources : 31 264 cellules logiques, 23 250 registres, 225 BSRAM,
25 DSP et 8 PRIMARY. Le firmware binaire et le PHY sont identiques à r20.
Les modules synthétisés complets `gpu_triangle`, `blitter`, `gpu_blit_dma`
et `usb_fifo` sont identiques dans r21, r22 et r23 ; leurs empreintes et
les résultats de timing sont conservés dans
[le relevé des builds Full Speed](usb_ax15_20261001/full_speed_build_checks.json).

Chargement SRAM du r23 réussi sur le FTDI `2023112818` (`3:66`). Linux
détecte cette fois des périphériques **full-speed** sur le port direct 3-7,
mais les quatre lectures du descripteur échouent avec **−110** (expiration).
Aucun port CDC n'apparaît. Le test s'arrête à la première programmation,
avant les échos, les deux rechargements suivants et la suite GPU. Le noyau
confirme la détection Full Speed ; il n'existe pas de périphérique énuméré
permettant de valider la vitesse par sysfs et d'échanger des données.
Voir [résultat r23](usb_ax15_20261001/l12_r23_full_speed/result.json) et
[journal noyau](usb_ax15_20261001/l12_r23_full_speed/enumeration.txt).

**Le r19 est restauré ensuite en SRAM**, après nouveau contrôle de ses
83 sources, du timing et du SHA-256. Sa console revient sur `/dev/ttyACM1`
à **480 Mbit/s**, mais le stress échoue dès la première série : 62 octets
reçus sur 64, suppression des octets aux positions 9 et 10. La bannière
suivante est également altérée. Il s'agit du retour au comportement de
référence défaillant, pas d'une réparation ni d'une validation de L12.
Voir [restauration et écho](usb_ax15_20261001/l12_r19_restored_after_fs/result.json).
Après fermeture du test, la commande `Z` est envoyée seule : le firmware
répond `AFFINE ANIMATION started`. Cette reprise est
[journalisée](usb_ax15_20261001/l12_r19_restored_after_fs/resume_affine.json),
sans nouvelle confirmation visuelle du LCD. Aucun test ni build de cette
série ne reste en cours à la fin de cette reprise.

Ces essais ne valident aucun nouveau contrôleur USB. La comparaison
480/12 Mbit/s est limitée par l'échec d'énumération des variantes régénérées
avec Gowin 1.9.12 ; elle ne permet pas de conclure que le défaut initial
est exclusivement électrique ou propre au mode High Speed. Le mode
`reference` reste celui du build par défaut ; aucun bitstream L12 nouveau
n'est promu dans `bitstreams/`.

### Revue croisée avec la session logic_analyser_wifi

Michael signale un défaut d'instabilité sur une autre carte et un autre PC,
et demande une comparaison entre les deux sessions Codex. Le projet est
confirmé : `/home/michael/logic_analyser_wifi`, sur ce même PC de travail.
Ses consignes et ses fiches USB sont lues sans modification, sans action
sur ses builds ou sa carte.

Distinction essentielle : ce projet utilise un **périphérique USB3 via
SerDes** ; la console Pro Dock utilise un **périphérique SOFT-USB2 via UTMI**.
Le nouvel hôte USB2 de manette du projet voisin constitue un troisième
chemin. Un symptôme d'instabilité commun ne prouve pas une même faute RTL.

Les notes du projet voisin décrivent toutefois des changements de comportement
d'un même bitstream après reset hôte et des limites de l'analyse statique
entre les domaines RX et pclk. Ici, `gpu.sdc` déclare aussi les domaines
USB 60/120/960 MHz asynchrones. Une revue des séquences de reset, de la
cohérence des traversées et des contrats de reprise est donc prioritaire ;
le timing positif ne constitue pas à lui seul une preuve de leur validité.
Les exceptions de timing des diagnostics du projet voisin doivent rester
explicites dans toute comparaison avec les builds console.

Le [relevé d'échange côté console](USB_INTERSESSIONS_CONSOLE.json) rassemble
l'état exact du r19 chargé, les preuves, les empreintes des sources USB
réellement compilées, les documents voisins consultés et les questions
destinées à l'autre session. Ce relevé est préparé ici : il ne prétend pas
avoir reçu de réponse de l'autre agent. Chaque session peut publier sa
réponse dans son propre projet. La lecture d'un fichier partagé ne réveille
pas automatiquement une session inactive.

### Limite des simulations : horloges indépendantes PC / carte

Michael demande explicitement si les simulations ont fait dériver deux
horloges, par exemple 125 et 124,5 MHz. **Non pour la liaison PC–PHY USB2** :
les bancs de FIFO, de paquets et de flux (`usb_tx_retry_tb`, `usb_in_packet_tb`,
`usb_stream_tb`) utilisent une seule horloge `always #5` en `1ns/1ps` et des
stimuli synchronisés sur ses fronts. Ils vérifient une logique en cycles,
sans inclure le PHY ni un émetteur USB indépendant. Le banc UART varie les
durées de bit (521, 516, 531 cycles), mais conserve aussi cet alignement.
Les résultats antérieurs ne doivent pas être présentés comme une validation
de la récupération USB avec dérive d'horloge ou du CDC interne du PHY.

Dans le top réel, le pont UART, les ports EP2 de la FIFO et le contrôleur
USB partagent `phy_clk` à 60 MHz. Mettre artificiellement deux fréquences
sur ces ports ne reproduirait pas le raccordement de la carte. Le test
manquant doit placer l'indépendance temporelle côté données USB reçues,
en conservant les rapports des horloges locales du PHY, puis balayer phases,
écarts de fréquence et séquences de reset/lock. L'audit structurel des CDC
reste nécessaire : un modèle numérique n'établit pas l'absence de métastabilité.

L'USB-IF spécifie 480 Mbit/s ±0,05 % pour chaque émetteur High Speed
([EL_2](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification%28v1.07%29.pdf)).
L'exemple 125/124,5 MHz représente 4 000 ppm ; pour USB2 HS, ce serait un
essai hors spécification, à séparer des essais nominaux à ±500 ppm.

Un modèle fournisseur `usb2_0_softphy.vo` non chiffré est présent dans
la référence Sipeed locale. Il n'a pas encore été exécuté : sa présence
ne prouve pas qu'une simulation complète avec les primitives Gowin est
opérationnelle ni représentative du bitstream chargé. Son chemin, son
empreinte et cet audit sont ajoutés au relevé d'échange intersessions.
Cette revue ne modifie aucun RTL, contrainte ou bitstream.

### FIFO à deux horloges : présence vérifiée, CDC non encore validé

À la suite de la remarque de Michael, la structure des FIFO est vérifiée.
Dans `usb_fifo.v`, `clk_cross_fifo` possède bien des ports lecture/écriture
distincts, des pointeurs Gray et deux étages de synchronisation. Le top
console raccorde néanmoins les deux côtés à `phy_clk` 60 MHz : ce n'est
pas à cet endroit que se situe l'indépendance entre le PC et la carte.

Le modèle fournisseur `usb2_0_softphy.vo` contient deux mémoires SDPB :

| Sens | FIFO interne | Horloge d'écriture CLKA | Horloge de lecture CLKB |
|---|---|---|---|
| Réception | `fifo_4to8_sub_inst` | `sclk`, 120 MHz | `clk_i`, 60 MHz |
| Émission | `fifo_8to4_sub_inst` | `clk_i`, 60 MHz | `sclk`, 120 MHz |

Pour chacune, les cellules des étages `wq1/wq2` et `rq1/rq2` observées
sur le bit 0 sont cadencées dans leurs domaines destinataires respectifs.
Les hiérarchies des deux FIFO figurent aussi dans le rapport de timing
du r19 chargé. Le relevé intersessions conserve les cellules et leurs
connexions extraites du modèle.

Ce constat réfute une absence générale de FIFO à deux horloges. Il ne
valide pas leurs resets, les contraintes physiques des pointeurs, la
gestion plein/vide ni les signaux de contrôle qui pourraient les contourner.
Aucun test du PHY avec une source USB indépendante n'a encore été exécuté.

Première vérification de faisabilité, le 2 octobre : Verilator reçoit le
modèle `.vo` et la bibliothèque Gowin `gw5a/prim_sim.v` intacts en mode
`--lint-only --timing`. Le chargement direct échoue sur des instructions
`deassign` non prises en charge ([journal](usb_phy_model_lint_20261002.txt)).
La bibliothèque entière étant analysée, il reste à identifier les primitives
effectivement utilisées avant de conclure à une incompatibilité du modèle.
Aucune simulation fonctionnelle PHY n'a été exécutée. Le plan enregistré
dans le relevé intersessions prévoit un simulateur compatible si nécessaire,
sans supprimer le comportement des primitives pour obtenir un faux succès.


### 2 octobre — bancs à horloges indépendantes, reset commun et r25

Les limites historiques décrites ci-dessus sont désormais complétées par de
nouveaux bancs. Icarus Verilog 12.0 est extrait sous `/tmp/console-usb-sim-tools`
depuis le paquet Ubuntu, sans installation système. Les `.vo` Sipeed et la
bibliothèque `gw5a/prim_sim.v` Gowin 1.9.12 sont utilisés **sans modification**.
Les compagnons de synthèse `.v` de la référence sont identiques à ceux du
projet pour le PHY et le contrôleur ; leurs empreintes figurent dans les JSON.

#### Réception du PHY : 40 configurations réussies

`tools/check_usb_phy_sim.py` et `rtl/usb_phy_drift_tb.sv` injectent réellement
sur les broches numériques du PHY un flux USB HS NRZI, avec bourrage de bits,
SYNC, PID, charge utile et CRC16, puis EOP. L'émetteur hôte possède sa propre
base de temps. Les horloges carte restent cohérentes à 960/60 MHz ; le modèle
fournisseur dérive son horloge interne 120 MHz. Des échéances absolues à la
femtoseconde évitent une dérive numérique due à l'arrondi des délais.

- Couples hôte/carte en ppm : `(0,0)`, `(+500,-500)`, `(-500,+500)`,
  `(+500,+500)`, `(-500,-500)`.
- Huit décalages de lancement entre 0 et 2,001 ns.
- ACK et DATA0/DATA1 de 0, 1, 2, 63, 64, 511 et 512 octets ; motifs zéro,
  `ff` et déterministe variable, avec bourrage maximal et franchissements FIFO.
- Trois suites par configuration : démarrage, reset interrompant un paquet,
  puis perte de LOCK avec reset externe et reprise.
- **40/40**, **1 200 paquets complets**, **264 600 octets UTMI vérifiés**
  (PID/CRC compris), plus les paquets volontairement interrompus.

Journal : [usb_phy_drift_20261002.json](usb_phy_drift_20261002.json).
L'état initial J du banc initialise le comparateur différentiel fournisseur
avant le repos HS SE0 : son modèle conserve sa valeur précédente sur 00.
Sans cette phase d'attachement, un X artificiel avait empêché le premier ACK.
Aucun `force` interne ni remplacement de primitive n'est utilisé.

Cela teste la récupération logique des données et le chemin RX 120→60 MHz.
Cela **ne prouve pas** les marges analogiques, le réseau RC, la métastabilité,
les contraintes physiques Gray, les délais après placement, l'énumération
complète ni la validation des paquets par le contrôleur.

#### FIFO applicative : 18 configurations réussies

`rtl/usb_cdc_fifo_tb.sv` instancie le véritable `clk_cross_fifo` de `usb_fifo.v`.
Les six couples écriture/lecture sont 125/124,5, 124,5/125, 60/59,94, 60/60,
80/60 et 60/80 MHz, chacun avec trois phases. Le scoreboard vérifie l'ordre
et le contenu malgré le plein, le vide, les tours de pointeurs, les requêtes
refusées, les resets contenant des données et l'arrêt des deux horloges.
**1 077 771 octets comparés**, aucune divergence ; les données explicitement
abandonnées au reset sont comptées séparément. Le cas 125/124,5 porte sur la
FIFO, pas sur une conformité USB HS à cet écart.

Journal reproductible : [usb_cdc_reset_20261002.json](usb_cdc_reset_20261002.json),
lancé par `tools/check_usb_cdc_sim.py`.

#### Défaut de cohérence du reset démontré, correction ciblée

La première lecture de la netlist avait identifié `.SET(reset_i)` sur la
cellule `s_reset_s0` et conclu trop vite à une assertion asynchrone.
**Correction : la primitive Gowin DFFSE possède un SET synchrone**, comme
le montre `prim_sim.v:381`. Sans front de `phy_clk`, `usbrst_o` ne suit donc
pas immédiatement `RESET`. Le pont UART recevait `RESET | usb_busreset`,
les FIFO et la configuration CDC seulement `usb_busreset`.

Le banc `rtl/usb_controller_reset_tb.sv` associe le contrôleur fournisseur
original à une vraie FIFO contenant un octet avant chaque reset. La variante
`LEGACY_RESET` échoue sur l'assertion immédiate. Le reset commun réussit huit
séquences, dont quatre avec horloge arrêtée, sans donnée résiduelle.
C'est une différence de comportement voulue : l'équivalence en phase de
reset n'est pas revendiquée. Hors reset, les signaux de transport sont inchangés.

`console_top.v` distribue désormais `usb_app_reset = RESET | usb_busreset`
aux FIFO, au pont UART, à la configuration CDC et à l'instrumentation.
Les domaines applicatifs concernés sont tous à 60 MHz dans ce top ; les
sources du reset sont libérées sur ce domaine. Les netlists fermées,
les fréquences et les contraintes SDC ne changent pas.

Le build r24 a échoué avant synthèse FPGA : le bac à sable interdisait le
socket AF_NETLINK utilisé pour l'identifiant de licence. Il n'a pas été
chargé. Le build r25 est réalisé hors bac à sable dans un dossier neuf.

| Mesure r25 | Résultat |
|---|---|
| Sources figées vérifiées | 83 |
| Timing | 110 chemins détaillés, minimum **+0,094 ns**, TNS 0 |
| Logique / registres | 31 411 / 23 284 |
| BSRAM / DSP / PRIMARY | 225 / 25 / 8 |
| ITCM binaire / BSS | 57 696 / 28 992 octets |
| SHA-256 bitstream | `71888e73d83ff6a879a3a770ef513200ffbc2393abb64c3726fa088a45320153` |

Chargement SRAM sur ax15, série FTDI **2023112818**, `DONE`, USB **480 Mbit/s**.
Le protocole prévu était trois charges × 100 séries, puis GPU ; il s'arrête
correctement au premier échec : **190/256 octets** dans la première série,
avec suppressions et insertion. La réponse d'identité est également corrompue.
Le test isolé suivant perd son premier `11`, toujours absent après 2,018 s :
la trace montre DATA1, longueur utile 1, quatre octets UTMI et CRC `80b3` ;
FIFO vide, `pending=0`, zéro RXERROR. Le reset commun **ne résout donc pas**
les erreurs USB en fonctionnement. Aucun succès d'endurance ou GPU n'est annoncé.

Journaux : [r25](usb_ax15_20261002/l12_r25_common_reset/result.json) et
`usb_ax15_20261002/l12_r25_isolated/`.

#### Émission du PHY : piste à qualifier, aucun PASS global

`rtl/usb_phy_tx_drift_tb.sv` conduit UTMI et récupère les symboles aux broches
avec une horloge hôte indépendante et une récupération de phase idéale sur
les transitions. Le banc cherche la fin KK de SYNC avant de comparer PID,
charge utile, CRC, bourrage et EOP ; il n'impose pas que l'activation du driver
marque exactement le début du premier bit série.

Les trois couples `(0,0)`, `(+500,-500)`, `(-500,+500)` comparent correctement
les symboles de 16 paquets et 4 398 octets chacun. **Les tests restent en échec** :
le modèle montre une première période K allongée au démarrage et plusieurs
transitions après l'EOP avant retour au repos (environ 6,5 à 10,5 temps de bit
sur ces essais). Ces écarts sont conservés et non neutralisés pour obtenir
un PASS. Il faut qualifier le banc et la compatibilité entre `.vo` 1.9.10.03
et primitives 1.9.12, puis comparer à la carte, avant d'en conclure à une
non-conformité électrique réelle. Ce n'est pas un test USB-IF de conformité.

Résultats : [usb_phy_tx_drift_20261002.json](usb_phy_tx_drift_20261002.json).
Reproduction : même commande que RX, ajouter `--direction tx --quick`.

#### r26 : suivre l'ACK du paquet observé et le retrait FIFO

La trace précédente enregistrait seulement les derniers ACK **antérieurs**
au paquet, ce qui ne permettait pas de trancher le cas de l'octet perdu.
`usb_packet_trace.v` conserve maintenant, pour chacun des quatre derniers
paquets EP2 utiles, les événements qui suivent sa propre émission :
ACK D2 reçu sans RXERROR, validation du contrôleur sur EP2, RXERROR observé,
et état `pending` de la FIFO six cycles après ACK/validation.
Un nouveau paquet coupe l'association afin de ne pas attribuer son ACK
à un paquet antérieur ; les ZLP normaux et NAK restent filtrés.

Le format garde les informations précédentes, la longueur annoncée, le PID
et les deux derniers octets transmis. Le bit 39 marque le nouveau format ;
38 = propre ACK PHY, 37 = propre validation contrôleur, 36 = RXERROR après TX,
35 = échantillon FIFO disponible, 34 = pending à cet instant ; le compte des
octets devient saturant sur 10 bits (33:24). Le décodeur hôte reconnaît les
anciens et nouveaux formats. La requête de contrôle reste `wValue=0xd1a7`.
Le banc vérifie les ACK sans validation, validations sans ACK, pending,
reprises, ACK erronés, ZLP, autres endpoints et resets :
[simulation](usb_packet_transaction_trace_20261002.txt).

Le r26 ne change que cette instrumentation et son raccordement par rapport
au r25, hors netlist AE350 régénérée par le build. Sa validation sur carte
reste à compléter après le contrôle de timing.


Commandes de reproduction locales des nouveaux bancs :

```sh
python3 tools/check_usb_phy_sim.py \
  --iverilog /tmp/console-usb-sim-tools/extracted/usr/bin/iverilog \
  --vvp /tmp/console-usb-sim-tools/extracted/usr/bin/vvp \
  --ivl-root /tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl \
  --jobs 2 --output /tmp/console_usb_phy_rx_recheck.json
python3 tools/check_usb_cdc_sim.py \
  --iverilog /tmp/console-usb-sim-tools/extracted/usr/bin/iverilog \
  --vvp /tmp/console-usb-sim-tools/extracted/usr/bin/vvp \
  --ivl-root /tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl \
  --output /tmp/console_usb_cdc_recheck.json
```

Les chemins du modèle et de la bibliothèque sont surchargeables par
`--reference` et `--primitives`. Les outils refusent de présenter le modèle
comme celui du projet si les netlists de synthèse de référence diffèrent.


### r26 sur carte : acquittement signalé, octet absent côté hôte

Le r26 passe **110 chemins détaillés**, minimum **+0,140 ns**, TNS 0 ;
83 sources figées. Ressources : 31 452 cellules logiques, 23 280 registres,
225 BSRAM, 25 DSP, 8 PRIMARY. Firmware inchangé (ITCM 57 696, BSS 28 992).
SHA-256 : `ac2fde600c00e79b16bc65fc0c0e256fe2f5902b3334d02f47228eb1ea2459b0`.

Chargement SRAM identifié FTDI 2023112818, `DONE`, énumération à 480 Mbit/s.
Le test ordinaire échoue à **250/256 octets**, première série : les essais
supplémentaires et GPU sont donc arrêtés. Ensuite, sur un même descripteur
CDC ouvert, le premier octet isolé `11` passe ; le deuxième `5a` reste absent
après **2,021 s**, sans requête de diagnostic pendant cette attente.

La trace prise **après** l'échec enregistre pour `5a` :

| Observation | Valeur |
|---|---|
| PID présenté au PHY | DATA1 (`4b`) |
| Longueur annoncée / octets UTMI acceptés | 1 / 4 (PID + donnée + CRC) |
| Deux derniers octets UTMI | `c0 84`, CRC16 correspondant à `5a` |
| ACK D2 annoncé par le PHY, sans RXERROR | oui |
| Validation du contrôleur pour ce paquet | oui |
| FIFO encore pending six cycles après ACK/validation | non |
| Compteur global RXERROR | 0 |
| Dernier octet UART / OUT / livré au firmware | `5a` / `5a` / `5a` |

L'octet précédent `11` est enregistré en DATA0, avec son propre ACK, sa
validation et sa FIFO retirée. Les ZLP entre paquets utiles ne sont pas
conservés dans cette histoire, mais participent aux PID des ACK précédents.

**Conclusion limitée aux signaux mesurés** : le retrait de cet octet dans la
FIFO est accompagné d'un ACK vu à l'interface UTMI et d'une validation du
contrôleur. La trace ne soutient pas une simple suppression sans acquittement
par la FIFO. Elle ne prouve pas ce qui a été transmis sur le câble : le PC
peut notamment acquitter un paquet considéré comme une répétition sans le
livrer à l'application, et un défaut du PHY peut aussi fausser le décodage
présenté au contrôleur. Le PID et les octets réellement vus par l'hôte, les
ZLP et le suivi des DATA0/DATA1 restent les prochains éléments à confronter.
Le PHY n'est pas déclaré innocent sur la base de ses propres compteurs.

Journaux : [r26](usb_ax15_20261002/l12_r26_transaction_trace/result.json),
[octet isolé](usb_ax15_20261002/l12_r26_isolated/result.json),
[trace détaillée](usb_ax15_20261002/l12_r26_isolated/diagnostic.txt).

La régression de reset est également reprise avec huit instants d'assertion
explicitement différents dans la période d'horloge :
[contrôleur/reset](usb_controller_reset_20261002.json).


### Réponse LA16 reçue et comparée

Le relevé de l'autre session est effectivement disponible dans
`/home/michael/logic_analyser_wifi/TESTS/USB_INTERSESSIONS_LA16.json`.
Il est lu avec le diff des adaptateurs, les journaux `before.log`/`after.log`
et la preuve d'identité de configuration de l'audit G13. La réponse console,
avec empreinte du fichier lu et réponse aux quatre questions, est déposée
uniquement dans `TESTS/USB_INTERSESSIONS_CONSOLE.json` ; aucun processus,
fichier ou programmateur LA16 n'est modifié.

Le défaut LA16 est plus précisément un reset d'un seul pointeur : l'ancien
compteur de démarrage n'était pas réarmé après reset système. Une commande
entièrement consommée était rejouée ; le correctif tient les deux côtés des
FIFO en reset et masque immédiatement la tête OUT, même horloge arrêtée.
Les journaux montrent FAIL avant, puis 2/2 PASS après. Le correctif LA16
n'est pas encore qualifié sur carte à la date du relevé.

La console partage la famille « reset incohérent », mais pas ce mécanisme
exact : les deux pointeurs applicatifs avaient déjà le même reset, tandis
que le pont UART recevait aussi le reset système immédiat. Le défaut de
console démontré concerne cet intervalle, notamment horloge arrêtée.
Aucune commande rejouée par un reset d'un seul pointeur n'est démontrée ici.

Les 0,822–1,243 ns mesurées sur les premiers trajets Gray du G13 sont
accompagnées d'une preuve de binaire identique. Ce résultat n'est pas
transposable au PHY USB2. Ses premiers trajets ne sont pas mesurés dans
notre audit actuel ; ne pas compter leurs exclusions par groupes asynchrones
comme des PASS. Un audit futur devra conserver la configuration routée et
confronter les délais de données, sans valider les horloges comme synchrones.

Après les essais r25/r26, le **r19 est restauré** par chargement SRAM identifié,
avec vérification de ses 83 sources, SHA et timing +0,140 ns. Il s'énumère à
480 Mbit/s ; le contrôle court échoue encore à 62/64 octets. Cette restauration
rétablit le point de retour antérieur, elle ne valide pas la fiabilité USB.

La commande `Z` est ensuite acceptée : `AFFINE ANIMATION started`. La réponse
est conservée dans `usb_ax15_20261002/l12_r19_restored_after_r26/animation.json`.
Aucune nouvelle confirmation visuelle de l'animation n'est revendiquée.


### Contrôleur fournisseur + FIFO : séquences USB réelles à UTMI

Le nouveau banc `rtl/usb_controller_packet_tb.sv`, lancé par
`tools/check_usb_controller_sim.py`, relie le **modèle original du contrôleur**,
la ROM de descripteurs, la configuration CDC et les FIFO effectives du projet.
Il effectue la négociation High Speed par SE0/chirps, `SET_ADDRESS(7)`, les
2 ms de récupération, puis `SET_CONFIGURATION(1)`. Il injecte des paquets
UTMI avec PID et CRC, et suit les DATA0/DATA1 du côté hôte. Aucun signal
interne n'est forcé ; `usbc_clr_in[2]` et `isync[2]` sont seulement observés.
La netlist fermée et la bibliothèque de primitives restent intactes.

Deux essais du **même banc**, avec les mêmes empreintes RTL :

| Séquence après configuration | Résultat |
|---|---|
| Bulk immédiat (`--bare-config`) | **FAIL** : `11` sort en DATA0 et est acquitté ; FIN est vu et la FIFO avance ; le nouvel octet `5a` sort encore en DATA0. |
| GET_CONFIGURATION supplémentaire, puis bulk | **PASS** : 131 octets exacts, 135 sondages, 69 paquets DATA acceptés, trois retransmissions identiques après ACK volontairement perdu. |

Dans le premier cas, `usbc_clr_in[2]` reste à 1 au moment du FIN et le
numéro de séquence reste à zéro. Dans le deuxième, cet indicateur est à 0
et l'alternance fonctionne. Le balayage couvre 64 délais d'arrivée UART
pendant la décision d'un IN vide ; aucun ZLP EP2 n'est observé dans cette
séquence. Les comparaisons hôte vérifient CRC, contenu, ordre, doublons et
longueurs. Un doublon contenant des données nouvelles fait échouer le test.

Rapports : [bulk immédiatement après configuration](usb_controller_bare_config_20261002.json)
et [bulk après GET_CONFIGURATION](usb_controller_retry_20261002.json).
Le premier conserve son **FAIL**, il n'est pas reclassé en succès.

**Portée :** c'est un comportement défectueux reproductible du modèle dans
une séquence précise, pas encore une preuve sur la carte. Il ne suffit pas
à expliquer la perte r26 après ouverture CDC et diagnostics EP0, qui ont
déjà envoyé d'autres requêtes de contrôle. Le PHY et le câble sont absents
ici ; les entrées UTMI sont synchrones et idéalisées. Ce banc complète les
essais de dérive série du PHY, sans les remplacer. Il n'effectue pas une
énumération hôte exhaustive. Les premières explorations FS n'étaient pas
qualifiées : OpMode était encore non-driving avant la fin de l'attachement.
Les deux rapports finaux concernent exclusivement le HS négocié.

```sh
python3 tools/check_usb_controller_sim.py \
  --iverilog /tmp/console-usb-sim-tools/extracted/usr/bin/iverilog \
  --vvp /tmp/console-usb-sim-tools/extracted/usr/bin/vvp \
  --ivl-root /tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl \
  --output /tmp/console_usb_controller_retry.json
# Ajouter --bare-config pour reproduire l'échec après SET_CONFIGURATION.
```

La comparaison et ses limites sont ajoutées à
`USB_INTERSESSIONS_CONSOLE.json`. Aucun fichier LA16, compilation Gowin ou
chargement sur carte n'est effectué pour cette extension de simulation.
Le r19 restauré reste le dernier bitstream chargé.


### Sélection EP0 → EP2 : ZLP parasite et reprise avec données nouvelles

Le 2 octobre, le banc contrôleur/FIFO est relié au modèle PHY fournisseur
intact, après initialisation et configuration à UTMI. Les transactions de
données passent ensuite réellement par D+/D− dans la simulation. L'hôte
a sa propre grille temporelle ; les horloges carte 60/960 MHz restent cohérentes.
Le banc suit CRC, DATA PID, longueur, ordre et identité des reprises. Aucun
signal interne fournisseur n'est forcé. Le démarrage UTMI signifie que ce
banc **ne valide pas l'énumération physique complète**.

Avec les sources r26, le premier IN sur EP2 vide produit `c3 00 00` :
DATA0, zéro octet, CRC vide. L'hôte l'accepte, mais son ACK est volontairement
perdu. Après arrivée du premier octet UART `11`, la reprise devient
`c3 11 80 b3` : même DATA0, contenu différent. Le banc échoue explicitement
sur `Retry changed payload length, including ZLP: 3 -> 4`. Un hôte ayant
accepté le ZLP peut éliminer la nouvelle donnée comme doublon tout en
l'acquittant. Cela fournit un mécanisme compatible avec une FIFO retirée
après ACK alors que l'application PC n'a pas reçu l'octet ; ce n'est pas
encore la preuve que chaque perte matérielle r26 avait cette cause.

Cause dans le code ouvert : CORK et longueur sont enregistrés pour
`s_endpt_sel`, tandis que le top sélectionne immédiatement l'endpoint
courant. Au passage EP0 → EP2, l'offre EP0 ouverte et de longueur zéro
peut apparaître brièvement sur EP2. La garde de sélection ferme l'offre
tant que les endpoints courant et enregistré diffèrent. Le POP et la
réservation de reprise utilisent aussi cette garde. Les netlists fermées
restent intactes.

Résultats :

- [Avant correction](usb_controller_phy_zlp_before_20261002.json) : FAIL
  reproductible du changement de longueur de la reprise.
- [Après correction, fréquence nominale](usb_controller_phy_endpoint_guard_20261002.json) :
  données PASS, 146 sondages, 131 octets exacts, 80 paquets acceptés,
  14 doublons identiques, zéro ZLP.
- [Hôte +500 ppm / carte −500 ppm](usb_controller_phy_endpoint_guard_fast_host_20261002.json)
  et [hôte −500 ppm / carte +500 ppm](usb_controller_phy_endpoint_guard_slow_host_20261002.json) :
  mêmes résultats fonctionnels, phases initiales respectives 1,113 et 1,891 ns
  (nominal : 0,317 ns).
- [Trois régressions historiques](usb_endpoint_guard_regressions_20261002.json) :
  journaux identiques avant/après, dont 30 000 octets concurrents,
  14 733 tentatives et 3 685 reprises. Comparaison bornée à ces stimuli,
  sans revendication d'équivalence formelle globale.
- [Assertions de transition](usb_endpoint_transition_20261002.json) : FAIL
  avant, PASS après ; vérification entre le changement d'endpoint et le
  front d'horloge suivant, FIFO vide puis contenant des données.

**Limite conservée dans les rapports** : les trois essais série détectent
chacun 147 écarts de forme au début/à la fin des trames produites par le
modèle PHY. Ils portent `payload_pass: true`, mais `pass: false`. Le
décodeur numérique récupère les données ; il n'est pas un instrument de
conformité électrique. Le lien PHY complet n'est pas déclaré validé et
ces anomalies doivent être confrontées à la bibliothèque et au matériel.

Le r27 compile mais est **rejeté au timing, donc non chargé** : minimum
−0,682 ns, 16 endpoints setup en défaut dans le blitter/triangle à 75 MHz,
TNS −3,135 ns. Aucun défaut hold. Firmware 57 696 octets ITCM, 28 992 octets
BSS ; logique 31 447/138 240, registres 23 280/139 140, BSRAM 225/340,
DSP 25/298, PRIMARY 8/8. Aucune fréquence ou contrainte temporelle relâchée.

### Audit physique des FIFO du PHY USB2, configuration r19 identique

`tools/check_usb_phy_cdc_timing.py` extrait du modèle fournisseur les
44 connexions de pointeurs attendues : RX 6 bits × 4 trajets, TX 5 bits ×
4 trajets, y compris les MSB pilotés par `rbin_num`. Chaque trajet source Q
→ destination D doit être présent ; une absence n'est jamais un succès.

Quatre audits isolés repartent de la netlist et du CST résolu r19. Les
deux premiers ne publient que les 22 trajets entre étages ; ils restent
incomplets. Le troisième ajoute des contraintes de délai explicites et
trouve 44 chemins, mais change le binaire : ses mesures ne sont pas
attribuées au r19 chargé. Le quatrième retire les groupes d'horloge
**dans la copie de diagnostic uniquement**, sans `set_max_delay`, puis
demande les 44 trajets explicitement. Il reproduit exactement le `.bin`
r19 : SHA-256 `a2e52769a4abbd4625d71e41259b239f4e89b11091e996f26fe292bbb6b870b4`.

[Rapport complet et preuve d'identité](usb_phy_cdc_r19_no_groups_20261002.json) :

| Trajet | RX (6/6 bits) | TX (5/5 bits) |
|---|---|---|
| Pointeur écriture → premier synchroniseur | 0,844–1,055 ns | 0,844–1,031 ns |
| Premier → deuxième synchroniseur lecture | 0,822–1,053 ns | 0,822–1,031 ns |
| Pointeur lecture → premier synchroniseur | 0,844–1,266 ns | 0,844–1,240 ns |
| Premier → deuxième synchroniseur écriture | 0,822–0,846 ns | 0,822–0,844 ns |

Ces délais de données courts ne révèlent pas une traversée Gray démesurément
longue sur r19. Ils ne prouvent ni l'absence de métastabilité, ni la cohérence
des resets, ni la qualité analogique USB. Le slack calculé entre domaines
déclarés ici synchrones pour diagnostic n'est pas une qualification CDC.
Le SDC de production n'est pas modifié ; aucun bitstream d'audit n'est chargé.

La variante r28 conserve la garde CORK/POP et retire uniquement le mux de
masquage de longueur : une longueur n'est pas une offre tant que CORK est
fermé. Les registres de longueur ne changent pas. Le test contrôleur+PHY
(+500/−500 ppm, phase 1,113 ns) produit un [journal strictement identique
à r27, événements horodatés compris](usb_endpoint_guard_r28_equivalence_20261002.json).
Les nouvelles assertions de sélection passent aussi
([journal](usb_endpoint_transition_r28_20261002.txt)).

Reproduction du défaut ancien avec le banc courant : ajouter
`--serial-phy --rtl-root tang/impl/gpu_l12_diag_r26/source` à la commande
du contrôleur ci-dessus. La FIFO de cet instantané a l'empreinte
`0175385b42710bdd6ebfef675fa43a3b0f18e75b88388458e9e851559926d79c`,
identique à celle du rapport avant correction.

Les entrées de l'audit CDC reproductible sont conservées dans
`usb_phy_cdc_audit_20261002/` (Tcl, SDC de diagnostic, empreintes des
entrées et preuve d'identité). Aucun fichier fermé n'est modifié.

Le r28 est également **non chargé** : un seul endpoint setup reste négatif,
−1,481 ns de `cy0_0_s2` vers `n4856_s/A[7]` (DSP du blitter). La trace
attribue notamment 4,565 ns au trajet de `t_step_16_s3`, placé en R24C108,
vers le groupe arithmétique proche de R40C140. r29 garde exactement le RTL
r28 et rapproche cette LUT en R39C140 par CST ; aucune exception SDC.

#### Acquittements rapides : une limite supplémentaire du modèle PHY

Le test r28 est aussi rejoué avec un ACK après 2 cycles UTMI au lieu de
20, hôte +500 ppm/carte −500 ppm. Il échoue sur la progression : trois
octets produits, un seul livré après le budget de reprises. La trace
montre **14 ACK envoyés**, débutant **36,085 à 37,983 ns** après retour
des lignes à zéro, mais **aucun `d2` remonté à UTMI RX**. Le même DATA0
`11` est retransmis à l'identique ; aucune validation FIN n'est observée
pour ce paquet. Le message historique du banc parle de disparition,
mais cette trace indique un paquet retenu faute d'ACK reçu, pas une preuve
de suppression d'octet par la FIFO.

Rapports : [ACK rapides](usb_controller_phy_fast_ack_r28_20261002.json),
[trace hôte et UTMI](usb_controller_phy_fast_ack_trace_r28_20261002.json).
Cette observation numérique s'ajoute aux écarts de framing. Il faut
qualifier les primitives et le modèle de broches avant d'accuser le PHY
sur carte ; aucun signal interne fournisseur n'a été modifié.

#### r29 : timing réparé, mais pertes matérielles persistantes

Le placement ciblé suffit pour obtenir 110 chemins détaillés tous positifs,
minimum **+0,140 ns**, TNS nul. Le [blitter synthétisé est strictement
identique à r28](usb_r29_blitter_identity_20261002.json). Logique 31 459/138 240,
registres 23 280/139 140, BSRAM 225/340, DSP 25/298, PRIMARY 8/8.
Firmware inchangé : 57 696 octets ITCM, 28 992 BSS.
SHA-256 du bitstream r29 :
`b636bb772ead70c618c3ab34023eb2b584cde82952e6f18c8438d9b14bc0b185`.

Après vérification des 83 sources figées, du SHA et du timing, chargement
**SRAM** sur ax15, FTDI `2023112818`, bus `3:66`. `DONE` obtenu, puis
énumération à **480 Mbit/s**, CDC `11252024`. Le premier lancement du
script n'avait pas le répertoire `bin` du chargeur dans PATH et n'a rien
chargé ; le lancement suivant utilise le wrapper local existant. Aucun
reset d'hôte USB, flash ou programmateur de l'autre projet n'est utilisé.

Le test d'endurance s'arrête au premier tour : **183/256 octets** reçus,
puis identité tronquée (`egaPro… core=00MHz`). Le défaut logique corrigé
ne suffit donc pas à rendre la liaison fiable. Les deuxième et troisième
chargements et le diagnostic GPU final ne sont pas exécutés, conformément
à l'arrêt au premier défaut. Ce build n'est pas archivé comme version validée.
[Rapport matériel](usb_ax15_20261002/l12_r29_endpoint_guard_retry/result.json).

La comparaison d'ACK à 8 cycles échoue aussi : 14 ACK à 136,106–137,962 ns
après fin physique, aucun ACK à UTMI RX
([rapport](usb_controller_phy_ack8_trace_r28_20261002.json)). Une seconde
bibliothèque Gowin locale produit un journal exactement identique pour
les ACK à 2 cycles ; les définitions des primitives utilisées par le PHY
sont identiques dans les deux bibliothèques. Cela exclut une différence
entre ces deux copies comme explication, sans qualifier leur fidélité au
matériel ([rapport](usb_controller_phy_fast_ack_altlib_r28_20261002.json)).

Le diagnostic isolé r29 reproduit ensuite la même perte unitaire que r26 :
`11` reçu puis `5a` absent après 2,022 s. La trace enregistre pour `5a`
DATA1 `4b`, CRC `c084`, longueur annoncée 1, ACK PHY et FIN contrôleur
présents, aucune RXERROR, pending retiré après acquittement.
[Échos isolés](usb_ax15_20261002/l12_r29_isolated/result.json),
[trace](usb_ax15_20261002/l12_r29_isolated/diagnostic.txt).
Le test hôte et cette trace ont fini ; aucun lecteur CDC n'est laissé ouvert.

Ce résultat **ne correspond pas** au blocage des ACK rapides du modèle
(qui ne produisait aucun ACK/FIN). Il faut encore confronter le suivi PID
côté hôte avec tous les DATA, y compris les ZLP légitimes actuellement
filtrés dans l'historique matériel. La correction de transition ne couvre
pas, à elle seule, tout éventuel paquet vide émis dans un autre contexte.
Ne pas traiter ces deux observations différentes comme une cause commune
démontrée. Le r29 reste chargé pour poursuivre ce diagnostic ; aucun
bitstream de ce travail n'est promu comme version USB fiable.

#### Audit CDC du r29 effectivement chargé

Le même audit est repris sur la netlist r29 : **44/44 trajets présents** et
`.bin` strictement identique au r29 chargé. Délais de données compris entre
**0,822 et 1,483 ns**. [Rapport et identité de configuration](usb_phy_cdc_r29_20261002.json),
entrées reproductibles dans `usb_phy_cdc_audit_r29_20261002/`.

| Trajet | RX (6/6 bits) | TX (5/5 bits) |
|---|---|---|
| Pointeur écriture → premier synchroniseur | 0,844–1,483 ns | 0,844–1,055 ns |
| Premier → deuxième synchroniseur lecture | 0,822–1,034 ns | 0,822–1,091 ns |
| Pointeur lecture → premier synchroniseur | 0,844–1,243 ns | 0,844–1,053 ns |
| Premier → deuxième synchroniseur écriture | 0,822–0,844 ns | 0,822–0,844 ns |

Même limite que r19 : ces trajets courts ne constituent pas une preuve
d'absence de métastabilité, une qualification de reset ou de conformité
USB. Le SDC de production reste inchangé. Les observations du modèle
réception (rx_en et état) sont conservées dans
[la trace en lecture seule](usb_controller_phy_fast_ack_rxenable_r28_20261002.json).
Le bus de compteur observé possède des bits non pilotés dans ce modèle
synthétisé : son affichage `Z` n'est pas interprété comme un état matériel.


### Suite du 2 octobre : contexte ZLP, trafic dans les deux sens et démarrage

#### Couverture supplémentaire du contrôleur

Le banc `usb_controller_packet_tb.sv` peut maintenant intercaler des commandes
OUT EP2 `45 01 00 xx` entre les lectures IN, y compris lorsqu'un ancien IN
attend encore son ACK. Le PID OUT alterne indépendamment du PID IN. La
production UART reste un stimulus du banc : ce test ne simule pas le CPU.
Le délai SET_ADDRESS est exprimé en temps absolu (au moins 2 ms), afin de
rester valide avec les variations de fréquence.

- UTMI idéal : **PASS**, 131 octets produits/livrés, 135 IN, 69 DATA acceptés,
  3 reprises identiques, zéro ZLP.
  [Rapport](usb_controller_utmi_in_out_r29_20261002.json).
- Contrôleur + PHY originaux, trafic D+/D− après initialisation UTMI :
  131 octets exacts, 146 IN, 80 DATA acceptés, 14 reprises identiques,
  zéro ZLP. **278 écarts de framing** restent détectés pour 277 réponses
  physiques (les ACK OUT sont désormais inclus). `payload_pass=true`,
  mais **`pass=false`**, conformément aux limites précédentes du modèle.
  [Rapport](usb_controller_phy_in_out_r29_20261002.json).

Ces séquences ne reproduisent pas la perte matérielle. Elles ne couvrent
pas un ordonnanceur hôte complet, toutes les requêtes CDC, ni le timing
électrique. Aucun résultat global PHY PASS n'est revendiqué.

#### Diagnostic r30 : mémoriser aussi les paquets vides

L'ancien enregistreur éliminait les ZLP légitimes. Le nouveau conserve
les trois tentatives DATA immédiatement antérieures au dernier paquet
utile, même vides, avec leurs ACK/FIN. L'instantané reste figé pendant
les sondages à vide ultérieurs. Interface de lecture et format 64 bits
inchangés ; trois enregistrements internes supplémentaires.

Le contrôle négatif échoue avec l'ancien RTL ; le nouveau passe les cas
ACK perdu, FIN, RXERROR, pauses TXREADY, reset et douze ZLP successifs qui
ne doivent pas effacer l'instantané. Voir
[avant](usb_packet_context_before_20261002.txt) et
[après](usb_packet_context_after_20261002.txt).
Il s'agit d'une modification du diagnostic passif, sans correction
supplémentaire du transport USB.

`gpu_l12_diag_r30` : 83 sources figées, 110 chemins détaillés,
slack minimal **+0,140 ns**, TNS nul. SHA-256 :
`f0326e6463cdc570400494e9d55d2a06f5de58c5e1ca8a1c7326d12f9ae04de6`.
Ressources globales : 31 804 cellules logiques, 23 502 registres,
225 BSRAM, 25 DSP, 8/8 PRIMARY ; firmware inchangé de 57 696 octets.
SDC de production inchangé.

Deux chargements SRAM sur FTDI `2023112818`, ax15, énumération à 480 Mbit/s,
mais aucune réponse d'identification. Le premier diagnostic EP0 retourne
EPROTO ; après le deuxième chargement, les contrôles EP0 fonctionnent et
les compteurs montrent **8 octets OUT reçus/livrés, zéro octet UART, zéro
DATA EP2 enregistré**. Cela ne prouve pas une nouvelle perte après émission :
aucune réponse UART n'est observée dans ce cas. Le démarrage CPU/DDR ou
le pont doit être distingué du défaut USB étudié.

Journaux :
[chargement 1](usb_ax15_20261002/l12_r30_packet_context/result.json),
[isolé 1](usb_ax15_20261002/l12_r30_isolated/result.json),
[chargement 2](usb_ax15_20261002/l12_r30_packet_context_reload2/result.json),
[compteurs](usb_ax15_20261002/l12_r30_packet_context_reload2/counter_probe.txt),
[isolé 2](usb_ax15_20261002/l12_r30_isolated_reload2/diagnostic.txt).

Le **r29 témoin rechargé ensuite** répond immédiatement aux commandes :
61/64 octets au premier tour, puis octet isolé `11` absent malgré DATA1,
CRC `80b3`, ACK PHY et FIN. Ce témoin retrouve le défaut initial, alors que
le r30 n'a pas fourni de réponse UART.
[Comparaison sur carte](usb_ax15_20261002/l12_r29_control_after_r30/result.json),
[trace](usb_ax15_20261002/l12_r29_control_after_r30/isolated/diagnostic.txt).
Les deux builds ne diffèrent dans leurs sources figées que par le traceur
et la netlist AE350 régénérée ; firmware `.bin`/`.elf` identiques. Cette
comparaison n'est pas une preuve d'identité physique après placement.
Aucun de ces essais n'est archivé comme version validée.

#### Autres traversées internes du PHY

La lecture du rapport CDC r29 contient aussi 19 chemins entre domaines,
hors pointeurs Gray : IDES/commande RX/linestate, délais de données de
1,714 à 4,898 ns. La couverture du rapport est limitée (un chemin commun
par paire), donc ce relevé **n'est pas un inventaire exhaustif ni une
validation CDC**. Les horloges locales proviennent de la même PLL ; la
relation réelle de phase et les commandes doivent également être étudiées.
[Relevé et limites](usb_phy_other_cdc_r29_20261002.json).


#### Réduction du diagnostic après refus de timing

Le r31 ajoute une observation synchronisée de quatre états lents de la
carte dans les bits auparavant nuls du mot de statut :
`[31] PLL AE350 lock`, `[30] DDR_STOP`, `[29] DDR_LOCK`, `[28] reset CPU libéré`.
Deux registres USB successifs par bit, observation uniquement. Le script
hôte affiche le nibble brut ; sur les anciens builds ces quatre bits sont
nuls et **ne constituent pas un état de carte valide**.

Build r31 **refusé et non chargé** : 117 endpoints setup en violation
(116 GPU, 1 USB), pire slack −3,852 ns, TNS GPU −199,980 ns et USB −0,528 ns.
Aucun changement des fréquences ni du SDC.

Le r32 réduit l'enregistreur : dernier DATA utile + **une seule tentative
DATA précédente**, vide ou non, au lieu de trois. Les deux mots supérieurs
de l'interface de 256 bits restent nuls/invalides. Cela conserve la preuve
nécessaire d'un ZLP immédiatement suivi d'un contenu nouveau avec le même
PID et réduit de 256 bits l'état historique par rapport au r30/r31.
La fenêtre est plus courte : elle ne permet pas de reconstruire une longue
séquence. Les champs de chaque enregistrement gardent le même format.
[Banc du traceur réduit](usb_packet_context_r32_20261002.txt) : PASS,
notamment prédécesseur ZLP avec/sans ACK et rétention pendant douze ZLP.

#### Qualification des essais avec SOF

L'allongement du banc UTMI idéal a révélé un artefact de son stimulus :
`boot_PHY_LINESTATE` restait SE0 même pendant les paquets. Après environ
3 ms de SE0 continu, le contrôleur déclenchait une nouvelle détection de
reset. Ce résultat n'est **pas attribué au matériel** :
[essai préliminaire invalide](usb_controller_utmi_sof_context_20261002.json).
Le faux PHY signale désormais une activité de ligne pendant RXACTIVE.
[Contrôle corrigé](usb_controller_utmi_sof_linestate_20261002.json) :
131 octets exacts, sans reset supplémentaire ; essai encore préliminaire
car son compteur de trame était incrémenté à chaque SOF.

Le stimulus final place les SOF sur une grille de 125 µs et calcule le
numéro de trame par période de 1 ms, conformément à la section 8.4.3.1 de
la [spécification USB 2.0](https://www.pjrc.com/teensy/beta/usb20.pdf).
L'injection reste limitée aux contextes étudiés, entre les transactions ;
ce n'est pas un ordonnanceur USB hôte complet. Les rapports finaux portent
le suffixe `sof_grid_20261002`.


Résultats du stimulus SOF final :
[UTMI idéal](usb_controller_utmi_sof_grid_20261002.json) **PASS**,
131 octets, 135 IN, 69 DATA acceptés, 3 reprises identiques, zéro ZLP.
[PHY original](usb_controller_phy_sof_grid_20261002.json), hôte +500 ppm,
carte −500 ppm, phase hôte 0,173 ns : 131 octets exacts, 146 IN,
80 DATA acceptés, 14 reprises identiques, zéro ZLP ; **278 écarts de framing**
maintiennent l'échec global. Les SOF et le trafic dans les deux directions
ne reproduisent donc pas la perte dans ces séquences bornées.


Le build r32 est également **refusé/non chargé** : 29 endpoints setup GPU,
TNS −18,549 ns, pire slack −2,885 ns ; aucune violation setup/hold du domaine
USB. Réduire la trace ne suffit donc pas à fermer le timing du design complet.

#### Variante d'isolation avec processeur et DDR conservés

`tools/build_gpu.py --usb-diagnostic` sélectionne maintenant
`console_usb_diag.v` : même `console_top.v`, mêmes USB/FIFO/reset/pont UART,
même firmware, AE350 800 MHz et DDR conservés. Seul le GPU est remplacé
par la branche historique `lcd_timing` (mire 800×480, 35 MHz).
Le jeu et les commandes graphiques ne fonctionnent pas dans cette variante.
La chaîne d'identité firmware est conservée ; elle ne prouve donc pas la
présence du GPU. N'utiliser que `?`, `X`, `E` et les diagnostics EP0.

Le SDC est strictement inchangé, les contraintes électriques et le brochage
sont identiques. Les placements de cellules du design graphique sont
retirés **dans la copie propre à cette variante uniquement** ; leur
suppression change aussi le placement USB. Un succès ne prouverait pas
que le GPU cause le défaut, et un échec ne prouverait pas à lui seul un
unique défaut logique indépendant du placement.

Le build `gpu_usb_isolation_r1` s'est arrêté en synthèse : le fichier de
mire n'était pas ajouté par le générateur. Corrigé dans le script ; nouveau
build `gpu_usb_isolation_r2`, avec 86 sources figées. Contrôle préalable :
SHA des sources exacts, firmware `.bin` identique au r29, IO_LOC/IO_PORT
identiques, SDC de production inchangé.

`check_gpu_reloads.py --usb-only` distingue explicitement cette portée dans
son JSON et n'exécute aucune commande graphique. Le mode est obligatoire
si `usb_diagnostic.json` annonce un GPU désactivé. Les contrôles de SHA,
sources, timing, carte ciblée, SRAM et vitesse USB restent actifs.


#### Résultats sur carte sans GPU : duplication après l'UART confirmée

`gpu_usb_isolation_r2`, SHA
`afc80e57ebe1dfc18befee5b72c0194125da987494dda8d942ba6df21c6b4e11`,
110 chemins détaillés, marge minimale +0,140 ns, 480 Mbit/s sur ax15.
Le premier tour échoue à 64 octets : longueur reçue 64, mais insertions
et suppressions. La chaîne d'identité montre aussi des doublons.
[Chargement et test](usb_ax15_20261002/usb_isolation_r2/result.json).

L'essai isolé ordinaire reçoit correctement `11`, `5a`, `a3`, `ec`, puis
**`3535` pour un seul `35` attendu**. Les deux derniers DATA UTMI sont
DATA0 (`c3`), longueur un octet, CRC `80a8` ; le premier sans ACK/FIN,
le suivant avec ACK/FIN. Aucun ZLP dans ces deux enregistrements.
[Résultat](usb_ax15_20261002/usb_isolation_r2/isolated/result.json),
[trace](usb_ax15_20261002/usb_isolation_r2/isolated/diagnostic.txt).

Un mode de mesure `check_usb_isolated.py --trace-each` lit les compteurs
EP0 **avant** chaque écho. Ce mode change le contexte des endpoints et
n'est pas présenté comme un test d'endurance CDC ordinaire. Il confirme
un doublon `5a5a` avec les variations suivantes :

| Compteur | Avant | Après | Écart |
|---|---:|---:|---:|
| Octets UART reçus par le FPGA | 201 | 202 | **1** |
| Octets USB OUT reçus | 108 | 112 | 4 |
| Octets OUT livrés au pont | 98 | 102 | 4 |
| POP contrôleur | 268 | 273 | 5 |
| FIN/ACK contrôleur | 200 | 201 | 1 |

Une seule commande de quatre octets est livrée au pont et un seul octet
revient de l'UART ; deux copies parviennent à l'application hôte. La
duplication est donc **en aval de la réception UART dans le FPGA** pour
cet essai. Ce n'est pas une double production du firmware.
[Avant/après](usb_ax15_20261002/usb_isolation_r2/counter_each/result.json),
[trace](usb_ax15_20261002/usb_isolation_r2/counter_each/diagnostic.txt).
Le statut carte vaut `0xf` (PLL verrouillée, DDR_STOP=1, DDR_LOCK=1,
reset CPU libéré) ; il décrit un état lent échantillonné, pas une preuve
complète de timing du SoC.

#### Trace étendue sur la variante d'isolation

L'historique à quatre enregistrements du r30 est rétabli dans les sources
pour `gpu_usb_isolation_r3` : la réduction du r32 n'est pas retenue.
Le banc enrichi conserve le test d'un prédécesseur ZLP acquitté :
[PASS](usb_packet_context_isolation_r3_20261002.txt).

Build r3 : 86 sources, 110 chemins détaillés, marge minimale **+0,139 ns**,
SHA `44fd64c99750c55c04e3fa5d294a3f75c9f1102cffd5c5c3d86eb56fd934b034`.
Chargé en SRAM sur la même carte, 480 Mbit/s. Le premier tour présente
encore des doublons/suppressions, dont la chaîne d'identité altérée.
[Rapport](usb_ax15_20261002/usb_isolation_r3/result.json).

Le premier `11` isolé manque ; compteurs UART 195→196, OUT et livré
74→78, POP 315→319, FIN 187→188. Les quatre dernières tentatives sont
toutes DATA1 (`4b`), longueur 1, CRC `80b3`, sans RXERROR ; aucune trace
ZLP dans cette fenêtre. Les trois premières n'ont ni ACK ni FIN, la
dernière a les deux et retire la FIFO. La fenêtre est bornée : elle ne
reconstitue pas tout l'historique PID précédent, ni le signal sur le câble.
[Compteurs](usb_ax15_20261002/usb_isolation_r3/counter_each/result.json),
[paquets](usb_ax15_20261002/usb_isolation_r3/counter_each/diagnostic.txt).

Enfin, **sans le pilote série**, usbfs direct reçoit les 30 premiers octets
attendus, puis signale EPROTO (-71) à l'index 29 (octet `56` déjà reçu).
La FIFO garde alors le paquet pending : quatre reprises DATA1 CRC `c081`,
sans ACK PHY/FIN ; zéro retour IN de longueur nulle dans le journal hôte.
Le pilote `cdc_acm` est rattaché correctement à la sortie du test.
[USB direct](usb_ax15_20261002/usb_isolation_r3/direct_bulk/result.json),
[trace](usb_ax15_20261002/usb_isolation_r3/direct_bulk/diagnostic.txt).

Ces résultats localisent les anomalies après l'UART et démontrent qu'elles
existent aussi dans la variante sans GPU. Ils ne prouvent pas encore si
le PID/CRC sur le câble correspond aux données UTMI, ni qu'une seule
cause explique pertes, doublons et ACK manquants. Le modèle de PHY et
les traversées physiques restent à qualifier. Aucun correctif global ni
aucun bitstream USB fiable n'est annoncé à ce stade.


#### Notifications CDC et vérification des octets OUT en simulation

Le descripteur utilise **EP3 / 0x83** pour les notifications, EP2 pour les
données. Les premiers essais `*_notifications_20261002.json` avaient sondé
EP1 (non configuré) : ils sont conservés comme essais préliminaires et ne
valident pas les notifications CDC. Le banc physique y avait aussi traité
un NAK OUT comme une erreur immédiate, au lieu de retenter la transaction.

Le banc final sonde EP3, accepte un NAK OUT avec reprise bornée du même
PID/contenu et vérifie **tous les octets sortant de la FIFO OUT**, une seule
fois, en plus du flux IN déjà contrôlé. Résultats :

- [UTMI idéal](usb_controller_utmi_ep3_out_checked_20261002.json) :
  PASS, 524/524 octets OUT, 131/131 IN, 3 reprises IN identiques.
- [Contrôleur et PHY originaux](usb_controller_phy_ep3_out_checked_20261002.json) :
  524/524 OUT, 131/131 IN, 14 reprises IN identiques, 343 réponses filaires
  numériques ; zéro ZLP et zéro NAK OUT dans cette séquence finale.
  **344 écarts de framing**, donc `payload_pass=true` et **`pass=false`**.

Ces essais n'établissent pas une reproduction simulée du doublon matériel.
Aucune netlist fournisseur n'a été modifiée.

#### État de la carte à la fin de cette investigation

Le r29 graphique complet a été rechargé en SRAM, SHA et 83 sources vérifiés,
480 Mbit/s ; le contrôle USB court échoue encore. La commande `Z` a ensuite
renvoyé `AFFINE ANIMATION started`. Aucune nouvelle confirmation visuelle
n'a été demandée et la suite de validation GPU n'a pas été exécutée.
[Rechargement](usb_ax15_20261002/l12_r29_restored_after_isolation/result.json),
[commande d'animation](usb_ax15_20261002/l12_r29_restored_after_isolation/animation.txt).
Les lecteurs CDC sont fermés ; les builds et simulations de ce lot sont
terminés. Aucune version expérimentale n'est promue dans `bitstreams/`.


### Revue croisée demandée le 2 octobre 2026

L'utilisateur demande un avis Claude et plusieurs regards indépendants. Deux
revues locales ont porté sur le protocole et sur le PHY/les horloges. Claude
CLI est lancé avec seulement `Read,Grep,Glob`, sans écriture ni accès carte.
Son premier appel confiné échoue explicitement par DNS `ENOTFOUND` ; la
consultation est relancée avec accès réseau autorisé. La demande exacte est
conservée dans `usb_claude_review_request_20261002.txt`.

La revue du protocole ne trouve pas de double lecture Python et confirme une
lacune de la trace r2 : cinq POP pour une FIN, mais seulement deux DATA
conservés. Les deux derniers PID identiques ne prouvent pas l'identité des
premières tentatives. Elle relève aussi le `full` ignoré dans `usb_tx_buf` :
un arrêt prolongé de l'hôte peut saturer la FIFO de paquets et perdre des
octets. Ce cas ne correspond pas aux échos isolés avec `available=0`.

#### Fenêtre de retour RX du modèle original

[Sept simulations et synthèse](usb_controller_localphase_review_20261002.json).
Le nouveau paramètre `--local-phase-ns` sépare la phase locale 960 MHz de
celle de l'horloge 60 MHz tout en gardant leur rapport exact. Les phases
0 ; 0,260417 ; 0,520833 ns ont été testées ; 4,166667 ns est redondant en
régime permanent. Les variations de fréquence hôte/carte restent distinctes.

Le modèle RX reste en état `01` jusqu'à `q_tx_cnt=24`, puis revient `00`
227,60 à 228,39 ns après la fin électrique du paquet. Chaque essai ACK court
émet quatorze ACK à 36–37 ns : aucun n'atteint UTMI. Avec ACK à 336–337 ns,
131 octets IN et 524 OUT sont exacts, quatorze reprises sont identiques et
aucun ZLP n'apparaît. Les 344 différences de framing TX maintiennent toutefois
`pass=false` : ce modèle numérique n'est pas une qualification du silicium.
Aucun signal fournisseur n'est forcé et aucune netlist n'est modifiée.

Le banc émettait aussi un EOP SOF de huit bits : il utilise désormais les
quarante bits requis. Les ACK courts sont autorisés par EL_22 (8–192 bits
en réponse à un paquet reçu) ; EL_23 (88–192 bits) concerne deux émissions
hôte consécutives. [Document USB-IF](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification(v1.07).pdf).

#### Contrôles CDC et sondes privées reproduits

Le banc `--cdc-context` rejoue SET_LINE_CODING 115200/8N1,
SET_CONTROL_LINE_STATE, GET_LINE_CODING et les requêtes privées exactes
`0xa0/0x21/d1a6` et `d1a7`. Les données de diagnostic sont une rampe fixe :
chaque octet et CRC est vérifié, mais ce n'est pas une simulation des
compteurs vivants du top. Des contrôles sont insérés pendant les reprises.

- [UTMI r3 sans GET_CONFIGURATION](usb_controller_cdc_utmi_bare_r3_20261002.json) :
  PASS, 133 contrôles dont trois pendant pending, 131 IN / 524 OUT exacts.
- [PHY nominal r3](usb_controller_cdc_phy_nominal_r3_20261002.json) et
  [hôte +500 / carte −500 ppm](usb_controller_cdc_phy_r3_20261002.json) :
  133 contrôles dont quatorze pendant pending, 131 IN / 524 OUT exacts,
  quatorze reprises identiques, zéro ZLP. 131 NAK OUT suivis de reprises
  correctes. `payload_pass=true`, `pass=false` à cause de 879 écarts framing.

Les contrôles ne changent ni le PID ni la longueur du paquet EP2 pending.
Les requêtes CDC effacent normalement `usbc_clr_in[2]`, même sans le
GET_CONFIGURATION de l'ancien bootstrap. Le cas « bare config » n'explique
donc pas ces séquences. Tous les rapports finaux portent
`sources_unchanged=true`. Les lots antérieurs restent conservés comme
préliminaires : constante diagnostic déclarée trop tard/tronquée à un bit,
puis espacement token→DATA de huit cycles trop court. Le lot r3 utilise
douze cycles (environ 200 ns).

#### Régénération officielle du PHY, essai matériel

`tools/build_gpu.py --usb-diagnostic --usb-phy gowin` utilise les fichiers
fournisseur de Gowin 1.9.12 / générateur PHY 3.4, sans modification, avec
les macros de la référence : UTMI, GW5AT, TX_DELAY_0_BIT. Le contrôleur,
les PLL, les broches et le SDC restent identiques. La variante est limitée
au diagnostic sans GPU ; la source de référence n'est pas remplacée.
Le guide officiel récent est [IPUG781-1.7E](https://www.gowinsemi.com/upload/database_doc/2125/document/687a7263eb932.pdf).
Il ne constitue pas une annonce de correction de la fenêtre RX observée.

`gpu_usb_phy34_r1` échoue dans le sandbox sur l'identification réseau de
licence ; aucune synthèse complète ni charge. `gpu_usb_phy34_r2`, lancé
avec l'autorisation existante, termine : 91 sources figées, 110 chemins,
marge minimale +0,139 ns, contraintes actives, SHA-256 du bitstream
`351bccf96b0173aeec22a3f69fc488b9d555a4a910284cd2d3551200990226b7`.
Chargement SRAM de FTDI2023112818 réussi ; SOFT-USB direct 3-7 à 480 Mbit/s.

Le test de 64 octets reçoit une longueur64 mais deux insertions et deux
suppressions, puis une identité corrompue. La sonde intrusive passe 25 échos
unitaires avant un EPROTO−71 sur lecture de contrôle ; aucune conclusion
sur le prochain écho, qui n'a pas été envoyé. Ce PHY régénéré ne répare
pas la panne. [Preuves](usb_ax15_20261002/usb_phy34_r2/result.json).
Il n'est pas archivé comme bitstream validé. La variante mire reste chargée
à ce point de l'investigation ; l'état final sera précisé après les essais.


#### Avis Claude reçu et confrontation aux nouvelles preuves

[Avis intégral](usb_claude_review_20261002.md), réponse API sans erreur en
445,651 s ; lecture seule. Il ne conclut pas à une cause racine prouvée.
Ses trois pistes : CDC/phase interne du PHY, retour RX tardif, puis
récupération xHCI comme mécanisme possible de désynchronisation des PID.
La réserve sur l'absence de balayage de phase est devenue partiellement
obsolète avec les essais locaux ci-dessus ; ces essais numériques ne
prouvent toujours pas le setup/hold des chemins physiques.

Le noyau d'ax15 est `6.17.0-35-generic`. Dans le code amont Linux v6.17,
`process_bulk_intr_td` tente des resets préservant l'état après erreur de
transaction ; après sa limite, `finish_td` peut demander un reset dur.
`xhci_queue_reset_ep` ne pose TSP que pour un reset souple. Les réussites
`COMP_SHORT_PACKET` ne remettent pas `err_count` à zéro dans cette fonction,
contrairement à `COMP_SUCCESS`. Cette lecture précise l'avis Claude : un
reset du toggle n'arrive pas nécessairement à la troisième erreur physique.
[Source primaire Linux v6.17](https://github.com/torvalds/linux/blob/v6.17/drivers/usb/host/xhci-ring.c).

L'avis prédit surtout doubles livraisons DATA0 et pertes DATA1 ; plusieurs
captures concordent, une capture historique r15 non. **Aucun événement de
reset xHCI n'est encore capturé sur ax15 : hypothèse, pas preuve.** Le compte
michael ne peut pas lire/configurer tracefs et `sudo -n` exige un mot de
passe. Un outil de capture borné et isolé est préparé avant de solliciter
une intervention utilisateur ; aucun réglage global du noyau n'a été changé.

Le modèle de simulation PHY3.4 a été obtenu par le flux officiel P&R avec
`set_option -gen_verilog_sim_netlist 1`, depuis la netlist r2 inchangée.
Ce n'est pas le modèle SDF du bitstream console chargé. Son attente RX
reste de 24 cycles : retour IDLE 235,938 ns après EOP ; les 14 ACK à 44,588 ns sont
ignorés. À 344,589 ns,131 octets IN exacts et 14 reprises,0 ZLP ;152 écarts framing
interdisent encore le PASS global. Rapports `usb_controller_phy34_ack2_r2_20261002.json`
et `usb_controller_phy34_ack20_r2_20261002.json`. Les premières compilations
sans suffixe _r2 échouaient sur un alias d'observation renommé ; correction
du banc seulement pour lire Q du même registre, aucune netlist modifiée.


#### Première tentative capturée sur carte : doublon confirmé

Mode passif `CAPTURE_FIRST=1`, impulsion de publication exactement définie
par `endpt_sel==2 && !usb_txpktfin && fifo_diagnostic[24] &&
!fifo_diagnostic[27]`. Le mode par défaut est inchangé au cycle près.
[Test positif, équivalence et témoin négatif](usb_packet_first_publication_20261002.json).
La première tentative conserve ses propres indicateurs ACK/FIN, même si
une reprise ultérieure est finalement acquittée.

`gpu_usb_first_r1` est refusé : reset contrôleur → FIFO RX, −1,807 ns,
trois endpoints fautifs. Aucune charge. `r2` est refusé au placement :
R55C135 indisponible. `r3` fixe seulement le OU `usb_app_reset_s0` sur une
case logique attestée R45C136[0][B] dans le CST de diagnostic ; aucun
assouplissement du SDC. PASS : 110 chemins, marge minimale +0,189 ns,
88 sources figées, SHA-256
`0fb372e25ee53394d7014634de530033a4e75d010e17848914bcb0df7e203e4a`.
Le PHY de référence est conservé pour cet essai.

Chargement SRAM réussi, série FTDI2023112818 ; USB 480 Mbit/s sur 3-7.
Le stress échoue à 64 octets avec trois insertions et trois suppressions.
Puis le diagnostic avec compteurs avant chaque écho reproduit `5a5a` pour
la seule commande `E01005a` (index 1), inchangé après une seconde de grâce.
UART 196→197 ; OUT 78→82 ; livrés 78→82 ; POP 293→298 ; FIN 196→197.

La **première** tentative est DATA0 (`c3`), quatre octets UTMI
(PID + charge 1 + CRC 2), CRC `c084`, sans ACK ni FIN vus par le FPGA.
Ses prédécesseurs immédiats sont DATA1/CRC 80b3 (écho 11), DATA0/CRC 817a,
DATA1/CRC c0b8, tous acquittés et retirés. Aucun ZLP dans cette fenêtre.
L'alternance au début du paquet est donc correcte dans cette observation.
Cinq POP indiquent des reprises, mais elles ne remplacent plus la première
capture. Les compteurs finaux montrent une FIN et pending 0 ; les marqueurs
ACK/FIN nuls du premier essai sont donc attendus et ne contredisent pas
l'acquittement d'une tentative ultérieure.

[Résultat de charge](usb_ax15_20261002/usb_first_r3/result.json),
[écho et compteurs](usb_ax15_20261002/usb_first_r3/counter_each/result.json),
[première tentative](usb_ax15_20261002/usb_first_r3/counter_each/diagnostic.txt).
Ce résultat resserre l'investigation sur les ACK/reprises et la récupération
hôte ; il ne mesure toujours pas les PID électriques ni un reset xHCI.

L'outil `tools/check_usb_xhci.py` est copié sur ax15, self-test réussi sur
les deux PC. SHA-256 après durcissement du nettoyage en cas de processus
bloqué : `6a55116b7b7341c5153bf129d03272ec88bd73f0ec38e77fc0fc3a0b4fa0988f`.
Il crée une instance tracefs privée, lit seulement les événements choisis,
exécute les échos sous SUDO_UID, conserve les formats et restaure son état.
La durée utile est bornée à 30 s, nettoyage en plus. Aucun reset USB, aucune
charge FPGA, aucun montage ni changement global du noyau. Certains événements
TRB/reset ne portent pas l'identité du contrôleur ; cette limite est conservée.
Le 2 octobre, une demande utilisateur est envoyée pour lancer la commande sudo,
le compte distant ne permettant pas ce privilège sans authentification.
La carte reste alors sur la mire de diagnostic r3, au repos, tous lecteurs
CDC fermés. Elle n'est pas promue comme version réparée.

#### Audit des huit relations de phase possibles et séquence de démarrage

`tools/check_usb_phy_phase_timing.py` analyse une copie du routage r29.
Le binaire de configuration produit est **identique** à la référence :
`97e5fb5985cb6f156deac2565a2e0455d9e2831ed2b04084f3af43fb0f80b7dc`.
Seule la copie de diagnostic du SDC enlève les groupes asynchrones internes
du PHY et définit huit horloges alternatives 960/8, espacées de 45 degrés
à 120 MHz. Le SDC de production et le bitstream chargé ne sont pas modifiés.
[Rapport détaillé](usb_phy_phase_r29_20261002.json).

Les chemins hors premiers étages des pointeurs Gray donnent les minima
suivants. Les valeurs sont les résultats STA de relations **hypothétiques**,
pas huit phases observées sur carte.

| Phase 120 MHz | Décalage (ns) | Setup minimal (ns) | Hold minimal (ns) |
|---|---:|---:|---:|
| 0 | 0,000 | +2,983 | +0,736 |
| 1 | 1,042 | −3,200 | +2,071 |
| 2 | 2,083 | −2,159 | +3,113 |
| 3 | 3,125 | −1,117 | +4,154 |
| 4 | 4,167 | −1,184 | +4,903 |
| 5 | 5,208 | −2,226 | +3,861 |
| 6 | 6,250 | −3,267 | +2,819 |
| 7 | 7,292 | −4,309 | +1,778 |

Chaque phase couvre 80 paires source/destination distinctes en setup et
84 en hold. Les 19 paires du précédent audit sont couvertes en setup ;
en hold, 16 paires identiques mais les 19 destinations sont couvertes,
l'analyse choisissant parfois une autre source plus rapide. Les 22 paires
des premiers synchroniseurs Gray sont rapportées séparément ; leur marge
synchrone ne qualifie pas la FIFO asynchrone. Aucun plafond de 20 000 chemins
n'est atteint. Il reste nécessaire de justifier la relation d'horloge réelle
et les éventuels protocoles qui rendent certaines transitions inobservables.
Ces résultats ne prouvent pas à eux seuls une violation fonctionnelle.

Le banc [usb_phy_startup_tb.sv](rtl/usb_phy_startup_tb.sv) observe ensuite le
modèle fournisseur intact, sans contrôleur, paquet ni `force`. Quatre phases
locales sont simulées pendant 22,1 µs chacune, avec deux séquences de reset.
[Résultat et empreintes](usb_phy_startup_r1_20261002.json).

Le séquenceur active la calibration à 358,333 ns, demande l'arrêt HCLK à
758,333 ns, libère le reset du CLKDIV à 1 291,667 ns **pendant que HCLK est
arrêté**, puis demande sa reprise à 2 358,333 ns. DHCE échantillonne la
reprise sur quatre fronts descendants ; le premier front sclk suit le
deuxième front HCLK repris. La phase est donc reconstruite par cette
séquence : l'hypothèse d'un diviseur libre dont le reset choisirait au hasard
une des huit phases n'est pas établie.

Avec les fronts montants idéaux 60/960 MHz alignés, le modèle place sclk
environ 5,209 ns après clk60, modulo 8,333 ns. Ce banc n'intègre ni la PLL
réelle, ni les retards d'insertion/routage, ni SDF, ni métastabilité. Ce nombre
ne sélectionne donc pas automatiquement la phase 5 du rapport STA et ne
mesure pas l'alignement du bitstream sur la carte. Il confirme une question
de conception à lever, sans constituer un correctif validé.

#### Capture xHCI utilisateur : reset du toggle entre les deux livraisons

L'utilisateur exécute l'outil sur ax15 le 2 octobre à 16:00:51 locale.
`status=completed`, sous-processus 1, aucun échec de nettoyage : le statut 1
vient d'un **écho incorrect**, pas d'une panne du collecteur. Tous les fichiers
sont récupérés dans [usb_xhci_20261002_160051_866672](usb_xhci_20261002_160051_866672).
Le script exact utilisé est conservé sous `capture_tool.py` avec son empreinte
dans [analysis.json](usb_xhci_20261002_160051_866672/analysis.json).

La carte reste `gpu_usb_first_r3`, 480 Mbit/s, port 3-7, adresse 91,
série 11252024 ; debugfs rattache la console au slot 49 du contrôleur
`0000:00:14.0`. Les 17 premiers échos sont exacts ; l'index 17 attend `ea`
et reçoit `eaea`, toujours doublé après une seconde de grâce. Aucune requête
de diagnostic EP0 n'est insérée avant l'anomalie ; elles commencent une seconde
après pour lire les traces passives du FPGA.

Chronologie monotone du noyau, résolution imprimée de 1 µs :

| Temps (s) | Événement |
|---:|---|
| 7344872,721227 | Commande OUT de quatre octets soumise |
| 7344872,721291 | Commande OUT terminée, quatre octets |
| 7344872,721857 | EP2 IN : premier octet rendu au pilote |
| 7344872,721863 | `Reset Endpoint`, slot 49, DCI 5, `flags t:C` |
| 7344872,721878 | Fin du reset, endpoint Bulk IN arrêté |
| 7344872,721881 | Nouveau pointeur du ring, même slot/endpoint |
| 7344872,721977 | Une autre URB IN rendue avec longueur 0 |
| 7344872,721992 | EP2 IN : deuxième octet rendu au pilote |

DCI 5 désigne EP2 IN. Dans le décodeur Linux v6.17, `t` minuscule signifie
**TSP=0**, donc absence de préservation de l'état de transfert. Le reset
intervient 6 µs après la première livraison et 129 µs avant la seconde.
[Décodeur primaire](https://github.com/torvalds/linux/blob/v6.17/drivers/usb/host/xhci.h#L2077).
La capture confirme ainsi la présence du mécanisme de récupération proposé
par Claude au milieu du doublon ; elle n'identifie pas encore la faute initiale.

La première tentative retenue dans le FPGA est DATA0, longueur 1, CRC `c130`
(octet EA), sans ACK ni FIN. Le prédécesseur est DATA1, CRC `8107` (A1),
acquitté et retiré. Aucun ZLP dans cette fenêtre. La lecture finale donne
UART 215, POP 320, FIN 215, pending 0, aucune erreur RX signalée par le PHY.
Les PID restent observés à UTMI et non mesurés sur les broches USB.

**Limite du collecteur trouvée et corrigée :** `xhci_handle_transfer` trace
le TRB du buffer d'origine ; `field3` n'y porte pas le slot. Le filtre slot
masquait donc ces événements. Il faut `xhci_handle_event`, qui trace l'Event
TRB et contient le slot, l'endpoint et le code de complétion.
[Appels dans Linux](https://github.com/torvalds/linux/blob/v6.17/drivers/usb/host/xhci-ring.c#L2775).
L'absence des codes ne signifie donc pas absence d'erreur, et interdit de
conclure à un épuisement des reprises, un CRC fautif ou un babble précis.
Les événements de commandes reset et les URB filtrées par `devname` ne sont
pas affectés par ce défaut de filtre. Aucun événement perdu ou débordement
n'est signalé dans les statistiques des quatre CPU.

Le collecteur corrigé refuse désormais un événement sans contrat de filtrage,
archive sa propre source et son SHA dans chaque nouvelle capture. Self-tests
local et distant réussis, syntaxe et `git diff --check` réussis. SHA installé :
`530dcc2fbc97bcdc70dd20814d4ad4f65757ae21e98289d8a7d158cb298bc1a8`.
Une seconde capture avec la même commande est demandée pour lire le code
précédant le reset ; `sudo -n` reste indisponible. La carte est laissée au
repos pour cette mesure, sans autre lecteur CDC.

La seconde exécution utilisateur à 16:05 est récupérée dans
[usb_xhci_20261002_160500_867079](usb_xhci_20261002_160500_867079).
Le collecteur corrigé fournit désormais les codes : **USB Transaction Error
sur EP2 IN**, suivie du reset TSP=0 et de deux livraisons de `0e` pour une
demande à l'index21. Une première erreur EP2 survient après l'écho `59` ;
le suivant, `a2`, est rendu par xHCI après0,519ms, mais lu par Python
après493,498ms. Cette latence inclut la restitution côté hôte ; elle ne mesure
pas une transaction électrique USB de493ms. La sonde EP0 ultérieure échoue
avec EPROTO71 et n'apporte donc pas de nouvelle trace FPGA.
[Revue indépendante des deux captures](USB_XHCI_REVIEW_20261002.md),
[chronologie et empreintes](usb_xhci_20261002_160500_867079/analysis.json).
Le code d'erreur ne départage pas à lui seul CRC, timeout ou défaut PHY ;
la cause initiale reste à établir. Les deux captures sont complètes,
sans débordement ni échec de nettoyage.

#### Variante officielle RX_Mode Advance en cours de qualification

Le guide [Gowin IPUG781-1.7E, page16](https://www.gowinsemi.com/upload/database_doc/2125/document/687a7263eb932.pdf)
documente RX_Mode Normal (traitement à60MHz) et Advance (120MHz, moins de
latence, timing plus strict, pour Arora V). Le générateur installé contient
le choix `rx_mode` et la macro `V_120`. Le script de build permet ce choix
uniquement en diagnostic avec régénération officielle ; seul `V_120` est
ajouté au fichier de configuration, aucune source fournisseur n'est éditée.
Les arguments incompatibles sont refusés avant création du dossier de build.

`gpu_usb_advance_r1` termine avec110chemins détaillés, marge minimale
+0,139ns,93sources figées. SHA-256 :
`4409a350228043a2296af28acf7892aa4aa07a7a901bb8628ba06c9358cde785`.
Les fréquences, broches et SDC de production sont inchangés. La variante
conserve l'enregistreur de première tentative et le placement de reset r3.
Archive transférée et vérifiée sur ax15 :
`19cbca5d113ec4d7442f637df5440f8e576a32d54d4929039e049cdc451dd939`.
À ce point, le bitstream est seulement préparé : attente de la comparaison
des modèles Normal/Advance avant l'essai SRAM. Le PASS du build porte sur
les chemins couverts par son SDC ; il ne remplace pas la qualification des
traversées internes exclues, ni un essai USB matériel.

La comparaison des modèles est terminée :
[revue détaillée](USB_PHY_ADVANCE_REVIEW_20261002.md),
[rapport final](usb_phy_turnaround_advance_r4_20261002.json).
Le modèle Advance est exporté officiellement depuis une copie du VG
matériel exact. Les deux modes émettent correctement `c3 ea c1 30` et
reçoivent l'ACK isolé à phase locale0. Les ACK à40/100ns après émission
sont perdus ; ceux à200/340ns sont reçus. Advance réduit le délai de
décodage RX de67–83ns, mais conserve la temporisation de retournement :
48cycles120MHz contre24cycles60MHz. OEN libère le bus dèsSE0 ; aucun
conflit de pilotage n'est observé. Des écarts de tramage subsistent, et
une autre phase fait même échouer l'ACK isolé : aucune qualification
électrique complète n'est déduite de ces seuls modèles sans SDF.

`gpu_usb_advance_r1` est ensuite chargé en SRAM sur FTDI2023112818
(`3:66`), énumération à480Mbit/s sur `/dev/ttyACM1`. Le premier stress
échoue dès64octets : quatre insertions, les quatre derniers octets
réapparaissant avant la bannière suivante ; la bannière est également
doublée par endroits. Les deuxième et troisième rechargements prévus
ne sont donc pas exécutés. [Résultat](usb_ax15_20261002/usb_advance_r1/result.json).

Le diagnostic unitaire qui suit passe dix échos, puis perd `eb` (index10),
toujours absent après une seconde de grâce. Le premier DATA1 de CRC`00f0`
est pourtant acquitté et retiré, après des reprises DATA0 de l'écho`a2`.
Cela concorde avec la désynchronisation du toggle observée dans les
captures précédentes, sans nouvelle trace noyau sur cet essai.
[Échos et délais](usb_ax15_20261002/usb_advance_r1/isolated/result.json),
[trace FPGA](usb_ax15_20261002/usb_advance_r1/isolated/diagnostic.txt).
La variante Advance ne corrige donc pas la panne et n'est pas promue.

#### Mesure directe du délai de réponse dans les modèles

L'instrumentation passive associe maintenant la fin EOP du paquet hôte à
la première K de la réponse FPGA, dans la même transaction. Sur le modèle
Normal 3.4, les 277 réponses observées prennent **426,245 à 442,912 ns** :
toutes dépassent le budget nominal de 400 ns. Sur Advance, les 273 réponses
prennent **372,078 à 376,245 ns**, sans dépassement. Les données vérifiées
restent exactes dans les deux cas : 131 octets IN et 524 OUT.

Cette correction du délai dans le modèle n'est pas une correction complète :
les différences de tramage maintiennent le résultat global en échec, les
ACK courts restent perdus dans le mini-banc et le matériel Advance échoue.
Ce ne sont pas des mesures électriques sur la carte.
[Instrumentation, résultats et limites](USB_CONTROLLER_RESPONSE_TIMING_20261002.md).

#### Le témoin Sipeed intact reproduit le doublon

Le projet `usb_uart_loopback` Sipeed est compilé dans
`tang/impl/usb_sipeed_reference_r1`, sans changement de ses 17 fichiers
actifs, GPRJ, contraintes ou netlists. Seul l'export du timing texte est
demandé. Les 110 marges détaillées sont positives, minimum **+0,144 ns**,
TNS nul. [Provenance et compilation](USB_SIPEED_REFERENCE_R1_20261002.md).
SHA du bitstream :
`e845b1343a23a1a9a47cb61382e45b97f91272cb1edf051235cbcacb4c4bb556`.

`tools/check_usb_reference.py` vérifie 45 empreintes couvrant les sources,
le projet compilé, la configuration, le bitstream et le timing avant accès
carte. Le transfert vers ax15 est revérifié. Chargement SRAM sur
FTDI `2023112818`, `3:66`, avec `DONE`, puis énumération **359f:2010**,
série `11252024`, **480 Mbit/s**, `/dev/ttyACM1`, port direct `3-7`.

Le test utilise la boucle UART interne Sipeed à 115200 bauds, avec des
octets bruts et sans commande console ni requête de diagnostic privée.
Les **103 premiers échos sont exacts** ; à l'index 103, `70` revient sous
la forme **`7070`**, toujours doublé après une seconde de grâce. Arrêt au
premier défaut : les 897 échos unitaires restants et les blocs ne sont pas
exécutés. [Résultat complet](usb_ax15_20261002/sipeed_reference_r1/result.json),
[outil exact et empreintes](usb_ax15_20261002/sipeed_reference_r1/analysis.json).

Le défaut peut donc se produire sans CPU, GPU, DDR ni modifications de FIFO
de la console. Le témoin conserve les FIFO fournisseur d'origine ; cet
essai ne départage pas à lui seul FIFO, contrôleur, PHY, contraintes/routage
et liaison physique. Aucune capture xHCI simultanée ne permet d'attribuer
le doublon de ce témoin au même événement noyau que les essais précédents.

Le diagnostic **gpu_usb_first_r3 est ensuite restauré** : 88 sources,
SHA et timing revérifiés, SRAM `DONE`, énumération 480 Mbit/s. Le stress
reproduit deux insertions dans les 64 premiers octets reçus, avec les deux
derniers octets attendus reportés avant la bannière suivante. La restauration
est réussie ; l'USB reste défaillant et aucun bitstream n'est promu.
[Journal de restauration](usb_ax15_20261002/usb_first_r3_restored_after_reference/result.json).

#### Témoin avec PHY Full Speed dédié

`usb_sipeed_fs_r1` active la branche PHY FS Sipeed à 60 MHz, sur les
broches de terminaison prévues dans son top, avec le contrôleur officiellement
configuré FS déjà généré et les descripteurs 64 octets. Les IP restent
intactes. Les ports HS inutilisés sont retirés dans ce témoin isolé ; ses
contraintes conservent les périodes et les deux exceptions UART de référence.
Le SDC de production n'est pas modifié.

Audit syntaxe/ports/descripteurs réussi ; 110 marges de timing positives,
minimum **+0,153 ns**, TNS nul. Les 71 empreintes sont revérifiées avant
chargement. SHA bitstream :
`f420fe25751b3e21730488ed7cad3793d037a9ace94a62a2a970cea1603c75ae`.

Chargement SRAM réussi, mais **FAIL énumération** : détection Full Speed
à quatre reprises sur `3-7`, puis `device descriptor read/all, error -110`.
Aucun port CDC et aucun écho testé. La variante ne fournit donc pas encore
de solution de repli. Le diagnostic `gpu_usb_first_r3` est restauré et
revient à 480 Mbit/s, avec son échec de stress connu.
[Rapport, provenance, limites et journaux](USB_SIPEED_FS_R1_20261002.md).

#### PHY 3.5 trouvé dans l'installation Gowin 1.9.12.03

L'installation distincte `/home/michael/gowin/IDE` contient le PHY **3.5**
et le contrôleur **3.3**. Le document local
`doc/RN100-1.9.12.03E_Gowin Software Release Note.pdf` du 17 juin 2026
annonce un ajustement des paramètres de délai IO du PHY. Le fichier fournisseur
PHY diffère effectivement de la version 3.4 ; son wrapper public et ses
macros statiques sont identiques. Aucune correction de notre panne n'est
déduite de cette seule annonce.

Le build permet de choisir séparément l'installation de génération du PHY
avec `--usb-phy-ide`. La génération utilise son outil et ses bibliothèques ;
AE350, synthèse/placement console et contraintes restent ceux de 1.9.12.
L'option locale `--usb-phy-system-freetype` résout l'incompatibilité entre
la FreeType livrée avec 1.9.12.03 et la fontconfig système, uniquement pour
le sous-processus concerné. Aucun fichier de l'installation n'est modifié.

Les essais r1/r2 échouent au démarrage Qt, avant génération du PHY.
`gpu_usb_phy35_r3` compile avec **+0,139 ns**, SHA
`f3c5797e6a2acd0762f6c891f1478f3e799f86105bf0d765110df03fb6569e52`.
Sa configuration est encore provisoire : le générateur 3.5 expose de nouvelles
macros de famille/gating dont le besoin doit être vérifié avant chargement.
Les commandes IPFlow Tcl ne listent pas USB parmi les IP prises en charge
et ne produisent pas d'IPC lors de notre essai ; le retour vide n'est pas
une validation de configuration.

Le modèle exporté depuis le VG r3 exact montre des réponses à
**355,411–359,579 ns**, soit un cycle 60 MHz gagné sur 3.4 Advance.
131 octets IN et 524 OUT restent exacts, mais 279 écarts de tramage
maintiennent le résultat global en échec. Les ACK à 40/100 ns restent
perdus, ceux à 200/340 ns reçus. [Revue indépendante](USB_PHY35_REVIEW_20261002.md).
Ces résultats numériques ne constituent ni une validation électrique ni
une autorisation implicite de charger une configuration non vérifiée.

La configuration est ensuite **confirmée par la GUI officielle 3.5**, dans
un affichage privé. Le composant exact GW5AST-138B, UTMI, Single, Advance
et TX Delay0 produisent les cinq mêmes macros que r3, à l'ordre près :
`module_name`, `TX_DELAY_0_BIT`, `UTMI`, `V_120`, `GW5AT`. Les nouvelles
macros `DEF_DHCE/DEF_DHCEN` ne sont pas requises pour ce composant.
L'IPC et le fichier de defines produits sont conservés sous
`tang/impl/gpu_usb_phy35_gui_r1/src/usb2_0_softphy/`.

Après ce contrôle, **r3 est chargé en SRAM** : 94 sources et timing
revérifiés, `DONE`, énumération 480 Mbit/s. Le stress échoue dès sa première
série de 64 octets, avec deux insertions ; les deux octets attendus en fin
de bloc arrivent avant la bannière suivante. Les autres rechargements
prévus sont annulés. [Résultat](usb_ax15_20261002/usb_phy35_r3/result.json).

L'essai unitaire qui suit passe deux échos puis perd `a3`, index 2, encore
absent après une seconde de grâce. Le DATA1 UTMI de CRC `00c6` est pourtant
acquitté et retiré, après des reprises du DATA0 précédent (`5a`, CRC `c084`).
Les compteurs indiquent pending 0 et aucune erreur RX PHY. Aucune capture
noyau simultanée ne complète cet essai.
[Trace et résultat](usb_ax15_20261002/usb_phy35_r3/isolated/result.json).
La version 3.5 ne corrige donc pas l'instabilité observée et n'est pas promue.

`gpu_usb_first_r3` est restauré après le test 3.5 : `DONE`, retour à
480 Mbit/s sur `/dev/ttyACM1` (adresse 101), stress encore défaillant.
Le port est fermé et `fuser` ne trouve aucun lecteur actif.
[Restauration](usb_ax15_20261002/usb_first_r3_restored_after_phy35/result.json).

#### Contrat EP0 des contrôleurs régénérés : investigation séparée

La revue ne trouve pas de macro manquante : le define du contrôleur HS r20
est identique à Sipeed ; le FS r23 remplace seulement HSSUPPORT par FSSUPPORT.
Les types d'endpoints à zéro correspondent bien au mode Bulk.

En revanche, le [guide fournisseur IPUG927-1.8E, §3.2.1](https://www.gowinsemi.com/upload/database_doc/2121/document/6a5957fc5a564.pdf)
demande `rxrdy_i=1` et `txcork_i=0` pendant les requêtes standard EP0.
Le wrapper transmet `rxrdy=0` depuis la branche EP0 de la FIFO, y compris
dans le témoin FS dédié. Le guide récent vise une version plus récente
du contrôleur ; l'ancien modèle Sipeed tolère certains contrôles avec zéro.
Cette différence est donc un **candidat de compatibilité à vérifier**, pas
une cause d'énumération déjà prouvée ni une explication des doublons HS.

Le banc précédent ne teste pas GET_DESCRIPTOR. Un nouveau banc A/B doit
vérifier longueurs 8/18/64, contenu et CRC des données, acquittement DATA,
puis ACK obligatoire du ZLP OUT de statut, avant et après SET_ADDRESS.
Un premier essai n'ayant pas attendu l'attachement du modèle FS est invalide
et ne permet aucune conclusion sur `rxrdy`.


#### Défaut EP0 confirmé ; trois chargements du témoin FS réussis

Le banc correctement initialisé confirme le défaut : avec le contrôleur
FS 3.2, `rxrdy=0` produit les données et le CRC attendus, puis **NAK** au
ZLP OUT de statut. Avec `rxrdy=1`, neuf lectures complètes de 8/18/64 octets
passent avant/après SET_ADDRESS. L'ancien contrôleur Sipeed accepte les
deux valeurs pour le scénario 18 octets ; 17 événements ont mêmes dates
et contenus. La correction du mux EP0 est appliquée dans `console_top.v`.
[Preuves et limites du banc](USB_EP0_RXREADY_20261002.md).

Le témoin `usb_sipeed_fs_r2` avec cette seule ligne modifiée est chargé
**trois fois** sur la Pro Dock. Chaque chargement s'énumère à **12 Mbit/s**,
puis passe **1 000 échos unitaires et les blocs de 64/256/1 024 octets**
sans différence. Cela représente 3 009 séquences d'écho, 7 032 octets utiles
comparés au total, avec un bouclage UART interne ; aucun CPU/GPU n'est testé.
[Essai 1](usb_ax15_20261002/sipeed_fs_r2/result.json),
[essai 2](usb_ax15_20261002/sipeed_fs_r2_reload2/result.json),
[essai 3](usb_ax15_20261002/sipeed_fs_r2_reload3/result.json).
La durée jusqu'au premier `read()` non vide est une mesure hôte et ne doit
pas être présentée comme une latence sur le câble USB.

#### Nouveau contrôleur HS avec EP0 corrigé : échec distinct

`gpu_usb_hs32_ready_r1` combine contrôleur HS 3.2, PHY 3.5 Advance et
correctif EP0, dans la console de diagnostic avec mire, CPU et DDR mais
sans GPU. 99 sources figées, 110 marges détaillées positives, minimum
+0,143 ns, toutes les lignes TNS nulles. SHA du bitstream :
`672f342cc8ae3329050f170fb2c97f8f4bce2bb1e5ae7e5dea2395f65a05b117`.

Après `DONE`, l'énumération à 480 Mbit/s réussit. Le stress échoue dès le
premier bloc de 64 octets : trois insertions, trois octets finaux reçus
avant la bannière suivante, elle-même altérée. Les rechargements suivants
sont annulés. [Résultat et journaux](usb_ax15_20261002/usb_hs32_ready_r1/result.json).
Le correctif EP0 résout le témoin FS, mais ne suffit pas à rétablir le
transport HS. Cette variante n'est pas livrée comme fonctionnelle.

La suite intègre le PHY FS dédié dans la console complète, avec CPU/GPU/DDR
et firmware inchangés, via `--usb-controller gowin-full --usb-phy sipeed-full`.
Le SDC de production est préservé ; la copie FS retire exclusivement les
horloges HS absentes et leur groupe, avec toutes les autres périodes et
exceptions conservées. L'audit statique vérifie aussi que la branche HS par
défaut, après prétraitement, reste identique à celle d'avant cet ajout.
[Audit](usb_dedicated_fs_top_audit_20261002.json).


Un essai unitaire HS 3.2 confirme ensuite 17 échos corrects puis `ea → eaea`.
La première tentative DATA0 de CRC `c130` ne voit ni ACK PHY ni FIN ; la
précédente DATA1 de CRC `8107` les voit. Le motif subsiste avec le nouveau
contrôleur. [Résultat](usb_ax15_20261002/usb_hs32_ready_r1/isolated/result.json).

La première compilation de console FS dédiée (`gpu_usb_dedicated_fs_r1`)
s'arrête avant placement sur cinq contraintes visant le PHY HS supprimé.
La revue indépendante les identifie : deux horloges, deux BSRAM et une
cellule de reset. La copie CST de la variante les retire en plus des six
lignes de brochage HS ; les contraintes GPU/DDR/FIFO restent présentes.
`gpu_usb_dedicated_fs_r2` est une nouvelle compilation, le r1 reste intact.


Le routage complet `gpu_usb_dedicated_fs_r2` termine, mais échoue au contrôle
de timing : marge minimale −3,140 ns, 317 endpoints setup violés, aucun hold.
Le chemin dominant du blitter traverse l'ancien placement forcé
`t_step_16_s3` à R39C140 alors que source et consommateurs se trouvent
vers R98C58 / R77C63 ; deux fils coûtent 4,358 ns et 5,531 ns.
Le DMA présente aussi un détour du décodage d'état (6,856 ns).
**Image non chargée.** Une correction de placement FS est étudiée sans
changer le RTL fonctionnel ni les fréquences. `gpu_usb_fs_diag_r1` isole
la nouvelle liaison avec CPU/DDR et mire pendant cette fermeture du timing.

Le contrôleur 3.3 installé dans `/home/michael/gowin/IDE` est également
évalué avec PHY 3.5 Advance. `gpu_usb_hs33_ready_r1` échoue au timing
(−0,269 ns) sur la capture passive de première tentative, et n'est pas
chargé. Le r2 reprend l'observateur normal de dernières tentatives pour
réduire ce chemin de diagnostic ; le protocole applicatif reste identique.
La configuration et la note fournisseur sont conservées dans les sources
et métadonnées. Une mise à jour d'IP n'est pas une preuve de correction.


#### Exigence HS confirmée ; piste FS arrêtée

Michael exige explicitement **480 Mbit/s minimum** et refuse les variantes
FS. La compilation `gpu_usb_dedicated_fs_r3` est arrêtée par SIGTERM sur son
seul groupe1020189, après contrôle exact de commande et de dossier ; retour143.
Les autres compilations ne sont pas touchées. Le diagnostic FS CPU/DDR
`gpu_usb_fs_diag_r1` avait terminé avec +0,148 ns mais **n'a pas été chargé**.
Aucun build FS de console complète ou avec CPU n'a été chargé ; seuls les
anciens témoins minimaux appartiennent aux essais historiques conservés.

#### HS 3.3 avec PHY 3.5 et contrôle du rechargement

`gpu_usb_hs33_ready_r2` passe le timing : 98 sources, 110 marges détaillées,
minimum **+0,140 ns**, TNS nul. SHA :
`d5c7370acc70dca2ce7ca2992ecbb1f324ad24e0a9740058384daf298141d21a`.
Le contrôleur est officiellement régénéré en version3.3 ; le PHY3.5 est en
mode Advance. CPU800/DDR et mire conservés, GPU désactivé. Le r1 avec capture
première tentative restait en échec timing ; le r2 utilise la trace normale.

L'information de Michael sur les correctifs USB3 conduit à renforcer
`check_gpu_reloads.py` : enregistrer l'adresse USB avant, exiger une nouvelle
adresse et une configuration complète (configuration1, deux interfaces CDC,
autorisation), puis contrôler la vitesse. Un ancien port CDC encore visible
n'est plus accepté comme preuve d'un nouveau chargement. Tests ciblés du
filtre : ancien numéro, périphérique absent, configuration vide et zéro
interface rejetés ; nouvelle adresse configurée acceptée. Le script exact
utilisé est archivé avec le résultat et son SHA.

Chargement SRAM FTDI2023112818 entre20:05:06 et20:05:21 environ : `DONE`,
adresse USB **105→106**, topologie3-7, **480 Mbit/s**, configuration1 et deux
interfaces. Bannière initiale exacte, mais **échec du premier bloc64** :
une insertion à l'offset14 et dernier octet reporté après le bloc. La bannière
suivante contient aussi des altérations. Les autres rechargements s'arrêtent.
[Résultat](usb_ax15_20261002/usb_hs33_ready_r2/result.json),
[journal](usb_ax15_20261002/usb_hs33_ready_r2/load1/usb.log).

La revue USB3 distingue trois mécanismes : G18 pouvait rester en Compliance
avec PowerPresent constant après reconfiguration ; G19 réarme la reprise ;
G25b/G26b corrigent réponses EP0 anciennes, état de rafale conservé, longueur
capturée avant rewind et lectures tardives de l'ancienne transaction. Ces
corrections ne sont pas transposées aveuglément à l'USB2. Le nouvel essai
prouve ici une réénumération HS complète, puis une corruption de données ;
il ne prouve pas que toutes les conditions internes de phase sont correctes.
Sources lues sans modification : `../logic_analyser_wifi/TESTS/TESTS_USB_ANALYSE_2026-09-29.md`
et `USB_INTERSESSIONS_LA16.json` (état G26b énuméré automatiquement à5000M,
validation bulk/endurance encore non établie dans la note consultée).


#### Reprise EP0 après ACK perdu — défaut ouvert confirmé et corrigé

La comparaison avec les travaux USB3 révèle un autre défaut indépendant dans
le gestionnaire CDC : `usb_uart_config.v` abandonnait sa réponse au dernier
POP, avant confirmation par FIN. Un IN repris après ACK perdu recevait donc
un DATA1 vide au lieu de CDC7 ou du snapshot diagnostic32. Le banc réutilise
le vrai contrôleur, les données applicatives et les CRC ; aucune netlist
fournisseur n'est modifiée.

Le correctif conserve `endpt0_pending` jusqu'au FIN EP0, tout en terminant
TXVAL à la fin de chaque tentative comme l'exige le contrôleur. Quand TXACT
retombe sans FIN, l'offre et le premier octet sont réarmés sans nouvelle
capture du snapshot. Un nouveau SETUP ou reset annule l'ancienne réponse ;
un FIN EP2 ne la retire pas. Le signal est raccordé au top principal et aux
quatre anciens tops qui utilisent le même module.

Sur le modèle original puis sur l'export officiel du VG **HS3.3 exact**,
les deux contre-tests échouent avant et passent après : 7 et 32 octets
retransmis avec PID, contenu, CRC et status corrects. Les préemptions SETUP
avant et après émission passent. Les préfixes normaux avant/après sont
identiques, horodatages compris. Le banc applicatif contrôle 188 octets,
reprises partielles et répétées, snapshot gelé, FIN d'un autre endpoint,
reset avec horloge arrêtée. L'intégration EP0/EP2 vérifie 133 contrôles,
131 octets IN, 524 OUT et trois reprises exactes. Rapports et limites :
[revue EP0](USB_HS_RECOVERY_REVIEW_20261002.md),
[résumé HS3.3](usb_hs33_ep0_summary_20261002.json).

La connexion des anciens tops s'élabore dans Icarus pour E0b PL-only,
USB-only et no-DDR. `ddr_test_cdc.v` a une double déclaration DDR3_INIT qui
bloque ce simulateur avant comme après le raccordement ; cette anomalie
historique n'est pas modifiée dans ce lot. Il ne s'agit pas d'une validation
fonctionnelle de ces anciens tops.

Le témoin matériel **avant correction**, HS33 ready r2 encore chargé, alterne
CDC7 et les deux pages diagnostic32 sans ouvrir l'UART ni effectuer de reset.
Quatorze réponses sont complètes (les cinq CDC7 sont exactes), puis la
quinzième requête reçoit EPROTO71 après 0,191 ms. L'adresse106 et la
configuration HS persistent. Ce test ne force pas la perte d'ACK ; il ne
prouve pas la cause de cette erreur physique.
[Preuve](usb_ax15_20261002/usb_hs33_ready_r2_ep0_baseline/result.json).

`gpu_usb_hs33_ep0_r1` fige le correctif, contrôleur3.3/PHY3.5 Advance,
CPU800/DDR et mire ; GPU toujours désactivé. Timing habituel : 110 marges
positives, minimum **+0,139 ns**, TNS nul. 98 sources vérifiées, SDC de
production inchangé. SHA bitstream :
`e838aa90263c34df3521d495f9c819b70162fb1aa02dfeb3370d1e487b80360e`.
Le passage de cette grille de timing n'établit pas encore les relations de
phase internes coupées par le SDC ; l'audit PHY indépendant reste nécessaire.

Michael précise les deux défauts USB3 : absence de retour en détection
après débranchement, et absence de connexion après chargement avec câble
déjà branché. Les essais USB2 enregistrent donc explicitement une nouvelle
adresse/configuration à chaque rechargement sans débranchement. Une capture
montrant seulement le VID/PID n'est pas comptée comme une connexion validée.


#### Diagnostic HS corrigé : trois rechargements et reprise après débranchement

Les trois chargements SRAM de `gpu_usb_hs33_ep0_r1` passent, toujours sur
FTDI2023112818 avec câble SOFT-USB laissé branché. Adresses106→107→108→109,
480 Mbit/s, configuration1/deux interfaces à chaque fois. Chaque chargement
vérifie 100 tours de blocs1/64/256/1024/4096, soit544100 octets binaires exacts.
Total **1632300 octets exacts**, sans défaut de bannière.
[Résultat complet](usb_ax15_20261002/usb_hs33_ep0_r1/result.json).

Après le troisième chargement, **300 requêtes EP0 consécutives passent** :
100 CDC7 exactes à115200 8N1 et200 snapshots32 complets. Ensuite **1000 échos
unitaires** sont exacts, sans reset ni requête diagnostic entre ces échos.
Cela couvre aussi le retour au bulk après les contrôles EP0.
[EP0](usb_ax15_20261002/usb_hs33_ep0_r1_controls/result.json),
[échos après EP0](usb_ax15_20261002/usb_hs33_ep0_r1_after_controls/result.json).

Le défaut EP0 est prouvé avant/après par simulation indépendante du placement.
L'amélioration matérielle globale ne prouve cependant pas que ce seul défaut
expliquait tous les doublons bulk : ce nouveau bitstream a aussi un nouveau
placement. La variante reste GPU désactivé ; ces résultats ne constituent pas
encore une validation de la console graphique complète.

Michael effectue ensuite un débranchement/rebranchement SOFT-USB réel :
l'adresse109 devient110, 480 Mbit/s/configuration1/deux interfaces confirmés.
Un nouveau test100tours +300contrôles est lancé sur cette connexion sans
rechargement FPGA.

#### Réintégration dans la console complète

Le générateur n'interdit plus le PHY HS régénéré hors mode diagnostic : le
chemin normal conserve `CONSOLE_GPU`, le même firmware, le SDC de production
et les broches. La première compilation `gpu_l12_usb_hs33_ep0_r1` s'arrête
avant placement sur deux noms internes devenus absents : le PHY3.5 Advance
renomme le scope `fifo_rx` en `fifo_rx_pkt` pour la RAM RX et sa bascule reset.
L'export officiel confirme ces deux instances. Dans la copie CST propre au
build3.5/Advance, seuls ces deux noms changent ; coordonnées physiques et
contraintes restantes sont conservées. Le CST de production reste intact.
`gpu_l12_usb_hs33_ep0_r2` poursuit avec cette adaptation. Aucun bitstream
GPU complet n'est chargé à ce stade.

Après le rebranchement physique, le test100tours termine **PASS544100octets**,
puis les300requêtesEP0 passent également. Aucun chargement FPGA entre le
débranchement et ces tests. [Preuves](usb_ax15_20261002/usb_hs33_ep0_r1_replug/).
Les deux scénarios de reprise signalés par Michael sont donc vérifiés dans
cette variante diagnostic HS ; la réintégration GPU reste distincte.


#### Contre-vérification A/B : ne pas attribuer toute la stabilité au seul fix EP0

L'ancien `gpu_usb_hs33_ready_r2` est rechargé après les succès du corrigé.
Il passe maintenant **quatre chargements**, chacun10tours/54410octets, soit
217640octets exacts. Il échouait auparavant dès64octets. Les résultats sont
conservés dans `usb_hs33_ready_r2_crosscheck` et `usb_hs33_ready_r2_crosscheck_more`.
Ce constat interdit de présenter les nouveaux PASS comme une preuve que le
seul correctif applicatif EP0 guérit toute l'instabilité physique. Le défaut
EP0 et sa correction restent démontrés séparément par les contre-tests avec
ACK perdu. Le démarrage/état du lien et l'effet du placement restent à examiner.
Le corrigé est ensuite restauré, avec trois nouvelles séries100tours prévues.

La console GPU complète r2 échoue au timing :104violations setup DDR UI,
TNS−97,633ns, marge minimale−2,581ns, hold nul. Les trois ancrages hérités du
blitter provoquent des fils2,800/5,938/6,334ns vers un groupe désormais placé
à gauche. Le r3 retire uniquement ces trois `INS_LOC` dans sa copie CST,
pour laisser le placeur regrouper ces cellules. Aucun changement RTL GPU,
aucune fréquence réduite et aucune exception de timing ajoutée. r2 non chargé.


#### Nouvelle récidive et correction de qualification PLL

La restauration de `gpu_usb_hs33_ep0_r1` passe le premier chargement
(100 tours, 544100 octets), mais échoue au deuxième : l’adresse116 livre
les descripteurs HS puis Linux rejette la configuration1 avec `error -71`.
Le test s’arrête ; le troisième chargement n’est pas tenté.
[Résultat](usb_ax15_20261002/usb_hs33_ep0_r1_restored/result.json) et
[journal noyau](usb_ax15_20261002/usb_hs33_ep0_r1_restored/kernel.log).
Les PASS précédents ne constituent donc pas une résolution de l’instabilité.

La revue de [UG306-1.0.9E, note tableau5-2](https://cdn.gowinsemi.com.cn/UG306E.pdf#page=49)
trouve une exigence explicite : surveillance continue de LOCK pendant au
moins2ms. Notre qualification1024cycles attendait seulement21,33µs puis
17,07µs. `console_top.v` utilise désormais104000cycles de la référence
50MHz indépendante pour chaque PLL (2,08ms), puis64cycles dans phy_clk60
pour la libération locale. Le PHY reçoit `pll_locked_i=~rst_usb` ; son reset
est `PHY_RESET|rst_usb`, donc affirmé même avec phy_clk arrêté. La calibration
interne reste postérieure au reset contrôleur, distincte de ces attentes.
Aucune fréquence ni contrainte du SDC de production ne change.

Le [banc de la chaîne réelle](USB_PLL_LOCK_WINDOW_20261002.md) extrait les
instances et connexions du top : anciens réglages rejetés, six nouvelles
qualifications2,08003ms, glitches à1,5ms, arrêt des sorties PLL et reprise
après66frontsPHY passent. Cela prouve le comportement numérique, pas la
cause complète des erreurs physiques ni leur correction sur carte.

#### Retour prioritaire du GPU complet : `gpu_l12_usb_hs33_lock2ms_r1`

Le retrait des trois anciens ancrages dans r3 ramène le défaut de timing à
7 chemins setup DDR UI, TNS−3,848ns, minimum−1,215ns ; r3 reste non chargé.
Les cônes concernés sont : somme/comparaison des bornes crop vers les états
zoom/affine, choix longueur de segment puis addition d’adresse, et validation
d’adresse de sprite vers les enables du portDDR.

Corrections RTL utilisant des cycles déjà disponibles :

- calculer les bornes puis valider le crop pendant la lecture/préparation
  des commandes, avant Z_INIT/A_INIT ;
- avancer l’adresse et le reste de rafale quand le DMA échantillonne `w_req`,
  à partir de `w_len` enregistré ; aucune demande ni fin décalée ;
- calculer la fin de texture pendant la lecture du dernier mot du descripteur
  de sprite, puis comparer dans CHECK.

Le test affine et l’équivalence contre le snapshot r3 passent :
**604commandes, 2081517cycles et251234demi-mots comparés**, pages et gardes
exactes, commandesDDR identiques, aucune latence ajoutée aux interfaces.
[Journal](gpu_hs_lock2ms_equivalence_20261002.txt).
Le test800×480 couches/sprites/tuiles et la compilation complète avec les
nouveaux resets sont lancés. Le chargement attend un timing positif.


Le test800×480 passe également :16couches,64sprites, tuiles8/16/32,
retournements, transparence, défilement, descripteurs invalides et récupération
après blocageDDR. Scène la plus chargée2452/2556cycles, budget conservé.
[Journal](gpu_hs_lock2ms_layers_20261002.txt).

La première tentative lock2ms_r1 s’arrête avant génération IP : AF_NETLINK
interdit par le bac à sable empêche la vérification de licence Gowin. Relance
autorisée hors bac à sable dans `gpu_l12_usb_hs33_lock2ms_r2`, avec les mêmes
sources. Aucun autre processus Gowin n’est interrompu.


Le routage lock2ms_r2 supprime les sept anciens chemins négatifs, mais garde
deux violations setup sur le même enable `gi_1_s2 -> waddr_0/1_s6/CE` :
minimum−0,128ns, TNS−0,255ns, aucun hold négatif. Le cône contient encore
le test combinatoire `gi == rw-1` et un enable distant ; version non chargée.
Le dernier indice de ligne est maintenant calculé dans un registre pendant
la préparation, avant les états de génération. Le test devient une égalité
sans chaîne arithmétique sur `gi`. La nouvelle équivalence est relancée avant
la compilation lock2ms_r3.


lock2ms_r3 : les fins de ligne du blitter passent ; le nouveau placement
fait ressortir21violations sur le trajet sprites VALID → arbitre READY →
activation de l’adresse DMA, minimum−0,424ns, TNS−3,704ns, aucun hold négatif.
La plus longue connexion de ce trajet prend5,015ns. Cette version reste
non chargée.

`gpu_blit_dma.v` enregistre maintenant l’acceptation d’écriture puis avance
l’adresse dans le cycle suivant, pendant `valid=0`, déjà réservé à PACK/PREP
ou IDLE. Une nouvelle demande IDLE reste prioritaire sur cette avance.
Aucun transfert ni acquittement n’est retardé. L’équivalence compare l’adresse
sur **tous les cycles valid**, y compris les attentes, et conserve la
comparaison cycle par cycle des contrôles ; une adresse inactive peut
changer un cycle plus tard. C’est la seule différence d’interface autorisée.
Le test604commandes, pages/gardes et2081517cycles reste exact.
[Équivalence r4](gpu_hs_lock2ms_r4_equivalence_20261002.txt).
La compilation complète `gpu_l12_usb_hs33_lock2ms_r4` est lancée.


lock2ms_r4 : le chemin READY→adresse passe. Une unique violation subsiste,
`cy1_9_s2 -> st_25_s0/D`, −0,343ns (TNS identique, hold nul), via la comparaison
de rectangle vide, un enable partagé et une longue connexion. Non chargé.
La comparaison `cy0>cy1 || cx0>cx1` est préparée dans le cycle M_CLIP qui suit
la dernière mise à jour des bornes, avant RECT_INIT/TXT_START. L’équivalence
est relancée avec cette préparation supplémentaire pour lock2ms_r5.


lock2ms_r5 : comparaison du rectangle vide conforme. Treize chemins du
rasteriseur de triangles sont maintenant négatifs, de `edge_left[1]` vers
la largeur/les états de span : minimum−1,169ns, TNS−8,235ns, hold nul.
La cascade de deux comparaisons max/min, multiplexages puis soustraction
est remplacée par trois comparaisons de paires en parallèle et un choix
one-hot. Les égalités donnent les mêmes bornes ; aucun état ni cycle ajouté.
Version r5 non chargée ; équivalence complète et compilation r6 prévues.


**lock2ms_r6 passe le timing** : 110 chemins détaillés, minimum +0,138 ns,
aucune violation setup/hold et TNS nul. Les 97 sources figées ont été
vérifiées par SHA ; fréquences et SDC de production inchangés.
Le test d’équivalence r6 passe encore 604 commandes, les pages/gardes,
2081517 cycles de blitter et toutes les commandes DDR, attentes comprises.
[Journal r6](gpu_hs_lock2ms_r6_equivalence_20261002.txt).

Bitstream : `f4b5df8fbb80c2a5b02b1688874772768713d341848c904d42fe12bf89cb2193`.
Archive de transfert : `63b645d8da5f1a3be27ef83becbcba53c5501506c30364e18ea7c02bec7db5da` ;
empreinte vérifiée sur ax15 avant extraction. Le test matériel charge en SRAM
uniquement FTDI2023112818 : trois rechargements, chacun20tours USB, puis suite
GPU complète après le dernier. Dossier distant `TESTS/gpu_l12_usb_hs33_lock2ms_r6`.

### 3 octobre — échecs matériels r6 et correction du pont CPU DDR

Le timing positif de r6 ne suffit pas : deux rechargements passent chacun
20 tours USB, le troisième perd 65/256 octets. Une autre série passe les
échos mais le CPU se bloque pendant la première boucle d'écriture DDR
avec cache. `Z` peut aussi bloquer avant le message de démarrage.
Le témoin r13 passe la DDR avec le même firmware, puis perd le `S` de
`SHARED END` sur USB. Ces résultats sont distincts ; USB n'est pas résolu.

Le J-Link confirmé par Michael permet d'arrêter r6 avant la première store
avec cache et de l'exécuter pas à pas. L'exécution suivante ne rejoint pas
la fin de la boucle et les demandes d'arrêt échouent. Le PC renvoyé après
expiration du débogueur est inexploitable.

La revue du pont Sipeed établit plusieurs contrôles directs 50↔75 MHz
malgré ses FIFO de données. Ces chemins sont exclus du STA par les groupes
asynchrones. Le remplacement `ahb_ddr_cdc` transporte commande et réponse
dans deux FIFO. Sept scénarios numériques passent, chacun 2 216 commandes,
avec dérive/phases, masques, rafales, attentes, arrêts d'horloges et resets.
GPU complet `gpu_l12_usb_hs33_cdc_r1` en compilation ; validation matérielle
encore nécessaire. Détails et limites : [DDR_AHB_CDC_20261003.md](DDR_AHB_CDC_20261003.md).

Pendant la compilation, le témoin complet r13 est rechargé et `Z` relance
l'animation : environ 55 fps et underflows=0 selon les compteurs. Son
stress USB échoue et ses réponses contiennent encore des pertes/doublons.
Il s'agit d'une restauration temporaire de l'affichage, pas d'une validation
USB. Évidence `usb_ax15_20261002/gpu_l12_diag_r13_animation_restore`.
