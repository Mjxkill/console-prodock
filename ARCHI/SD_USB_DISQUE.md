# Carte SD et disque USB

Contrat matériel et logiciel de deux fonctions ajoutées au socle de la console :
la carte microSD du dock, et la présentation de la console au PC comme
**un port série et un disque** sur le même câble USB. L'état de validation
(simulation, PC, carte) est tenu dans `TESTS/TESTS_SD_USB.md`, puis dans
`TESTS/TESTS_REPRISE_20261007.md` pour les corrections du 7 octobre ; ce document
décrit ce qui est construit, pas ce qui est prouvé.

Les corrections issues de la revue du 8 octobre (CMD13, fin CMD25, validation
CBW, verrou BOT matériel/logiciel et USBDISK R4) sont détaillées dans
[`CORRECTIONS_REVUE_20261008.md`](../TESTS/CORRECTIONS_REVUE_20261008.md).
Ce suivi indique séparément les preuves de simulation et la qualification
matérielle. C37 et USBDISK R4 sont qualifiés le 9 octobre ;
l'archive C22 ne contient pas le nouveau garde BOT.

## 1. Carte microSD

Le connecteur microSD du dock est câblé en SDIO sur des broches libres du FPGA.
La carte est pilotée **en mode SPI** par le contrôleur SPI optionnel de l'AE350
(`AE350_APB_SPI_EN`, ATCSPI200 en `0xF0F00000`), sans logique nouvelle.

| Signal carte | Broche FPGA | Rôle en mode SPI | Source |
|---|---|---|---|
| CLK | D23 | horloge | `SPI_CLK` de l'AE350 |
| CMD | D24 | MOSI | `SPI_MOSI` |
| D0 | H23 | MISO | entrée `SPI_MISO` |
| D1 | J23 | inutilisé | entrée |
| D2 | A25 | inutilisé | maintenu à 1 |
| D3 | B25 | sélection (CS) | GPIO 0 de l'AE350, 1 au repos |
| DET | J15 | présence | GPIO 1 (0 : carte insérée) |

- Les broches sont en LVCMOS33 (`tang/constr/gpu.cst`).
- **Les sorties « OE » utilisées de cette IP AE350 sont actives à l'état haut.**
  Relevé reproduit le 7 octobre : sur le R40 diagnostic, seul COMBO=1
  (OE haut, GPIO 0 en sortie) produit des fronts SPI et une réponse CMD0/CMD8.
  La description précédente de leur polarité était erronée. Les sources
  actuelles fixent directement la convention qui fonctionne.
- Relecture par le firmware : GPIO 1 = présence, GPIO 2 = horloge,
  GPIO 3 = commande, GPIO 5 = sélection. GPIO 0 est la sortie de sélection ;
  son registre d'entrée ne permet pas de vérifier le niveau physique.
  Le bit GPIO 4 qui changeait la polarité dans R40 n'est plus utilisé.
- Le GPIO de l'AE350 (`0xF0700000`) passe en ports séparés entrée/sortie/validation
  (`AE350_GPIO_IOPORT_EN` retiré) : c'est ce qui permet de n'en sortir que deux bits.
- Horloge SPI = 80 MHz / (2 (n + 1)) : 400 kHz à l'initialisation, puis 20 MHz
  (essai à 40 MHz par la commande `H` de l'application d'essai).

Logiciel (`fw_console/`) :

- `sd.c`/`sd.h` : protocole SD en mode SPI (CMD0, 8, 59, ACMD41, 58, 16, 9, 17, 18,
  24, 25, 12, 13), CRC7 et CRC16 vérifiés, statut de programmation contrôlé,
  reprises bornées sans repli de fréquence : l'identification se fait à 400 kHz
  puis le régime demandé reste fixe. Indépendant du matériel par quatre fonctions `sd_port_*`.
- `sd_ae350.c` : ces fonctions sur l'ATCSPI200 et le GPIO.
- `fatfs/` : FatFs R0.11a repris du SDK AE350 (voir `tang/rtl/PROVENANCE.md`),
  configuré pour un volume, secteurs de 512 octets, noms courts.
- `sd_test_main.c` : application d'essai téléchargée en ILM.

## 2. USB composite : port série + disque

Le périphérique garde son identité `359f:2011` et son port série CDC inchangé
(interfaces 0 et 1, EP2 données, EP3 notification). Il gagne une interface 2
« stockage de masse, SCSI transparent, Bulk-Only » sur **EP1 OUT et EP1 IN**
(512 octets en High Speed).

- Descripteurs (`usb_descriptor.v`, paramètre `MSC`) : classe de périphérique
  EF/02/01, association d'interfaces pour le CDC, configuration de 98 octets,
  `bcdDevice` 2.00. Avec `MSC = 0`, les octets sont ceux d'avant.
