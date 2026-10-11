# Port Linux Pro Dock — preuves du 9 octobre 2026

État courant : **Linux R12, GPU et lectures SD passent sur carte** ; U-Boot
et son menu passent en RAM. Installation et lancements SD encore à effectuer.
Les sections suivantes conservent aussi les échecs et corrections antérieurs.
Référence FPGA **C37**,
SHA-256 `6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2`.
Pas de nouvelle synthèse ni changement d'horloge ; les compilations Gowin
des autres projets ne sont pas intervenues dans ces essais.

## Référence et périmètre

Le port du dépôt voisin `logic_analyser_wifi/ae350/linux` est une base
logicielle déjà compilée/testée sous QEMU ; ses documents ne revendiquent
pas un démarrage physique. Les pilotes LA16 ne correspondent pas aux
périphériques C37. Le port console fournit son DTB, SPI/SD, GPU/fbdev,
OpenSBI et lanceurs, avec Linux et les démos bare-metal en modes séparés.

## Tests logiciels

- Linux RV32, OpenSBI, BusyBox, musl et U-Boot compilés dans `linux/build/`.
- QEMU virt : démarrage du vrai noyau/initramfs, six tests KUnit des plages
  GPU, validation de l'ABI utilisateur et test threads/fork/mmap/mprotect.
- Décodeur C d'images de boot : six types, CRC, octets d'en-tête altérés,
  mauvaises cibles, tailles tronquées/allongées, bornes et débordements.
- Validateur C GPU contre les scènes ORBITAL existantes : **51 poses,
  54 626 commandes**, avec correction de la validation des tilemaps à une
  seule rangée. Cette preuve valide l'acceptation de l'API, pas le rendu
  Linux sur le matériel.
- Analyse des binaires liés : noyau sans AMO/LR natifs ; OpenSBI 8,
  BusyBox 24, prodockctl 12, test runtime 37 et U-Boot 4 sites AMO/LR,
  précédés d'une lecture de la même cible et d'une barrière.
- Le chargeur conserve le refus des identités inconnues et des pauses sans
  acquittement complet ; ses sept tests passent après ajout de répétitions
  idempotentes de la demande de pause.

## Préflight et découverte des contraintes processeur

`linux_preflight_20261009_r1` : MISA `0x4094312d`, mode S présent,
SATP accepte Sv32, aucun trap, timer PLMT mesuré à environ **80 MHz**.
Ce test de SATP seul ne suffisait pas à démontrer un démarrage Linux.

`linux_boot_20261009_r1` : paquet téléchargé et CRC correct, mais arrêt
sur AMOSWAP à `0x07c00032` avec caches désactivés. Aucun Linux démarré.

`linux_atomic_20261009_r1` : AMO et LR/SC réussissent après écriture d'une
ligne en cache. `linux_boot_20261009_r2` reste cependant bloqué sur la
première AMO, malgré les caches actifs. `linux_atomic_20261009_r2` isole
la différence : après writeback/invalidation, l'AMO ne progresse plus.

`linux_atomic_20261009_r3` : avec lecture/barrière avant l'opération,
**1 024 AMO + 1 024 LR/SC passent**, chaque essai suivant une invalidation.
Le correctif logiciel est adapté du port LiteX cité dans `linux/PROVENANCE.md`.

`linux_boot_20261009_r3` franchit les atomiques, puis entre dans le handler
d'exception précoce. `linux_atomic_20261009_r4` confirme : cause=2,
MEPC=`0x07c000c6`, MTVAL=`0x3102b073` (accès CSR mstatush absent).
Identité : `mvendorid=0x31e`, `marchid=0x80000a25`, `mimpid=0x160`.
OpenSBI doit respecter l'ISA privilégiée 1.11 de cette révision.

Le bit PMA programmable est nul (`MMSC_CFG=0x2007f039`). Les échanges
CPU/GPU utilisent donc une maintenance explicite L1D par SBI, pas une
promesse de mémoire non cachée obtenue par un attribut PTE.

## Premier démarrage matériel

`linux_boot_20261009_r4` : **OpenSBI 1.6 et Linux 6.12.112 démarrent**.
Le noyau utilise Sv32, détecte 384 Mio de RAM allouable, utilise le timer
80 MHz, initialise `/dev`, puis exécute `/init`. Le pilote GPU détecte
C37, enregistre fb0 800×480 RGB565 et `/dev/prodock-gpu`.

Limites découvertes dans ce premier démarrage :

- Réservation du firmware déclarée deux fois, par le DTB et OpenSBI :
  supprimée du DTB source, OpenSBI conserve ses réservations.
