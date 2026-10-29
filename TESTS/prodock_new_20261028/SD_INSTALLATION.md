# SD de la nouvelle Pro Dock — installation du 28 octobre 2026

## Autorisation et cible

Michael a confirmé que la SD présente dans le lecteur de ce PC était celle
prévue pour la nouvelle Pro Dock `2025071717`, puis a demandé explicitement
« non efface tout ». Son ancien système ext4 et le fichier `soma.img` ont
donc été supprimés par reformatage, sans sauvegarde demandée. Il ne s'agit
pas d'une procédure d'effacement sécurisé de tous les secteurs.

Identité contrôlée avant les écritures : lecteur USB `000000001532`, branche
`3-4.4.4`, disque `/dev/sdc`, numéro de changement de média `159`,
31 267 487 744 octets. Les autres disques et les deux Pro Dock n'ont pas été
utilisés par cette opération.

## Paquet installé

- FAT32 sur le support entier, disposition « superfloppy » également testée
  sur l'image locale. Le chargeur FatFs et le script Linux acceptent cette
  disposition ; aucune partition ext4 n'est nécessaire pour cette version.
- Manifeste du paquet :
  `10b0ee5d77919f492bef371427d5849010ead80e9be7ded10089772d55b05b43`.
- Linux : `6.12.112-prodock-luma3d-g3d1-sdoptin-r1`, avec démarrage du jeu
  explicitement activé dans ce candidat Pro Dock.
- Jeu **CM1**, incluant les glissements des cartes : 16 649 200 octets,
  SHA `a8485ce6d5e34ed46617a2b663278f14333fd20ee47396198d4296e087b76ebd`.
- Répertoire `PRODOCK` : `UBOOT.BIN`, `LINUX.BIN`, `LUMA.BIN`, `LUMA.DAT`,
  `ORBITAL.BIN`, `ORBITAL.DAT`, `LUMA3D.ELF`, `GAME.SHA`.

## Contrôles et résultat

Le contrôleur `prepare_sd_media.py` vérifie les empreintes de l'installateur
et de chaque source avant de modifier la carte. Sept identités incorrectes
ont été rejetées lors des tests locaux. L'installation de fichiers est faite
par le compte utilisateur, sur le volume monté explicitement par le contrôleur.

Après synchronisation et démontage : purge des buffers, vérification FAT sans
correction, remontage en lecture seule et relecture complète des huit fichiers.
Chaque taille et SHA-256 correspond au manifeste. La carte est ensuite
démontée proprement. **Installation et relecture matérielles PASS** dans
`sd_media_01/result.json` ; les commandes et sorties sont conservées à côté.

Le jeu CM1 est validé par tests logiciels et captures, pas encore mesuré sur
cette Pro Dock. L'installation SD ne prouve pas le boot autonome : la nouvelle
carte doit encore recevoir le FPGA avec chargeur SD, puis être testée avec
cette SD, y compris après coupure d'alimentation. Aucun FPGA ni flash n'a été
programmé par l'installateur SD. La première Pro Dock conserve son jeu FM4A.
