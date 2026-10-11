# Linux sur la console Pro Dock

Évolution du 11 octobre : terminal natif fbcon en **tuiles matérielles**, jeu
400×240 + terminal 50×15 + diagnostics 100×15, modes plein écran et shell
permettant de lancer `prodock-game`. Voir
[la description du mode partagé](../ARCHI/LINUX_AFFICHAGE_PARTAGE.md) et
[les essais associés](../TESTS/LINUX_DESKTOP_20261011.md). Les paragraphes R12
ci-dessous décrivent le port initial et ses preuves historiques ; l’interface
actuelle réserve 2 Mio à l’affichage et laisse 86 Mio aux applications.
L'affichage Linux R12 du 11 octobre est validé sur **G22r0** : 51,92 FPS
sur le jeu d'intégration, puis 131 s d'endurance à 51,09 FPS sans erreur.
Le chargement actuel utilise J-Link compact (`--packed --jtag-speed 4000`) ;
les gros transferts MSC décrits plus bas ont rencontré des échecs et restent
à fiabiliser. Le terminal CDC HS est testé séparément.

Port expérimental de **Linux 6.12.112, OpenSBI 1.6, BusyBox 1.37.0 et
musl 1.2.5**, pour le matériel C37. Le cœur reste à **800 MHz** et les
horloges bus/GPU/LCD restent à **80/75/35 MHz**.

**Linux R12 qualifié sur C37** : shell, threads/mémoire virtuelle, rendu GPU
(384 000 pixels comparés, 2 430 commandes, aucune sous-alimentation LCD),
lectures SD répétées et montage FAT32 en lecture seule. Le démarrage SD à deux
modes reste à installer et à qualifier. Preuves et limites :
`TESTS/LINUX_PRODOCK_20261009.md`. Un passage QEMU ne qualifie pas le matériel.

## Deux modes conservés

Le menu U-Boot propose Linux, LUMA sans Linux, ORBITAL sans Linux. Le menu
a démarré en RAM et lu un fichier SD avec CRC ; les images sont préparées
dans ce dossier. Le bitstream C37 existant
conserve son firmware de diagnostic au démarrage électrique. Le premier étage
SD peut être chargé en ILM pour essayer le menu. Son intégration permanente
dans l'initialisation ITCM du FPGA demande encore un build/timing/essai dédié.

Linux prend seul possession du GPU, du SPI et de la SD. Les applications
bare-metal ne tournent pas en parallèle du noyau. Les ressources graphiques
historiques restent hors de la mémoire allouée à Linux.

## Interfaces livrées dans les sources

| Fonction | Interface | Contrat |
|---|---|---|
| Console série | `/dev/ttyS0` | UART2 via CDC FPGA HS 480 Mbit/s, UART à 115200 |
| SD | `/dev/mmcblk0` | ATCSPI200 et `mmc_spi` amont ; mode SPI 0, jusqu'à 20 MHz |
| Terminal Linux | `/dev/tty1`, fbcon tileblit | Glyphes composés par le FPGA ; fb0 réservé au noyau |
| Disposition et diagnostics | `/dev/prodock-display` | Écran partagé, jeu ou terminal plein écran ; texte de diagnostic |
| Accélérateur | `/dev/prodock-gpu` | Un propriétaire, accès root/CAP_SYS_RAWIO, ioctl et mmap |
| Contrôle utilisateur | `prodockctl` | `selftest`, `info`, `demo`, `display`, `layout` |
| Jeu Linux | `prodock-game` | Casse-briques GPU, clavier ou `--demo`, lancé depuis le shell |
| Test du système | `prodock-runtime` | Threads/mutex, fork, mmap, mprotect, copie à l'écriture |

Le GPU conserve ses opcodes 1–30, 16 couches, 64 sprites, tuiles, palette,
police, rasterisation RGB565, textures, profondeur et composition V1.
Sous Linux, quatre couches appartiennent aux consoles et douze au jeu.
L'ABI géométrie G3D1 de G22r0 n'est pas encore exposée par ce pilote Linux.
Le pilote vérifie les plages mémoire, attend la fin des commandes et présente
au retour vertical. Un dépassement de délai verrouille le pilote en erreur :
il ne rejoue pas automatiquement une commande dont l'issue est inconnue.
La composition reste activée avec des descripteurs vides même sans surcouche :
sur C37, cela sélectionne le lecteur RGB capable de maintenir plusieurs
lectures DDR en vol. Le mode direct historique a manqué des lignes pendant
le rendu et n'est pas utilisé par ce pilote.

