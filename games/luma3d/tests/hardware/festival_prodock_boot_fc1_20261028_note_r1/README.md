# Pro Dock ax15 — démarrage RAM G22r0/G3D1 et livraison FC1

Cette note est préparée sans accès matériel, transfert ni modification des chargeurs. La précision utilisateur désigne **la Pro Dock déjà branchée à ax15, FTDI2023112818**. Ce n'est donc pas une nouvelle sélection de périphérique à inventer.

## Décision immédiate

Si la relecture root confirme le noyau `6.12.112-prodock-luma3d-g3d1-r1` et FM4A PID3940/start35705238 avec les arguments connus, conserver cet état. Utiliser le nettoyage préparé de deux benchmarks puis le deltaFC1 de118315octets. Le paquet transfert vérifie à nouveau cette identité : il refuse tout autre état.

Si Linux a réellement disparu après un reset/rechargement FPGA, FM4A et ses fichiers/tmp ont disparu aussi. Le delta ne convient plus. La procédure RAM vérifiée exige un **J-Link sur le JTAG du processeur AE350/A25**, absent du dernier inventaire root communiqué. Le programmateur FTDI du FPGA ne remplace pas ce branchement dans cette procédure. Ne pas recharger le FPGA vivant en anticipant que le chargement Linux suivra sans ce J-Link.

## Branchements requis par la procédure connue

1. Programmateur FPGA de la Pro Dock visible enUSB, FTDI0403:6010, numéro2023112818 ; permet le chargement SRAM G22r0.
2. J-Link USB connecté au JTAG du **CPU AE350**, numéro historique506005083 : TCK/TMS/TDI/TDO, masse et référence de tension de la cible selon le connecteur existant. Le présent dépôt ne justifie pas un nouveau brochage pin-par-pin ; ne pas le déduire du connecteur FPGA. Le chargeur sélectionne `-Device A25 -If JTAG`.
3. Port SOFT-USB de cette même carte vers ax15, CDC359f:2011/iSerial11252024, attendu en480Mbit/s. Les scripts historiques refusent plusieurs consoles identiques ; le by-id seul n'identifie pas deux Pro Dock chargées du même firmware. Ici root a clarifié une seule cible.
4. Alimentation auxiliaire12V et écranLCD800×480 conservés. Aucun accès ni carteSD n'est nécessaire pour ce démarrage volatile.

## Fichiers exacts, vérifiés localement

Tous les chemins, tailles, SHA-256 et CRC sont dans `identities.json`.

