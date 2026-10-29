# Chargement SRAM et capture du premier démarrage SD

Préparation hors carte uniquement. Le coordinateur cible **2025071717** ;
il n'utilise jamais le programmateur 2023112818, le port USB7.3 ou le J-Link.
Le routage du candidat et sa revue restent du ressort de root. Aucun `.fs`
nouveau n'est supposé disponible ou qualifié par cette livraison.

`load_sd_candidate.py` réutilise `load_fpga.devices()`, la capture et le port
passif figés dans `autoboot_validation`. Il conserve le même verrou
`/tmp/prodock-diagnostic.lock` depuis l'inventaire jusqu'à la fermeture de
l'UART et la récolte du processus openFPGALoader.

Le programmeur fonctionne comme processus enfant, pendant que la boucle de
capture lit uniquement le port nouveau :

`/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0`

La capture peut donc commencer avant le retour d'openFPGALoader. Elle exige
une nouvelle énumération (disparition/réapparition ou nouveau bus/devnum)
depuis l'inventaire initial. Si le port conserve son ancienne identité,
les données potentiellement anciennes ne sont pas lues pour qualifier ce
démarrage. Il n'existe aucun repli sur un autre port.

## Utilisation réservée à root

Après copie et contrôle SHA de ce paquet et du `.fs` exact dans le ROOT distant :

```sh
python3 -B TESTS/prodock_new_20261028/load_sd_candidate.py --bit /home/michael/console-validation-20261001/TESTS/CANDIDAT.fs --sha SHA256_CANDIDAT --out /home/michael/console-validation-20261001/TESTS/NEW_SRAM_BOOT --seconds 120
```

Cette invocation prépare et affiche l'argv, sans ouvrir de périphérique ni
créer de dossier résultat. Après la revue root du bitstream et du protocole,
la même commande avec `--run` exécute l'essai. Le dossier résultat doit être
neuf ; les chemins symlink/traversal et les fichiers hors du ROOT distant
sont refusés. Le binaire doit être un `.fs`, dont le SHA est contrôlé avant
la programmation. L'unique commande FPGA autorisée est :

```sh
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k -m --verbose EXACT_CANDIDATE.fs
```

Le wrapper et son runtime sont épinglés respectivement aux SHA
`1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066`
et `101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873`.
Le runtime est celui dont les métadonnées ont été relevées par root sur ax15.

## Dépendances et paquet de transfert

L'archive `load_sd_candidate_delivery/runtime.tar.gz` contient uniquement :

- le coordinateur et le `load_fpga.py` déjà figé ;
- `autoboot_validation/{collector.py,serial_guard.py,boot_log.py,manifest.json}`
  aux empreintes originales ;
- une copie de transport de `support.py` sous `load_sd_candidate_delivery/`.

Les chemins de l'archive sont relatifs au ROOT distant. Les dépendances
existantes doivent conserver leurs SHA ; une extraction ne doit pas écraser
des fichiers divergents. `support.py` doit déjà se trouver à
`/tmp/festival_persistent_20261028_prepared_r1/support.py`, SHA
`45cf2c8cddcbe8a903f6bf73dca552512052883d88670ffa889815133127c29b`.
Si absent, root peut y copier la copie de transport vérifiée ; si divergent,
l'essai est refusé. Aucune copie distante n'a été effectuée par l'agent.

Seule la méthode de lecture UART de ce support est réutilisée. Ses anciens
PID, commandes de shell et contrôles de sauvegarde ne sont pas exécutés.

## Bornes et résultats

Budget normal : 120 secondes maximum pour inventaire + programmation +
capture. Le programmeur doit terminer dans les 90 secondes suivant son
lancement, sans dépasser le budget global. Les appels UART attendent au plus
100 ms ; l'ouverture/fuser est bornée. En sortie anormale : TERM, attente2s,
puis KILL et attente2s au plus. Aucun thread n'est créé.

Les signaux INT/TERM/HUP sont différés pendant la création du processus et
l'enregistrement de son propriétaire, puis pendant sa récolte. Le masque
initial est restauré dans l'enfant avant exec. Les tests comprennent un vrai
SIGTERM local entre création et enregistrement, et un processus Python local
dont la terminaison et la récolte sont vérifiées.

Les délais userspace ne couvrent pas un blocage noyau non interruptible, un
stockage bloqué ou le contrôle initial de fichiers. Si le processus ne peut
être récolté même après KILL, `programmer_reaped=false` interdit PASS ; le
rapport ne promet pas une disparition du processus dans ce cas.

`program_result.json` est écrit avant puis dès la fin de la programmation,
et complété dans le bloc final. `result.json`, `program.log` et les segments
`capture_NNN.bin` conservent les preuves et les erreurs. Sur signal pendant
la capture, ses octets déjà reçus sont sauvegardés par l'API existante.
Un incident d'écriture du stockage peut évidemment empêcher la conservation
complète ; il n'est pas transformé en succès.

`configuration_completed` exige le retour nul **et** le statut exact final
SRAM `DONE_FINAL`, ID physique1081b et absence de diagnostic explicite FAIL.
Le chemin Gowin peut revenir sans exception après certaines erreurs : le
retour nul seul ne suffit donc pas.

`log_checks_passed` exige la séquence de boot du collecteur figé, sur une
nouvelle connexion et après programmation confirmée. Si l'USB apparaît après
les tout premiers messages, la capture peut rester incomplète : aucune
ancienne preuve n'est substituée aux marqueurs manquants.

`game_launch_observed` est une observation des logs. `gpu_tested=false`,
`powercycle_validated=false`, `flash_writes=0`, `uart_tx_bytes=0` restent
explicites. Les SHA du paquet SD/Linux/jeu sont ceux attendus par le collecteur,
pas des SHA matériellement relus par cette capture. Aucun test de pixels, de
FPS ou de persistance après coupure n'est prétendu.

## Validation locale

15 tests passent avec le vrai coordinateur et le vrai collecteur, aux seules
frontières matériel remplacées par des fakes : boot précoce, absence UART,
ancienne énumération, mauvais serial/port, erreur programmeur, erreur avec
exit0, timeout, capture interrompue, exception hors capture et chemins.
Le signal et la récolte d'un petit enfant local sont aussi exercés réellement.
Le contre-lecteur indépendant n'a trouvé aucun bloqueur dans la gestion du
verrou, du processus et de l'identité de la connexion.

Aucun essai de carte, accès SSH, JTAG, flash ou SD n'a été fait par l'agent.