- Requêtes de classe (`usb_uart_config.v`, paramètre `MSC`) : Get Max LUN
  répond 0 par le chemin déjà validé de GET_LINE_CODING (même reprise après ACK
  perdu) ; Bulk-Only Mass Storage Reset est signalé au port.
- `usb_fifo.v` : EP1 activé. EP1 IN est en **mode paquet validé**
  (`EP1_IN_PACKET`) : l'hôte ne se voit proposer que
  min(octets validés − octets acquittés, taille de paquet). Un bloc en cours
  d'écriture n'est donc jamais pris pour un paquet court, qui terminerait le
  transfert. La longueur d'un paquet reste figée jusqu'à son acquittement
  (mécanisme existant de reprise).

### Port du firmware : `usb_msc_port.v`, fenêtre `0xE9003000`

| Adresse | Accès | Contenu |
|---|---|---|
| +00 | R | identité `0x554d5343` (« UMSC ») |
| +04 | R | état : bit0 octet reçu disponible, bit1 émission vide, bit2 reset du bus vu, bit3 reset Bulk-Only vu, bit4 purge en cours, bit5 configuré, bit6 High Speed, bit7 perte, bit8 le firmware sert le disque, bit9 service demandé, bit10 verrou BOT, bits 31:16 octets émis non acquittés |
| +08 | R | octet reçu (bit31 = 1 : aucun) ; la lecture le retire |
| +0c | W | octet à émettre |
| +10 | W | validation de tous les octets écrits |
| +14 | W | commande : bit0 purge, bit1 demande le disque, bit2 efface « reset du bus », bit3 efface « reset Bulk-Only », bit5 rend le disque, bit6 demande le verrou BOT, bit7 efface « perte » |
| +18 | R | octets écrits (15:0) et acquittés (31:16), modulo 65 536 |
| +1c | W | quatre octets à émettre, celui des bits 7:0 en premier |
| +20 | R | quatre octets reçus, le premier dans les bits 7:0 ; à ne lire que si +24 en annonce au moins quatre |
| +24 | R | nombre d'octets reçus disponibles (valeur prudente, jamais supérieure au réel) |
| +28 | R | version ABI du garde BOT : 1 dans les sources corrigées, absent dans C22 |

- Deux FIFO double horloge (`ddr_dcfifo`) séparent l'AHB 80 MHz du contrôleur
  USB 60 MHz. Le marqueur de validation voyage dans la même FIFO que les
  octets, donc dans l'ordre. Aucune attente AHB ne dépend de l'horloge USB.
- La purge attend l'acquittement de son assertion puis de son retrait dans
  le domaine USB. Une horloge arrêtée laisse le bit « purge en cours » à 1,
  sans bloquer les lectures AHB. Les deux moitiés des FIFO sont remises à
  zéro avant que de nouveaux octets soient autorisés.
- Un accès AHB coûte environ 0,2 µs depuis le cœur à 800 MHz : les accès par
  mots de quatre octets (+1c, +20) existent pour le débit. Côté USB le port
  émet un octet tous les deux cycles (30 Mo/s). Une lecture de mot attend au
  plus 15 cycles AHB que ses quatre octets, déjà reçus, soient rassemblés ;
  lue sans octets annoncés, elle rend la main et lève « perte ».
- Une écriture est acceptée tant que le niveau non acquitté ne dépasse pas
  3 576 octets ; au-delà elle est refusée et
  « perte » est levé (jamais de débordement silencieux).
- En réception, le contrôleur répond NAK à l'hôte tant que le firmware n'a pas
  fait de place : rien n'est perdu.
- La fenêtre `0xE9002000` (trace USB) est inchangée.

`usb_msc_guard.v` contrôle les paquets CRC-valides d'EP1 dans le domaine USB.
Un CBW invalide ou une perte de cadrage verrouille EP1 IN/OUT jusqu'au reset
BOT/bus ; une purge locale ou CLEAR_FEATURE seul ne suffit pas. Le contrôleur
fournisseur répond NAK au port bloqué, puis le wrapper UTMI substitue STALL
à ce seul PID. GET_STATUS d'EP1 reflète HALT. Les octets bulk et le CDC ne sont
pas modifiés. La demande et le statut de verrou traversent les horloges par
leurs synchroniseurs dédiés, en complément des FIFO à deux horloges.

### Lecteur sans carte : `usb_msc_empty.v`

Le bitstream est commun à tous les programmes (diagnostic, Orbital, Luma…),
dont la plupart ignorent le disque. Un disque muet ferait attendre le PC, qui
finirait par réinitialiser le périphérique entier, port série compris. Tant
qu'aucun firmware ne sert le disque, **le matériel répond donc lui-même comme
un lecteur de cartes vide** :

- INQUIRY standard : identité « Electros / Console SD / 1.00 », amovible ;
- REQUEST SENSE : NOT READY, MEDIUM NOT PRESENT (02/3A/00) ;
- toute autre commande échoue, phases de données respectées (longueur
  annoncée émise en zéros, ou lue et jetée), état dans un paquet à part.