- FPGA : `tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs`,41688834octets, SHA`fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- Paquet Linux : `games/luma3d/build-kernel/prodock_g3d1_20261024_r1/`, manifeste SHA`2b6c8b61a920ea45fcc189a44c5af7f4d6941b87c5d9a814af87021f478c091f`.
- Payload OpenSBI+noyau+initramfs :25673800octets, SHA`0ff71bb9b7d44ce2f149ed6406d33c8497b45b8439c54b896621dedcd0c498b3`.
- `payload.rle.bin` :3461284octets, SHA`80229b6ec248710b0d9a7ce9dcf72e1942a524bb2582d5c26f05d0d90d33c1fb`.
- `launch_packed.bin` :12184octets, SHA`e252f9adc872d45ee80ffd15832339f05a8f08601c68a1042585441367136ef4`.

G22r0 est la référence fonctionnelle historique avec ses limites de timing/USB déjà documentées ; cette note ne lui attribue pas un timing PASS.

## Commandes de la procédure connue — à exécuter seulement par root après identification

En présence du J-Link et d'une cible prête à perdre son étatRAM, le chargement FPGA utilise **SRAM** (`-m`), sans écrire sa flash :
```
bin/openFPGALoader --busdev-num BUS:DEV -b tangmega138k -m tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs
```
`BUS:DEV` doit venir de l'identification récente du FTDI2023112818, jamais d'une valeur ancienne. Observer DONE, l'énumérationHS et le firmwareG22r0. Avant de stopper sonCPU, `tools/load_ilm.identify_console()` puis `quiesce_console()` exigent l'acquittement du firmware. Si une interfaceMSC existe, aucun volume associé ne doit être monté ; ne détacher que cette interface identifiée, pas le CDC.

Depuis le firmware G22r0 initialisé, le chargeur compact connu est :
```
python3 tools/load_linux.py --pack games/luma3d/build-kernel/prodock_g3d1_20261024_r1 --packed --jtag-speed 4000 --out TESTS/NEW_PRODOCK_BOOT
```
Cette commande n'est pas un chargeur multicarte : ses identités FTDI/CDC et J-Link sont historiques et fixes. Elle n'est pas à lancer sur Linux déjà actif. La version warm répond à un autre cas, transitionLinux→parkingM-mode, et n'est pas nécessaire pour le départ froid aprèsFPGA.

Le script J-Link produit utilise `DisableFlashDL`, `DisableFlashBPs`, `SetAllowFlashCache=0`, `connect`, `h`, puis :
```
speed 4000
loadfile PACK/payload.rle.bin 0x10000000 noreset
loadfile PACK/launch_packed.bin 0xa0000000 noreset
verifybin PACK/launch_packed.bin 0xa0000000
SetPC 0xa000000c
g
q
```
Invocation sous-jacente : `JLinkExe -SelectEmuBySN 506005083 -Device A25 -If JTAG -Speed 100 -JTAGConf -1,-1 -NoGui 1 -ExitOnError 1 -CommanderScript SCRIPT`.
Le lanceur décompacte et vérifie leCRC intégral avant OpenSBI à0x07C00000 ; noyau à0x08000000. Attendre `CRC OK`, la versionG3D1 exacte puis `PRODOCK_LINUX_READY - SD non montee; prodockctl info`. Contrôler noyau, caps GPU, affichage, absence de montageSD ; pas seulement un prompt.

## FC1 complet si le fichier de base est absent

`fc1.full.lz4` est le **fichier complet compressé**, pas un delta :5808670octets. Il reconstruit l'ELF16644780octets SHA`950ced706963b9f7591f45c067b80ee515dcae084a061c78274fe0f00f3871f7`, CRC`ad06b5da`.
La décompression libLZ4 indépendante et le mode`unpack` du helperhost ont produit exactement ces octets. Aucun jeu n'a été exécuté et aucune nouvelle preuveQEMU/RV32 n'est revendiquée pour cette compression complète ; le helperRV32 est celui déjà validé.

Sur une installation Linux vide, préparer d'abord le receiverRX2 et le helper avec relectureintégraleSHA après bootstrap, puis transférer le fichiercomplet via le senderRX2 validé par segments/checkpoints. Les chemins locaux et empreintes de ces outils sont dans identities.json. Les contrôleurs existants de transfertFM4A sont liés à unPID et une base préexistants : **ne pas les réutiliser en supprimant leurs gardes** pour ce départfroid.

Commandes terminales après transfert confirmé et contrôles d'espace :
```
/tmp/mc1-helper unpack /tmp/rx2-fc1-full.lz4.part /tmp/luma3d-fc1 16644780 ad06b5da
/tmp/mc1-helper raw /tmp/luma3d-fc1 unused 16644780 ad06b5da
chmod 700 /tmp/luma3d-fc1
/tmp/luma3d-fc1 --festival --festival-save /tmp/fc1-new.festival.save --memory-save /tmp/fc1-new.memory.save
```
Les noms doivent être neufs et la cible un fichier normal non symlink. Réserve/tmp minimale fichiercompressé+ELF+8MiB=30842058octets et MemAvailable>=64MiB. LeSHAci-dessus est celui de l'ELFlocal ; le contrôleduhelper surcarte est unCRCcomplet. Lancementpersitant/fenêtresd'essai doivent encore être bornés et relusparroot selonl'état réel. Les performances du transfertcomplet ne sont pas celles du delta118Ko.

Toutes les données de jeu et Linux restent enRAM ; une extinction ou reconfiguration les perd. Aucun fichier de démarrageSD ni flash permanent n'est installé par cette procédure.
