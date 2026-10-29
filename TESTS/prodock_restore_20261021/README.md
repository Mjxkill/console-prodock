# Restauration Pro Dock — 21 octobre 2026

Restauration demandée par l'utilisateur après remise sous tension de la Pro Dock.
Les essais Neo restent séparés ; aucun bitstream Neo n'est chargé sur la Pro Dock.

## Identités restaurées

- Hôte : `michael@ax15`, répertoire `/home/michael/console-validation-20261001`.
- Pro Dock : FTDI `2023112818`, J-Link `506005083`, SOFT-USB `11252024`.
- FPGA : **G22r0**, SHA-256 `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- Linux et NEBULA : **paquet R17 d'origine**, sans reconstruction.
- Chargements en SRAM FPGA, ILM et DDR uniquement. Aucune écriture sur la SD
  physique ni dans la flash. La SD reste non montée.

## Sauvegarde binaire retrouvée

Le dossier local `linux/build/golden_nebula_r17` contient les 14 fichiers exacts
du paquet historique : noyau, OpenSBI, ressources, applications et lanceurs.
Son manifeste est identique à `TESTS/nebula_20261012/r17_manifest.json`.
Les tailles et SHA-256 de chaque binaire correspondent à ce manifeste ; le
payload décompressé est également identique à l'image OpenSBI/Linux originale.

L'archive `r17_runtime.tar.gz` conserve ces binaires ; SHA-256 :
`7c4467d19b6ba0d666799d85ad22eeaaa668bb1fb02b92693ec5f3771cb247e8`.
Le fichier `restoration_manifest.json` recense les 14 empreintes. Le dossier
de destination sur ax15 est `linux/restored_nebula_r17_20261021`.
La vérification après copie compare aussi le bitstream et le chargeur USBDISK.

Cette découverte complète l'archive de sources
`bitstreams/prodock_r17_sources_b2b1ba8.tar.gz`. La métadonnée antérieure
`linux_r17_binary_archive_available=false` décrit l'état avant cette découverte ;
elle ne doit pas servir à conclure que le paquet R17 est introuvable.

## Procédure

Sur ax15, depuis le répertoire de validation :

```sh
python3 tools/load_linux_disk.py \
  --fs tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs \
  --bin linux/usbdisk_c4b.bin --entry 0xa000000c \
  --expect 'USBDISK READY R4' --out TESTS/prodock_restore_20261021/disk

python3 tools/load_linux.py \
  --pack linux/restored_nebula_r17_20261021 --packed --jtag-speed 4000 \
  --out TESTS/prodock_restore_20261021/boot

python3 tools/check_linux.py --runtime --demo --sd \
  --out TESTS/prodock_restore_20261021/system
```

Les répertoires de résultat sont uniques : ne pas relancer ces commandes en
écrasant les preuves. Chaque outil doit avoir terminé avant d'ouvrir à nouveau
le port console ou JTAG de cette carte.

## Résultats matériels

- Copie : 14 fichiers et bitstream vérifiés sur ax15.
- FPGA chargé, USB réénuméré en HS **480 Mbit/s**.
- Firmware USBDISK R4 : cœur **800 MHz**, SD détectée.
- Linux **6.12.112-prodock** démarré ; CRC du payload vérifié sur la carte.
- Démarrage SD : première tentative en erreur `-110`, puis détection réussie
  de la carte **SC16G, 31 116 288 secteurs**. Cette reprise reste consignée.
- Linux : `threads=2`, 20 000 incréments ; 32 cycles fork/mmap/mprotect : PASS.
- GPU : **384 000 pixels** vérifiés, **2 430 commandes** exécutées exactement ;
  aucun défaut ni underflow.
- SD : secteurs **0, 1, 8191 et 31 116 287**, deux lectures de chacun après
  vidage des caches Linux : contenus identiques. Ce contrôle ne couvre pas
  l'intégralité de la carte.
- NEBULA : les trois CRC framebuffer et les neuf sommes de sortie LCD
  correspondent aux références (trois poses, trois lectures par pose).
- Benchmarks de 600 images : **47,71 FPS plein écran**, **45,06 FPS partagé**.
- Commandes clavier, nova, pause, changement d'affichage, sortie Q et SIGINT :
  PASS, shell récupéré. Modes partagé, console et jeu : PASS.
- Endurance : **10 000 images / 226,056 s / 44,24 FPS**,
  **213 740 commandes**. Les compteurs d'images et de commandes correspondent
  exactement à l'exécution ; jusqu'à **39 sprites et huit couches**.
- Aucun défaut GPU, underflow, rejet de commande ou erreur de sprite pendant
  ces contrôles ; aucune lecture série rejetée dans les deux campagnes NEBULA.
- État laissé : **NEBULA en démonstration automatique plein écran**, Linux
  démarré, console CDC libérée. Le test d'endurance confirme que les compteurs
  avancent de nouveau après lancement de cette démonstration.

Preuves : [démarrage](boot/result.json), [système/GPU/SD](system/result.json),
[NEBULA](nebula/result.json), [endurance](endurance/result.json).
Les journaux bruts sont conservés à côté de chaque résultat, sur ax15 et dans
ce dossier. Les scripts de contrôle n'ont pas été modifiés pour cet essai.
L'arrêt entre les deux campagnes est tracé par `stop_test_demo.json` ; seul
le PID NEBULA laissé par la première campagne a été arrêté.

Cette campagne revalide **la référence binaire G22r0/R17**. Elle ne qualifie
pas les modifications ultérieures du code de travail pour la Pro Dock.
Les 11 groupes locaux des deux profils et les diagnostics Neo constituent
des campagnes distinctes.

## Accès après restauration

Sur ax15, console série à 115200 bauds :

```sh
python3 -m serial.tools.miniterm /dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00 115200
```

Depuis le shell Linux, `prodockctl layout split` affiche le jeu, la console
et le tableau de bord. `prodockctl layout game` rétablit le jeu plein écran.
Pour arrêter la démonstration puis jouer : `kill $(cat /tmp/nebula.pid)` puis
`nebula`. Les chargements restent volatils : un arrêt électrique nécessite
un nouveau chargement.

## Limites conservées

La restauration de la référence ne ferme pas son timing : G22r0 avait un
setup de **−0,564 ns / 9 violations**. Les duplications CDC observées dans les
essais historiques restent documentées dans `TESTS/NEBULA_20261012.md`.
Les nouveaux résultats matériels doivent distinguer GPU, mémoire, transport
USB et SD ; un rendu correct ne démontre pas à lui seul leur intégrité globale.