- Le contrôleur SPI n'avait pas de lien OF pour énumérer son enfant MMC :
  ajout de `ctlr->dev.of_node`.
- La console ttyS0 s'arrête après une partie du message READY. Le noyau
  attend dans `arch_cpu_idle`. La source UART9 est en attente dans le PLIC,
  avec priorités/masques désactivés. Une configuration manuelle de diagnostic
  par J-Link n'a pas rendu le shell utilisable. Les interruptions S-mode ne
  sont pas qualifiées ; essai suivant avec le chemin timer 8250 amont.
- Lors du retour au firmware C37, le PC a effectué des resets USB répétés.
  Le pilote usb-storage de la seule interface MSC a été détaché pour isoler
  la console CDC pendant les essais Linux. Le mode HS reste négocié.

**READY seul ne valide donc ni le shell interactif, ni la SD, ni le rendu
GPU sous Linux.** Les essais suivants doivent établir ces points séparément.

## Transfert rapide des paquets

Le firmware USBDISK R4/C4b qualifié écrit exclusivement dans son disque
DDR, à partir du secteur 32768 (adresse `0x09000000`). Support DDR,
capacité de 65536×512, état SERVING et HS sont exigés avant WRITE.

`linux_stage_20261009_r2b` : 7 311 016 octets transférés en 1,235 s,
relus en 0,957 s, comparaison intégrale correcte, aucune erreur de nettoyage.
Le lanceur refait un CRC après copie à `0x07c00000`. Les transferts r3/r4
passent aussi. Aucune écriture sur carte SD physique.

## Démarrage SD et limites de livraison

Premier étage SD : 20 936 octets en ILM, compilation réussie. U-Boot propose
Linux/LUMA/ORBITAL et conserve la SD en lecture seule. Les quatre atomiques
du début d'U-Boot sont préchargées, comme OpenSBI. Les six fichiers sont
préparés dans `linux/build/sd/PRODOCK/` avec leurs en-têtes et manifeste.

Ces fichiers n'ont pas encore été copiés sur la carte SD physique. Le menu
et le premier étage n'ont pas encore passé un essai complet sur carte. Le
bitstream C37 archivé conserve son démarrage historique. Pas de flash écrite.

## R8–R12 : pilotes et système qualifiés sur la carte

R8 avec UART sans IRQ passe le démarrage et détecte la SD, mais l'ancienne
énumération USB perd des caractères et blocs de journaux. Un essai J-Link
transfère l'image en **415,5 s** avec CRC correct, sans corriger la liaison.
Les compteurs matériels confirment 2 430 commandes GPU, mais les réponses
tronquées ne permettent pas de valider ce premier test utilisateur.

R9 repart du **même C37 en SRAM**, détache uniquement l'interface MSC côté
PC avant de remplacer le firmware et conserve le CDC HS. Le transfert DDR,
la relecture complète, le boot, le shell, le test runtime et les pixels GPU
passent, avec des journaux complets. Aucune modification RTL n'est attribuée
à cette récupération ; les cycles prolongés de reset USB restent à qualifier.

R11 ajoute `PROC_SYSCTL` pour vider le cache de blocs entre deux lectures
SD et `STRICT_KERNEL_RWX` pour protéger les sections noyau. Sur RV32/Sv32,
l'alignement augmente l'image OpenSBI+noyau à environ **25 Mio**. Le transit
USB utilise désormais les 32 Mio du disque DDR à `0x08000000`, secteur 0.
La copie est croissante vers `0x07c00000`, donc sûre malgré le recouvrement
(destination inférieure à la source). Relecture USB intégrale puis CRC du
lanceur vérifient les deux étapes. Aucun secteur SD n'est écrit.

Le contrôle des compteurs a détecté un défaut que le contrôle des pixels
seul ne révélait pas : R11 rendait correctement en DDR mais manquait
**20 857 lignes LCD** sur la démonstration de 90 images. Le pilote désactivait
la composition sans surcouche, ce qui sélectionnait le lecteur RGB historique,
non pipeliné (`gpu_scanout.v`/`gpu_rgb_reader.v`). R12 active la composition
avec des descripteurs vides, y compris pour fbdev, comme le font les démos
existantes. Aucun changement FPGA n'a été nécessaire.

`linux_check_20261009_r12/result.json` : **PASS** sur carte :

- Linux 6.12.112 à 800 MHz, Sv32, UART temporisée et timer 80 MHz ;
- deux threads, 20 000 incréments protégés, 32 essais fork/mmap/mprotect/COW ;
- GPU : **2 430 commandes**, **384 000 pixels** exacts, **0 erreur**,
  **0 sous-alimentation LCD** avant/après, restauration fbdev ;
