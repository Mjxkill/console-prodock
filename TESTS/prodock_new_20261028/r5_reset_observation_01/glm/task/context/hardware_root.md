# Deuxième Pro Dock : vérification de communication du 29 octobre 2026

## Objectif et environnement

Vérifier à distance la communication du candidat de démarrage SD R5 et la
comparer à G22r0, sur **la seule Pro Dock 2025071717**, connectée à ax15.
Programmateur 3-7.2 ; SOFT-USB 3-7.1. La première Pro Dock 2023112818,
sa console 3-7.3 et sa sonde CPU ne sont pas utilisées par ces essais.

Le verrou `/tmp/prodock-diagnostic.lock` couvre chaque opération matérielle.
Tous les chargements sont en SRAM. Aucun accès au JTAG CPU, aucune écriture
SD et aucune écriture flash. L'utilisateur est éloigné : l'image LCD n'est
pas vérifiée visuellement.

## Versions exactes

| Bitstream | SHA-256 |
|---|---|
| G22r0 protégé | `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f` |
| R3, ancienne ROM | `5b516ea97edc04b64a28c5364743ed149216a4359b9e23cc0130e2e8fa7d6859` |
| R5, ROM SD vérifiée | `24d6bfbc364aec025e9970ccfb0ab40463f1f576c153bd4c64313f5a3a551c2a` |

## Procédure et résultats

Charger le bitstream avec `load_sd_candidate.py`, ciblant explicitement le
numéro du nouveau programmateur. Attendre une nouvelle énumération du seul
port 3-7.1. Le bit DONE_FINAL prouve ici la fin annoncée par le programmateur,
pas le fonctionnement du firmware.

| Ordre / preuve | Configuration | USB observé |
|---|---|---|
| `sram_boot_01` — R5, 120 s | Terminée | Aucun |
| `g22_link_control_01` — G22r0, 60 s | Terminée | HS 480 Mbit/s, adresse 108 |
| `sram_boot_02` — R5, 120 s | Terminée | Aucun |
| `r3_old_rom_link_control_01` — R3, 60 s | Terminée | Aucun |
| `g22_restore_01` — G22r0, 60 s | Terminée | HS 480 Mbit/s, adresse 109 |

Après chacun des deux chargements G22r0, `probe_new_link.py` lit dix fois le
descripteur USB puis envoie le seul octet `?` au firmware diagnostic. Chaque
essai reçoit une réponse de **87 octets**, contenant `MegaPro GPU G6`.
Les deux réponses ont le SHA-256
`40675dd975bae9616bfb7fb475d0c81c1a92df901a6300480b5bbdd46e0842f4`.
Preuves : `g22_communication_01/result.json` et
`g22_communication_02/result.json`.

Le second test de communication vaut PASS : 10/10 requêtes EP0, réponse CPU,
identité USB inchangée pendant le test. Son script a pour SHA-256
`5c951f4689c8dce4c091d510b0012d6920bda3524b154b1e90e458f0c2fb455c`.
Il ajoute des chemins de preuve paramétrables mais conserve la cible physique
fixe. Syntaxe et refus des chemins hors périmètre vérifiés avant exécution.
Le script du premier essai est archivé ici sous `probe_new_link_initial.py`.

## Interprétation et limites

La deuxième carte communique avec G22r0 sur ce câblage. L'échec USB des builds
R3/R5 est reproduit ; la nouvelle ROM SD et la régénération AE350 ne sont pas
nécessaires à cet échec, puisque R3 conserve l'ancienne ROM/IP. La comparaison
ne détermine pas encore la cause et ne prouve pas une panne de timing.

Le collecteur de chargement exige aussi les messages de démarrage SD : son
champ global `passed=false` est attendu pour G22r0, qui ne démarre pas cette
chaîne SD. Il ne faut pas le confondre avec l'échec USB. Les preuves de
communication ci-dessus sont distinctes de la validation de démarrage SD.

**État laissé : G22r0 en SRAM sur la deuxième Pro Dock, USB et CPU répondants.**
Linux/jeu depuis SD, démarrage autonome après coupure et affichage restent
non validés. La flash n'a pas été programmée ; ses deux sauvegardes antérieures
sont conservées. Aucun résultat de cette fiche ne qualifie un build Neo.
