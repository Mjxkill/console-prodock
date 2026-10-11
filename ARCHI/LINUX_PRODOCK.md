# Linux Pro Dock : architecture et ABI

Le mode partagé et le terminal matériel ajoutés le 11 octobre sont décrits
dans [LINUX_AFFICHAGE_PARTAGE.md](LINUX_AFFICHAGE_PARTAGE.md). Ils remplacent
le framebuffer texte à copie différée décrit historiquement ci-dessous et
réservent les 2 derniers Mio de la fenêtre graphique au gestionnaire d’affichage.

Port du 9 octobre 2026, sur FPGA C37 et A25 à 800 MHz. Le socle du dépôt
`../logic_analyser_wifi` sert de référence logicielle ; ses registres FPGA,
son framebuffer SDRAM et ses broches ne sont pas repris.

## Chaîne de démarrage

Deux chemins chargent le même OpenSBI avec noyau/initramfs incorporé :

1. Essais volatiles : firmware USBDISK → transfert vérifié dans le disque DDR
   → petit lanceur ILM J-Link → copie et CRC → OpenSBI → Linux.
2. Démarrage depuis fichiers SD : premier étage ILM/ITCM → U-Boot → menu
   Linux/LUMA/ORBITAL → vérification des images → exécution du mode choisi.

Le premier étage n'est pas incorporé au bitstream C37 archivé. Son futur
build FPGA devra conserver les contraintes, satisfaire le timing et être
qualifié sur carte. Aucune flash n'est écrite par les outils de ce port.

## Carte mémoire

| Début | Fin exclue | Usage |
|---|---|---|
| `0x00800000` | `0x06000000` | Réserve graphique de 88 Mio, hors allocateur Linux |
| `0x00800000` | `0x01800000` | 16 emplacements historiques de 1 Mio |
| `0x01700000` | `0x017BB800` | Pixels RGB565 de `/dev/fb0`, page 15 |
| `0x04000000` | `0x04800000` | Ressources LUMA, limite du chargeur |
| `0x05000000` | `0x05800000` | Ressources ORBITAL, limite du chargeur |
| `0x06000000` | `0x06800000` | Fenêtre initiale U-Boot |
| `0x07000000` | — | DTB transmis au noyau |
| `0x07C00000` | `0x08000000` | OpenSBI et son espace réservé |
| `0x08000000` | `0x20000000` | 384 Mio allouables à Linux, moins noyau/réserves |
| `0x08000000` | `0x0A000000` | Zone USB de transit avant Linux, 32 Mio maximum |
| `0x10000000` | `0x12000028` | Tampon de lecture U-Boot avant Linux |
| `0xA0000000` | `0xA0010000` | Application ILM téléchargée |

Les fenêtres de transit recouvrent la future RAM Linux, mais ne sont utilisées
qu'avant son démarrage. Le lanceur copie en ordre croissant de 128 Mio vers
124 Mio : la destination est inférieure à la source, ce qui permet leur
recouvrement sans écraser une donnée restant à lire. Les trois chemins
acceptent un paquet Linux de 32 Mio maximum. Le transit USB remplace le
contenu du disque DDR volatile, après vérification du support et de sa capacité.

## Pilotes

`prodock-spi.c` possède ATCSPI200 `0xF0F00000` et GPIO0 de
`0xF0700000` (CS SD). Il remet les FIFO à zéro, utilise le duplex complet
aussi en lecture seule pour transmettre `0xFF` sur MOSI, borne les attentes
et transmet les erreurs à SPI/MMC. `mmc_spi` amont gère les commandes SD,
les CRC et les périphériques de blocs. Aucune application bare-metal ne
possède le SPI simultanément. L'initramfs ne monte pas la SD automatiquement.

`prodock-gpu.c` possède l'afficheur `0xE9000000`, l'accélérateur
`0xE9001000` et la réserve DDR. Il contrôle les identifiants et les capacités
`0x1FF` avant d'enregistrer ses interfaces. Le LCD et les accélérations
restent les mêmes circuits que ceux des démos bare-metal.

Le framebuffer est une image ombre en RAM Linux. Les modifications fbcon,
write et mmap sont recopiées dans la page GPU par un travail différé, avec
maintenance explicite du cache. Le rafraîchissement est limité à 20 Hz et
copie actuellement toute l'image ; une optimisation par rectangles reste
possible. Ce chemin n'assure pas une présentation atomique de la console
texte. Les jeux utilisent la présentation GPU au retour vertical.

