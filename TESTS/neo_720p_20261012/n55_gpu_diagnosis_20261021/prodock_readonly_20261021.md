# Pro Dock rallumée : inventaire sans accès carte

Relevé du 21 octobre 2026, vers 18:14–18:18 CEST (16:14–16:18 UTC), par SSH
sur `michael@ax15`. Aucun port série ou USB ouvert par la sonde ; aucune commande
envoyée à la carte, aucun accès JTAG, aucun fichier distant écrit.

## Présence matérielle observable côté PC

- Hôte `michael-AX15`, joignable, uptime 104 jours.
- FTDI `0403:6010`, SIPEED USB Debugger série `2023112818`, chemin USB `3-3.1`,
  bus 3/device 90, énuméré à 480 Mbit/s. Ses ports sont `ttyUSB0` et `ttyUSB1` ;
  leurs liens udev datent de 18:07 le 21 octobre.
- J-Link `1366:0105`, série `000506005083`, chemin `3-1`, bus 3/device 74,
  `ttyACM0`, énuméré à 480 Mbit/s.
- **Aucun périphérique SOFT-USB de VID 359f** dans l'inventaire USB et sysfs.
  `ttyACM0` est le J-Link et ne doit pas être utilisé comme console CDC FPGA.

Ces numéros concordent avec les sélections explicites des outils locaux
`tools/load_ilm.py`, `tools/load_linux.py` et `tools/check_gpu_reloads.py`.
Le débit 480 Mbit/s des programmateurs ne décrit pas le SOFT-USB absent.

Aucun processus JTAG, terminal série, test console ou Gowin pertinent n'a été
identifié dans la liste des processus. Aucun descripteur ouvert vers les ports
ou fichiers USB concernés n'a été trouvé parmi les processus inspectables.
154 tables de descripteurs de processus n'étaient pas lisibles : ce relevé
n'est pas une garantie exhaustive d'absence d'utilisateur du périphérique.

## Fichiers présents sur ax15

Arbre : `/home/michael/console-validation-20261001`, avec `tools`, `tang`,
`linux`, `TESTS` et `bitstreams`.

Le fichier
`tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs`
existe, mesure 41 688 834 octets et a le SHA-256
`fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`,
identique à la référence locale `tang/boards/prodock/reference.json`.
**Ce contrôle de fichier ne prouve pas le bitstream actuellement chargé.**

Paquets Linux trouvés directement sous `linux/` : `runtime_r1`, `runtime_r2`,
`runtime_r3`, `runtime_r4`, `runtime_r7`, `runtime_r8`, `runtime_r11`,
`runtime_r12`. Leurs huit manifests désignent la Pro Dock, mais aucun ne
contient une entrée NEBULA. Aucun payload déclaré n'a l'empreinte du manifeste
historique R17, `7d8cb19e0cb032cc73bc271172dae67e50354746e4ce27f529b5e00a08b41f4c`.
Aucun dossier `linux/runtime_r17` n'a été trouvé. Ce contrôle ciblé n'est pas
une recherche exhaustive de toute copie éventuellement présente ailleurs.

Les outils `load_linux.py`, `stage_linux.py`, `load_ilm.py`,
`check_linux_desktop.py`, `load_orbital.py` et `load_astrilla.py` sont présents.
`JLinkExe` est `/usr/bin/JLinkExe` ; `openFPGALoader` n'est pas dans PATH mais
existe dans `runtime/openFPGALoader` et `bin/openFPGALoader` de l'arbre.

## Possibilité de non-régression sans rechargement

La lecture des outils actuels montre :

- `check_linux.py` sans option de démonstration écrit des commandes système et
  `prodockctl info` sur un CDC identifié explicitement, à 480 Mbit/s ; il ne
  programme rien, mais exige un Linux déjà lancé et une console libre.
- `check_linux_desktop.py` modifie l'affichage, lance un jeu et change les
  dispositions. Il ne convient pas à une simple observation transparente.
- `check_nebula.py` exige explicitement Linux/NEBULA, un CDC libre et aucun jeu
  en cours ; il lance plusieurs scènes et manipule le clavier/dispositions.
- `check_nebula_endurance.py` lance une nouvelle partie et une démo finale.

**Aucun de ces tests n'a été lancé.** Le CDC nécessaire est absent, donc les
préconditions ne sont pas remplies. Un attachement JTAG ou un rechargement
pour retrouver la console dépasserait cette mission d'inventaire. L'état du
CPU, le logiciel en RAM, le bitstream chargé et la santé du GPU restent inconnus.
L'inventaire ne constitue pas une nouvelle validation matérielle Pro Dock.

## Lecture de statut autorisée ensuite, à 19:00 CEST

La tâche principale a ensuite autorisé une unique lecture JTAG non destructive
du statut de configuration, sans halt AE350 ni reset/reprogrammation FPGA.
Le programmateur Pro Dock a été identifié par son numéro `2023112818` et son
bus/adresse `3:90`. Le J-Link du processeur n'a pas été utilisé.

Le binaire openFPGALoader distant v1.1.1 a exactement la même empreinte que le
binaire local dont les sources ont été relues :
`101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873`.
Le chemin SVF de `main.cpp` sort avant la construction de la classe Gowin et
donc avant ses opérations de configuration. `--read-register` n'a pas été
utilisé : cette option standard est documentée pour Xilinx uniquement.

Le fichier SVF minimal a été fourni par un descripteur `memfd` en RAM, sans
création de fichier distant persistant. Il sélectionne l'instruction de lecture
`0x41`, attend six TCK, lit 32 bits en comparant uniquement `DONE_FINAL`, bit13,
puis sélectionne `NOOP` 0x02. Aucune instruction de configuration, effacement,
écriture ou rechargement n'est présente. L'initialisation du TAP JTAG n'est pas
une réinitialisation du FPGA ni du processeur.

Résultat : **IDCODE `0x0001081b`, GW5AST-138, IR8 ; `DONE_FINAL=1`**, comparaison
SVF réussie et code de sortie zéro, à 1 MHz. Le FPGA est donc configuré. Cela
n'identifie pas le bitstream actuellement chargé ; aucun USERCODE ni statut
complet n'est revendiqué, et Linux/GPU ne sont toujours pas testés. L'absence du
SOFT-USB ne démontre pas une SRAM FPGA vide après rallumage.

Preuves locales : `prodock_status_read_20261021/result.json` et
`prodock_status_read_20261021/read_done.svf`. Aucun autre accès à la carte n'a été
effectué après cette lecture.