L'interface est destinée à des jeux de confiance. Ce pilote n'est pas un pilote
DRM/Mesa/OpenGL ; l'accès brut n'est pas une isolation matérielle d'applications
non fiables. GPIO, I2C/ADS1115, manettes, audio et gadget USB MSC sous Linux
ne sont pas encore portés. Le CDC FPGA continue à transporter l'UART ; Linux
ne transforme pas ce port en contrôleur USB hôte.

## Particularités de cet A25

Les diagnostics réels identifient `mvendorid=0x31e`, `marchid=0x80000a25`,
`mimpid=0x160`. Une AMO en DDR bloque après invalidation du cache ; elle
réussit après une lecture préalable. Le port utilise :

- atomiques noyau génériques, protégées des interruptions, **un seul cœur** ;
- préchargement/barrière des cibles atomiques OpenSBI et musl ;
- caches actifs, BRPE désactivé, bit de conformité RISC-V activé ;
- synchronisation PTE/PMD pour le parcours des tables mémoire Andes ;
- absence d'accès à `mstatush`, non implémenté par cette révision ;
- service SBI privé de maintenance L1D pour les échanges CPU/GPU.

Le noyau active `STRICT_KERNEL_RWX`. L'alignement des grandes pages Sv32
agrandit l'image embarquée à environ 25 Mio ; le transit USB accepte 32 Mio.

Les binaires RV32IMA précompilés quelconques ne sont pas pris en charge.
Compiler les programmes fournis avec le wrapper `build/userbin/` reconstruit
par le port. L'API C11 `libatomic` générale n'est pas encore intégrée ; le
correctif amont est conservé en référence. Ne pas utiliser une AMO assembleur
brute en DDR dans un programme ajouté.

`pgprot_noncached()` ne suffit pas à rendre la mémoire GPU non cachée sur
ce RV32 sans PMA programmable. La synchronisation SBI fait explicitement
l'écriture et l'invalidation du cache avant et après les commandes GPU.
Une application ne doit pas écrire concurremment une surface utilisée par
le GPU. La lecture CPU d'une surface rendue intervient après le retour de
`PRODOCK_SUBMIT`. Le framebuffer Linux passe par une mémoire ombre distincte.

## Construction

Dépendances hôte : make, GCC hôte, Python 3.12+, patch, curl, dtc, QEMU RV32,
flex, bison et outils usuels de construction Linux. Le lanceur ILM emploie
le SDK Gowin AE350 déjà configuré dans `fw_console/Makefile`.

```sh
make -C linux all JOBS=4
make -C linux/uboot all JOBS=4
make -C linux sd-boot
make -C linux test
python3 linux/tests/test_boot_images.py
python3 linux/tests/test_orbital_api.py
python3 linux/tests/test_atomic_code.py
python3 linux/sd_package.py
```

Archives et SHA-256 : `sources.json`, `uboot/prepare.py`. Les sources extraites,
outils et binaires restent dans `linux/build/`, ignoré par Git. Les correctifs
ont leur provenance dans `PROVENANCE.md`. Une modification d'un correctif
appliqué arrête la construction : réextraire la source concernée dans un
répertoire propre au lieu de cumuler des patches différents.

La toolchain Bootlin compile le noyau. Le wrapper `build/userbin/` compile
les programmes RV32IMFDC/ILP32D avec la musl adaptée, sans génération
spontanée d'AMO. Le contrôle des exécutables liés vérifie les préchargements.

## Essai volatile depuis ax15

Copier `build/manifest.json`, `launch.bin`, `launch_usb.bin` et le fichier
`opensbi/platform/generic/firmware/fw_payload.bin` dans un dossier de paquet
sur ax15, en gardant cette arborescence. Copier les outils Python associés.

Le chargement direct, plus lent, utilise J-Link pour tout le paquet :

```sh
python3 tools/load_linux.py --pack linux/runtime_rN --out TESTS/linux_boot_rN
```

