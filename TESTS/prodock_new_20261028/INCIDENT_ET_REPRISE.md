# Incident de ciblage J-Link et reprise de la première Pro Dock

## Contexte et responsabilité

Le 28 octobre 2026, la cible demandée pour la nouvelle installation était la
Pro Dock dont le programmateur porte le numéro **2025071717**. La Pro Dock
**2023112818**, qui exécutait FM4A sous Linux, devait continuer à fonctionner.

Le premier chargement FPGA visait correctement le nouveau programmateur.
En revanche, j'ai lancé le chargement Linux par le J-Link **506005083** sans
avoir établi à quelle carte son câble CPU était relié. Il était toujours relié
à la première carte. C'est mon erreur de ciblage, pas une panne spontanée du jeu.

Le journal montre le CPU arrêté dans Linux, puis un téléchargement vers
`0x10000000`. Ce téléchargement a été interrompu ; le lanceur ILM et son SetPC
n'ont pas été exécutés. L'étendue des écritures DDR éventuellement effectuées
n'est pas établie. Après reprise, un Oops Linux a été reçu sur la console de
l'ancienne carte, avec le PID du jeu. Le simple resume n'a pas rétabli le jeu.
Le FPGA de référence a donc été rechargé sur l'ancienne carte pour une reprise
à froid. Les états du jeu et sauvegardes présents uniquement en RAM ne sont
pas déclarés préservés.

## Identités physiques établies après l'incident

Sur `michael@ax15` :

| Carte | Programmateur | Console SOFT-USB | J-Link CPU |
|---|---|---|---|
| Première, restaurée | 2023112818, branche 3-7.4 | branche 3-7.3 | 506005083, association prouvée par nonce |
| Nouvelle, destinée au boot SD | 2025071717, branche 3-7.2 | branche 3-7.1 | aucune association nouvelle établie |

Les deux consoles utilisent le même iSerial firmware `11252024`. Le lien
`/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00` n'identifie
donc pas une carte de façon unique. Les contrôleurs de cette reprise emploient
le chemin physique `by-path` et les preuves de réénumération du FPGA.
Ces associations sont propres à ce câblage ; un déplacement de câble les invalide.

## Reprise vérifiée

- FPGA G22r0 exact :
  `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- Linux G3D1 : payload
  `0ff71bb9b7d44ce2f149ed6406d33c8497b45b8439c54b896621dedcd0c498b3`,
  release `6.12.112-prodock-luma3d-g3d1-r1`.
- Jeu FM4A : 16 640 496 octets, SHA source
  `6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7`,
  CRC32 complet `fa358bf4`.

Le chargement FPGA, l'association CPU/console, l'écriture/relecture du jeu
compressé en mémoire réservée et le boot Linux avec CRC sont vérifiés. Le jeu
compressé a été déposé avant Linux à `0x04000000`, dans la réserve GPU, sans
chevaucher la RAM Linux. L'extraction complète a ensuite passé ses deux CRC.
Le contrôle de progression après lancement passe dans
`recovery_evidence/game_01/result.json` : PID 92, démarrage au tick 84236,
compteur de présentations 0 → 32 → 107 → 185. Les compteurs d'erreurs,
d'underflow, de commandes invalides et de fautes restent nuls sur ces mesures.
Michael a ensuite confirmé visuellement : « Oui, le jeu est revenu ».
Le jeu est laissé en fonctionnement ; cette vérification courte ne constitue
pas un nouvel essai d'endurance.

Les chargements mémoire de reprise ont ajouté un garde avant écriture :
CPU en mode machine, SATP nul, PC dans la ROM/ILM de firmware, MPRV désactivé.
Huit cas locaux du garde passent. Une nonce écrite par l'UART via JTAG a
confirmé l'association CPU/console avant les téléchargements de reprise.
Le garde ne dispense pas d'identifier physiquement le câble : il ne faut pas
se reconnecter au J-Link de la première carte pour tester la nouvelle.

## Défaut de l'outil de récupération, corrigé séparément

Le premier `stage_reader` a été transféré et relu intégralement, puis a refusé
son mapping avec le code 9. La cause est vérifiable dans le noyau exact :
`mm/mmap.c` efface `VM_SHARED` pour un fichier ouvert sans `FMODE_WRITE`, alors
que le callback `gpu_mmap` impose ce drapeau. Le fixture QEMU sur fichier
ordinaire ne couvrait pas cette restriction du pilote personnalisé.

R2 change uniquement l'ouverture du périphérique en `O_RDWR`. Le mapping
reste `PROT_READ`, sans ioctl ni écriture GPU. Son ELF de 13 032 octets, SHA
`00bf58fbcf032f1c4c95f7c64cc0b85bb47c03b8f00dfb689de6a9ebc29534a0`,
a été reconstruit dans un nouveau fichier et relu intégralement avant exécution.
L'extraction sur carte retourne
`STAGE_FM4A_OK bytes=16640496 crc=fa358bf4`.

## Limites et éléments conservés

- Aucun formatage, écriture SD ou programmation persistante de flash dans
  cette reprise. Les chargements FPGA sont volatils.
- Les limites historiques de timing de G22r0 restent celles de la référence.
- Le progrès courant du jeu en RAM avant l'incident n'a pas été récupéré.
- Les scripts `*_initial_snapshot.py` conservent les commandes initiales
  fautives comme preuves ; ils ne constituent pas une procédure à réutiliser.
- Les journaux Oops, les résultats des essais refusés et les deux versions du
  lecteur sont conservés pour expliquer les échecs, sans les transformer en PASS.
- Le démarrage autonome SD de la nouvelle carte est une livraison distincte :
  FPGA configuré à l'allumage, puis chargeur, Linux et jeu lus depuis la SD.
  Il n'est pas validé par cette restauration RAM de la première carte.