Passage de main :

- le firmware demande le disque (bit1) ; le matériel l'accorde **entre deux
  commandes de l'hôte**, émission terminée (bit8). L'hôte apprend l'arrivée du
  support par UNIT ATTENTION à sa commande suivante ;
- le firmware le rend (bit5) entre deux commandes : rien n'est purgé ;
- chien de garde : après 2^29 cycles AHB (6,7 s) sans aucun accès à la fenêtre
  (processeur arrêté par J-Link, autre programme chargé), le matériel reprend
  le disque et purge les tampons ; l'hôte voit le support retiré ;
- un reset du bus ne retire pas le disque au firmware : il le voit (bit2) et
  purge.

### Firmware : `usb_msc.c`/`usb_msc.h`

Transport Bulk-Only et commandes SCSI au-dessus d'un périphérique de blocs
(`usb_msc_disk` : capacité, lecture, écriture, synchronisation). Commandes :
TEST UNIT READY, REQUEST SENSE, INQUIRY (pages 00 et 80 comprises), MODE SENSE
6 et 10, START STOP UNIT, PREVENT ALLOW MEDIUM REMOVAL, READ FORMAT CAPACITIES,
READ CAPACITY 10 et 16, READ 10, WRITE 10, VERIFY 10, SYNCHRONIZE CACHE.

Règles de transport (USBDISK R4 exige le garde BOT matériel) :

- vers l'hôte, exactement la longueur annoncée est émise, complétée par des
  zéros ; le résidu de l'état dit ce qui manque ;
- venant de l'hôte, tout ce qui est annoncé est lu, même si la commande échoue ;
- les octets ne sont validés qu'aux multiples de 512 depuis le début de la
  phase puis à sa fin ; l'état n'est écrit qu'une fois les données acquittées ;
- un transfert sans progression pendant 3 s est abandonné et compté ; hors
  reset hôte, il verrouille le transport jusqu'à la récupération BOT ;
- les CBW/CDB sont validés avant exécution ; après une commande invalide,
  aucune nouvelle signature n'est recherchée dans le flux ;
- Un reset survenu pendant les lectures groupées RX4 invalide le tampon
  avant toute écriture du support ; RX_COUNT n'est pas une garantie contre
  une purge postérieure à sa lecture.

La sortie matérielle MSC vers EP1 enregistre ensemble données, validité
et compteur de validation publié. Cette étape ajoute un cycle USB, sans
réduire le débit ; elle coupe le long chemin combinatoire depuis le reset
du contrôleur vers la BSRAM d'émission. Un reset EP1 annule également
l'octet encore dans ce registre. L'attente « émission terminée » tient
compte du compteur publié avant toute remise du disque au lecteur vide.

`usb_disk_main.c` est l'application téléchargée en ILM : disque = carte SD si
elle répond, sinon 32 Mio de DDR (`0x08000000`) formatés FAT16 au démarrage.
Le port série donne le journal et accepte `?`, `s`, `m`, `v`, `q`, `g`, `d`.
La commande `d` sélectionne explicitement le disque DDR, même si une SD est
présente ; `m` recherche de nouveau la SD. Changer de support uniquement
après avoir démonté le disque sur le PC et terminé ses transferts.

## 3. Essais sur le PC connecté à la carte

Avec l'application USBDISK chargée et aucun autre client du port série :

```sh
python3 tools/check_usb_disk.py --out TESTS/disque_lecture
python3 tools/check_usb_disk_recovery.py --rounds 12 --out TESTS/disque_reprises
```

Le premier contrôle l'identité du périphérique composite HS, son port série
et les transferts. Sur SD, son comportement par défaut est exclusivement
en lecture : aucun montage, aucun fichier créé et deux lectures de 8 Mio.
Sur le disque temporaire en DDR, il exerce aussi l'écriture et la relecture.
`--allow-sd-write` autorise les écritures brutes destructives sur une carte
d'essai ; cette option n'est pas utilisée dans les validations de la SD
physique du 7 octobre.

Le second interrompt des READ10 par un reset Bulk-Only, efface les halts,
puis vérifie que les lectures reprennent avec les mêmes données. Il
n'écrit jamais sur le support. Les deux outils sélectionnent la console
de série `11252024` et vérifient la liaison High Speed.

## 4. Ce qui n'est pas fait

- Démarrage sur carte SD : il demande un chargeur dans l'ITCM, donc une
  écriture de la flash, qui n'est faite qu'avec l'accord explicite de
  l'utilisateur.
- Le lecteur sans carte ne connaît qu'une unité logique et ne gère pas le
  verrouillage du support.
- Si un firmware rend le disque à l'instant précis où une commande de l'hôte
  arrive (fenêtre inférieure à une microseconde), cette commande peut être
  partagée entre les deux ; l'hôte s'en remet par son reset de récupération.
