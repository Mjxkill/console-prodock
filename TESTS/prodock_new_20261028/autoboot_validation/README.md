# Validation passive du boot — nouvelle Pro Dock 2025071717

Collecteur préparé uniquement, jamais exécuté sur une carte par cet agent.
Il ne sait ni programmer, ni envoyer une commande, ni tester le GPU.

Cible imposée : hôte `michael-AX15` (alias SSH `ax15`), SOFT-USB
`/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0`, topologie USB `3-7.1`.
Le port7.3 de l’ancienne carte et tout J-Link sont exclus. Le numéro USB
11252024 n’est pas une identité physique suffisante : root atteste le
raccordement et le collecteur vérifie aussi le parent sysfs du TTY ouvert.

## Avant exécution par root

1. Relire le manifeste et le candidat FPGA ; programmer uniquement2025071717.
   Une première configuration SRAM (`flash_writes:0`) est admise et demeure
   distincte d’une programmation persistante ou d’un essai après coupure.
2. Préparer une revue JSON avec les champs de `review.example.json` et les
   empreintes réelles. `program_result_path` désigne le résultat du chargeur :
   `target_serial`, `bitstream_sha256`, `configuration_completed` et
   `flash_writes` sont contrôlés. Ce fichier doit être relu et haché par root.
3. Copier `collector.py`, `serial_guard.py`, `boot_log.py`, `manifest.json`
   ensemble. Le petit helper UART historique est réutilisé à son chemin
   `/tmp/festival_persistent_20261028_prepared_r1/support.py` et vérifié par SHA ;
   aucun ancien garde PID/jeu ni protocole d’émission n’est appelé.
4. Exécuter d’abord `python3 -B collector.py` : précontrôle sans matériel.
   Puis uniquement root, avec revue fraîche et nouvelle sortie :

```
python3 -B collector.py --run --expected-manifest <SHA_manifest> \
  --review revue_root.json --out nouvelle_capture --seconds 120
```

La durée de lecture maximale est120s (horloge monotone), avec4MiB maximum.
Les opérations noyau/filesystem bloquées ne peuvent pas recevoir une garantie
de délai absolu depuis Python. Le collecteur prend le verrou de diagnostic,
refuse un propriétaire fuser, ouvre **O_RDONLY**, prend TIOCEXCL, règle le
termios115200/raw et évite HUPCL. Aucun octet, flush, commande shell ou ioctl
DTR/RTS explicite n’est émis. Les reconnexions conservent des segments séparés.

Pour capturer les toutes premières lignes pendant la programmation, root peut
réutiliser `capture(io,out,seconds)` et `PassiveUART` dans son propre
coordinateur détenant le verrou. Le collecteur autonome commence seulement
après la preuve de programmation et peut donc manquer les premières lignes :
il retourne alors INCONCLUSIF, jamais une validation inventée.

## Sens exact des résultats

`log_checks_passed` exige, dans la dernière tentative seulement et dans
l’ordre, les messages réels SD/U-Boot/Linux, la version Linux SD opt-in,
le lancement fixe `LUMA3D.ELF --festival`, puis GRAPHICS_READY hardware=1.
Une demande de lancement seule ne signifie pas que le jeu s’est initialisé.
Le jeu attendu est CM1 SHA a8485ce6… ; l’identité binaire est reliée au paquet
installé par la revue root, **pas mesurée par ces messages UART**. Le parser
ne peut pas distinguer des ELF différents qui impriment les mêmes messages.

`game_launch_observed` signifie que le programme a atteint GRAPHICS_READY
après le hook. Cela n’affirme pas qu’il tourne toujours ensuite.
`gpu_tested`, `powercycle_validated`, `kernel_sha_measured` et
`game_sha_measured` restent toujours faux. Les mesures GPU et le constat de
coupure/remise sous tension nécessitent leurs preuves séparées. Une ligne
fatale ou des données corrompues empêchent le succès du contrôle des logs.

Les21cas parser,7groupes de gardes et8tests de transport avec faux ports/
horloges sont hors matériel. Ils couvrent notamment un succès ancien suivi
d’un nouveau boot incomplet, les ports7.3 interdits, les preuves du mauvais
programmateur, l’absence de port, les interruptions et la borne de données.

Beam a fourni un parser initial mais la contre-revue a reproduit5défauts :
bytes non sérialisables, lancement affirmé sans hook, suffixes de chemin et
de message acceptés, champ `nothardware=1` accepté. Sa reprise n’a pas édité
avant sa limite de pas ; le superviseur a corrigé ces5points dans
`boot_log.py` et rejoué les21cas. Les métriques FAILED des2essais restent
conservées, sans score ni réussite de workflow inventée.
