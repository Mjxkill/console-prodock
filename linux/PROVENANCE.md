# Provenance du port Linux Pro Dock

Le socle de construction reprend `../logic_analyser_wifi/ae350/linux`
(état lu le 9 octobre 2026), sans modifier ce dépôt. Les configurations et
la structure OpenSBI/Linux/BusyBox sont adaptées à la Pro Dock C37.
`linux/sources.json` fixe les archives amont et leurs empreintes SHA-256.

- Linux 6.12.112 : GPL-2.0, notices et licences par fichier dans l'archive.
- OpenSBI 1.6 : BSD-2-Clause ; adaptation `prodock.c` dérivée de `la16.c`.
- BusyBox 1.37.0 : GPL-2.0.
- musl 1.2.5 reconstruite : MIT, avec adaptation LR/SC propre à l'AE350.
- U-Boot 2025.10 : GPL-2.0-or-later, archive vérifiée par SHA-256 dans
  `uboot/prepare.py`.
- Toolchain Bootlin RV32 ILP32D musl stable-2025.08-1 : licences présentes
  dans l'archive (GCC, binutils, musl et autres composants).
- Pilotes Pro Dock : GPL-2.0-or-later ; UAPI avec Linux-syscall-note.
- Programme utilisateur et diagnostics de démarrage : MIT.

Le pilote SPI est écrit à partir du contrat ATCSPI200 déjà utilisé par
`fw_console/sd_ae350.c` et des définitions du SDK Gowin AE350 1.3.
Le protocole de carte est celui du pilote Linux amont `mmc_spi`.
Le port U-Boot ajoute un contrôleur SPI équivalent et un correctif limité
à cette cible pour appliquer l'horloge choisie par MMC ; la fonction amont
`dm_mmc_spi_set_ios` était vide dans cette version.
Le pilote GPU reprend l'ABI C37 documentée dans `ARCHI/GPU_*.md` ; il ne
réutilise pas le framebuffer SDRAM indirect de LA16. Les contrôles mémoire
s'exécutent dans le noyau avant la soumission au matériel.
Les modèles QEMU ne représentent ni l'AE350 ni les périphériques FPGA.

Les contournements du processeur proviennent du travail de Florent Kermarrec
([LiteX PR 463](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/463),
révision `889016988ac5bfc50219984e4a28c182b4dd286c`) :

- `patches/linux/` : atomiques génériques protégées des interruptions sur
  un seul cœur ; synchronisation des modifications PTE/PMD. GPL-2.0.
- `patches/musl/` : lecture et barrière avant chaque tentative LR/SC. MIT.
- `patches/opensbi/` : adaptation au code OpenSBI **1.6**, avec préchargement
  des atomiques, suppression des builtins qui contourneraient ce traitement,
  caches actifs, bit BRPE désactivé et conformité RISC-V activée. BSD-2-Clause.
- `patches/reference/` : correctifs OpenSBI/libatomic d'origine conservés
  pour comparaison, **non appliqués** par la construction. Le correctif GCC
  conserve sa licence GPLv3 avec exception de bibliothèque d'exécution.

Le blocage d'une AMO après invalidation du cache est reproduit localement
sur C37 ; le préchargement passe 1 024 AMO et 1 024 LR/SC avec invalidations.
Ces observations n'établissent pas un erratum constructeur général.

## Affichage partagé du 11 octobre 2026

L'interface fbcon tileblit et la disposition des cellules (caractère 8 bits,
premier plan 4 bits, fond 4 bits) suivent le pilote GPL
`../logic_analyser_wifi/ae350/linux/drivers/la16-fb.c`, lu comme référence.
`prodock-text.h` remplace ses accès aux registres texte LA16 par des atlas et
grilles DDR3 doublés, composés par le GPU Pro Dock existant. Les callbacks,
la synchronisation et le gestionnaire des dispositions sont propres au port
Pro Dock. La police est la VGA8x16 fournie par le noyau Linux épinglé ;
aucune nouvelle police externe n'est téléchargée.