Même sans surcouche, le pilote active la composition avec une table vide.
Sur C37, `gpu_rgb_reader.pipelined` dépend de ce bit. Le chemin direct
historique attend chaque réponse DDR avant la lecture suivante et perd des
lignes sous charge. R11 avait 20 857 sous-alimentations sur 90 images ; R12
conserve le lecteur rapide et en mesure zéro pour le même rendu.

## ABI accélérateur 1

L'en-tête partagé est `linux/drivers/prodock-uapi.h`. Les structures utilisent
des entiers de largeur fixe, sans pointeur utilisateur embarqué.

| Opération | Contenu |
|---|---|
| INFO | ABI, capacités, DDR, dimensions, DONE, erreurs, sous-alimentations, image, somme LCD, état de faute |
| SUBMIT | De 1 à 64 commandes de huit mots, validation complète avant émission |
| PRESENT | Fond, pas, format, activation, 16 descripteurs de couches, 64 de sprites |
| PALETTE | 256 couleurs RGB24, indépendantes de la transaction vblank |
| FONT | 4 096 octets de police |
| mmap | Décalage relatif à `0x00800000`, seulement dans les 88 Mio réservés |

Un seul fichier ouvert possède l'accélérateur. L'ouverture exige
`CAP_SYS_RAWIO` et suspend fbcon ; la fermeture restaure l'affichage de la
console. Les VMA conservent leur référence de fichier jusqu'à leur suppression.
La palette n'est pas échangée atomiquement avec les tables de composition.
Les appels SUBMIT sont synchrones ; la différence DONE est traitée modulo
65 536. Tout timeout après émission est une faute persistante, sans rejeu.

Les surfaces/atlas sont contrôlés en 64 bits pour éviter les débordements
d'adresse. Les opcodes historiques référencent leurs emplacements fixes ;
les adresses V1 et les descripteurs sont bornés à la réserve. Le propriétaire
root reste responsable de l'ordre logique, de l'exclusivité CPU/GPU des
surfaces et du budget de composition. L'ABI n'expose aucun registre MMIO brut.

## Cache, atomiques et mémoire virtuelle

La révision A25 présente une absence de progression des AMO à froid,
reproduite par les diagnostics ILM. Le simple réglage MCACHE_CTL=3 ne suffit
pas. Le noyau mono-cœur utilise les atomiques génériques avec protection des
interruptions ; OpenSBI utilise des lectures/barrières avant ses AMO et LR/SC ;
musl répète ce préchargement à chaque tentative LR/SC. Le contrôle du binaire
lié rejette une AMO/LR dépourvue de ce préchargement dans le logiciel fourni.
Le `sc.w` isolé du retour d'exception Linux efface une réservation : il ne
sert pas de primitive de lecture-modification-écriture.

BRPE reste désactivé et la conformité RISC-V est activée suivant le port
LiteX cité dans `linux/PROVENANCE.md`. PTE et PMD sont synchronisées suivant
le contournement Andes 2X. Le CSR `mstatush` est absent sur cette révision
(privileged ISA 1.11) ; OpenSBI ne tente pas d'effacer MDT dans ce registre.

La PMA programmable n'est pas implémentée (`MMSC_CFG.PPMA=0`). Le service
SBI privé Andes EID `0x0900031E` propose FID `0x101` (signature `0x50444301`)
et FID `0x100` (fences et writeback/invalidation L1D, commande CCTL 6).
Le pilote GPU refuse de se charger sans ce service. Une simple PTE dite
« non cachée » ne constitue pas une garantie suffisante sur ce RV32.

## Limites à qualifier

- Livraison des interruptions PLIC en mode superviseur ; l'UART utilise
  provisoirement le chemin de scrutation temporisée du pilote 8250 amont.
- Débits SD, retrait à chaud et écritures physiques : aucune qualification
  en écriture ne doit être déduite des tests de lecture.
- API générale libatomic/C11, exécutables tiers, SMP, pilotes GPIO/I2C/audio/
  manettes et gadget MSC Linux : non livrés par cette première étape.
- Démarrage électrique autonome, menu SD sur carte et retour depuis Linux
  vers une démo : la présence de sources compilables ne vaut pas validation.