- SD SC16G : **31 116 288 secteurs de 512 octets** ; lectures des secteurs
  0, 1, 8191 et 31 116 287 deux fois, avec `drop_caches=3` entre lectures ;
  mêmes SHA-256 pour chaque paire, aucun accès en écriture ;
- volume FAT32 monté **en lecture seule** sous R11 : `CONSOLE.TST` de
  262 144 octets, puis démontage réussi (`linux_sd_ro_list_r11.log`).

R12 : écriture du paquet DDR **4,315 s**, relecture **3,333 s** et chargement
ILM J-Link **2,3 s**. La durée supplémentaire de copie/CRC/démarrage est
consignée dans le résultat du chargeur. Les compteurs et images concernent
la démo de validation Linux ; ce n'est pas encore un port de LUMA/ORBITAL
comme processus Linux, ni une qualification de tous les opcodes sur matériel
à travers ce nouveau pilote.

La version finale du test utilise `od -v -b`, disponible dans la configuration
BusyBox minimale, et vérifie les offsets de chaque ligne, la taille de
512 octets et le code de retour. Une troncature série est un échec du test.

## U-Boot en RAM et préparation de l'installation

Le lanceur `uboot_ram.c` vérifie le CRC du programme chargé par J-Link à
`0x06000000`, puis entre dans U-Boot en M-mode. Il ne lit/écrit aucun fichier
SD lui-même. `tools/load_uboot.py` vérifie aussi les empreintes et l'en-tête.

- R1 s'arrête faute de timer : `ANDES_PLMT_TIMER`, symbole Kconfig sans
  prompt, n'était pas activé par sa ligne defconfig. La cible le sélectionne
  maintenant explicitement. `test_uboot_config.py` contrôle les options
  effectives, dont le timer et l'absence d'écriture MMC/FAT dans U-Boot.
- R2 démarre le menu **Linux / LUMA sans Linux / ORBITAL sans Linux**.
  `fatls mmc 0:0` retrouve `CONSOLE.TST`. Les 262 144 octets sont lus en
  29 448 ms (7,8 Kio/s), CRC32 **18210e0c**.
- R3 remplace le transport octet par octet par des blocs de 512 octets avec
  accès FIFO fusionnés, et applique l'horloge MMC (initialisation 400 kHz,
  jusqu'à 20 MHz ensuite). Même fichier et CRC, **2 856 ms, 88,9 Kio/s**.
  Ce débit reste une limite de ce premier chargeur : le noyau d'environ
  25 Mio peut demander plusieurs minutes à charger depuis la SD.

L'entrée Linux retourne proprement au prompt lorsque `/PRODOCK/LINUX.BIN`
est absent. Ces essais qualifient U-Boot et sa lecture FAT32 en RAM, pas
encore les trois lancements depuis leurs fichiers physiques.

`linux/build/sd/PRODOCK/` et sa copie sur ax15
`/home/michael/console-validation-20261001/linux/sd_r12_final/` contiennent
les six images (35 030 836 octets) et un manifeste SHA-256. Le script
`tools/install_linux_sd.py` :

- vérifie toutes les images avant accès au matériel ;
- exige USB 359f:2011, série 11252024, HS, capacité et secteur FAT qualifiés ;
- ne formate pas et refuse un dossier PRODOCK/PRODNEW déjà présent ;
- crée seulement les six fichiers dans un nouveau dossier temporaire,
  les relit, puis renomme ce dossier PRODOCK ;
- vérifie que CONSOLE.TST conserve son contenu, démonte et remonte en
  lecture seule pour contrôler la destination finale ;
- demande root uniquement pour monter/démonter le volume sur ax15.

Le mode `--check-package` a passé sur le paquet final. L'installation
physique et les démarrages SD restent à effectuer ; aucune flash n'a été
écrite et le bitstream archivé C37 conserve son firmware initial.

Préparation hôte terminée : USBDISK R4 sert la SD en HS, l'interface MSC
est réattachée et ax15 expose `/dev/sdc`, série 11252024, 14,8 Gio, non monté.
Le paquet final a aussi passé `--check-package` sur ax15. La commande
`sudo -n ... --check-package` confirme que sudo exige une authentification ;
la commande d'installation complète a été transmise à l'utilisateur. Aucun
mot de passe n'est demandé à l'assistant. Tant que cette étape n'est pas
exécutée, aucun fichier `/PRODOCK` n'est présent sur la SD.
Le premier étage est prêt sur ax15 sous `linux/sd_boot_r1.bin` ; le test de
boot SD devra détacher de nouveau MSC après démontage, puis exiger
l'acquittement de libération du firmware USBDISK avant de le remplacer.