Le chemin rapide exige le firmware **USBDISK R4/C4b** déjà qualifié :

```sh
python3 tools/load_ilm.py --bin linux/usbdisk_c4b.bin --entry 0xa000000c \
  --expect 'USBDISK READY R4' --out TESTS/linux_disk_rN
python3 tools/stage_linux.py --pack linux/runtime_rN --out TESTS/linux_stage_rN
python3 tools/load_linux.py --pack linux/runtime_rN --staged --out TESTS/linux_boot_rN
```

Pour les essais successifs après un noyau Linux, le rechargement SRAM de
C37 doit précéder le nouveau firmware bare-metal. Le script de qualification
`TESTS/linux_20261009/fresh_load.py` applique les mêmes contrôles de
`load_ilm.py`, puis détache uniquement l'interface PC `usb-storage` avant le
chargement. Exemple sur l'arbre de validation d'ax15 :

```sh
python3 TESTS/linux_20261009/fresh_load.py \
  --fs tang/impl/gpu_sdusb_c37/impl/pnr/console_gpu_sdusb_c37.fs \
  --bin linux/usbdisk_c4b.bin --entry 0xa000000c \
  --expect 'USBDISK READY R4' --out TESTS/linux_fresh_rN
```

L'interface MSC du PC reste volontairement détachée pendant Linux ; le CDC
reste lié à `cdc_acm` en HS. Un rebranchement USB ou une nouvelle énumération
la réattachera côté PC. Linux ne sert pas encore la SD par USB MSC. Les essais
avec des resets USB répétés dans l'ancienne énumération ont perdu des données
CDC ; le rechargement propre a rétabli les transferts et leurs comparaisons.
Ce résultat ne constitue pas une qualification d'endurance des resets USB.

Le transfert rapide sélectionne explicitement la **DDR 32 Mio**, vérifie
le support et la capacité avant toute écriture, relit intégralement le
paquet puis libère le disque. Le lanceur copie depuis `0x08000000` et
recalcule le CRC. Aucun fichier de SD physique et aucune flash ne sont écrits.
Les deux chargeurs refusent de remplacer un firmware qui n'acquitte pas sa
pause/libération. Un noyau Linux en cours ne répond pas à ce protocole : ne
pas contourner ce contrôle pour le remplacer en marche.

## Paquet SD

`build/sd/PRODOCK/` contient `UBOOT.BIN`, `LINUX.BIN`, `LUMA.BIN`, `LUMA.DAT`,
`ORBITAL.BIN`, `ORBITAL.DAT`. Les images ont un en-tête de 40 octets avec
version, type, adresse/entrée, longueur, capacités GPU et deux CRC32.
U-Boot vérifie les types, plages et CRC avant chaque saut. CRC et SHA détectent
la corruption ; ce mécanisme n'est pas un démarrage signé.

Le script prépare seulement les fichiers locaux. Il ne formate et ne monte
aucun disque. Une copie sur SD physique reste une étape distincte.
U-Boot lit la FAT et la SD en lecture seule : initialisation à 400 kHz,
puis horloge choisie par MMC jusqu'à 20 MHz, avec transferts groupés par
blocs de 512 octets et accès FIFO de quatre octets pour les données.
La sélection peut aussi se faire au prompt avec `prodockboot linux`,
`prodockboot luma` ou `prodockboot orbital`.

Le premier étage téléchargeable est
`fw_console/build/linux_sd_boot/console_test.bin`, entrée `0xa000000c`.
Le compiler ne l'installe pas dans le FPGA. Ce premier étage réutilise le
transport SD bare-metal existant, dont certaines attentes matérielles ne
sont pas bornées ; une SD défaillante peut empêcher d'atteindre le menu.
Les nouveaux pilotes SPI Linux et U-Boot possèdent des délais bornés.

`sd_package.py` génère aussi `build/sd/uboot_ram.bin` et son manifeste pour
essayer U-Boot en RAM, avant toute installation de fichiers sur la SD :
`python3 tools/load_uboot.py --pack linux/build/sd --out TESTS/uboot_ram_rN`.
Le firmware résident doit acquitter sa pause ; ce chargeur ne remplace pas
un noyau Linux en cours sans rechargement préalable du FPGA.
