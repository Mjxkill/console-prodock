# R4 : contrôle de capacité du tmpfs avant chaque phase

Candidat local, aucun matériel touché par sa préparation. R3 demeure intacte.
Le delta et le jeu sont exactement Festival R9, sans le nouveau Pendu.

Le 28 octobre, root a mesuré `/tmp` à 186556/186556 Kio (0 disponible).
Le contrôleur refuse désormais de transmettre chaque fichier ou de reconstruire
l’ELF si `LC_ALL=C df -Pk /tmp` annonce moins de **32768 Kio disponibles**.
Les réponses absentes, dupliquées, incohérentes ou pour un autre point de montage
sont refusées. Aucune suppression automatique n’est effectuée. Les journaux
`space_before_transfer_*` et `space_before_reconstruction` gardent les mesures.
Cette garde ne réserve pas la mémoire : une consommation concurrente reste
possible et les erreurs de transport/reconstruction restent fatales.

Noms neufs : `f9d-helper`, `festival-r9d.delta.lz4`, `luma3d-f9d`, `festivalr9d_*`.
Les 5 tests de capacité utilisent la vraie méthode Hardware.prepare, avec
cibles simulées, en plus des 40 tests transport/contrôleur hérités.
Les fenêtres manuelles mesurent le rendu au repos, pas la fluidité du jeu.
Le tour de 450 images ne garantit pas la visite des quatre jeux.

Le reste du protocole R3, les gardes d’identité, la restauration GM1,
le verrou UART et la confirmation de retour au shell sont conservés.
Une revue root liée au manifeste exact est toujours nécessaire avant `--run`.

---

Historique du protocole précédent (conservé pour contexte) :

# Festival R9 — préparation r3, aucun essai matériel effectué

Cette préparation corrige la conduite du transfert après l'échec matériel r2.
Elle conserve R9, le helper, le delta compressé et tous les imports historiques
à l'identique ; le delta et le helper portent des noms temporaires neufs.
Ni r1 ni r2 ne sont réécrites. R2 n'a lancé aucune fenêtre Festival et GM1 a été
retrouvé actif par root, avec sa sauvegarde inchangée.

## Identités imposées

- Alias SSH `ax15`, nom local exact `michael-AX15`.
- Pro Dock G22r0, noyau `6.12.112-prodock-luma3d-g3d1-r1`.
- UART `/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00`.
- Verrou exclusif `/tmp/prodock-diagnostic.lock` et ouverture série exclusive.
- GM1 PID3158, startticks27508908, argv `/tmp/luma3d-gm1 --showcase`.
- ELF GM1 `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.
- Sauvegarde `/tmp/op2-live.save`, SHA
  `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.
- FPGA `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- R9 `6cdac82bb1b517c9d61680bf6542baec4b5fc586b2b202e8c3cf463615530f50`.
- Noms neufs : `/tmp/f9d-helper`, `/tmp/festival-r9d.delta.lz4`,
  `/tmp/luma3d-f9d`, préfixe des pid/logs `festivalr9d`.

Les anciens `/tmp/f9-helper` et `/tmp/festival-r9.delta.lz4` ne sont ni écrasés
ni supprimés. Les gardes de noms frais, de sauvegarde, de noyau, de PID/starttime,
de G22r0, de tmpfs et d'absence de montage SD restent obligatoires.

## Correction du transfert

`guarded_transport.py` enveloppe le transport historique figé. Le récepteur
RV32 historique reste **inchangé**. Les nouvelles règles sont :

- réémettre uniquement sur un `N` explicite avec la séquence attendue ;
- arrêter sur `F`, `D` en phase de données, séquence inattendue, octets non
  protocolaires, ACK partiel, timeout, écriture partielle ou exception UART ;
- conserver tous les ACK bruts, phase et séquence dans
  `<nom>.transport.json`, y compris le premier échec ;
- conserver le préfixe d'un marqueur de sortie qui aurait été lu à la place
  d'un ACK et attendre sa ligne complète avant d'interpréter son code ;
- accepter avant R0 l'écho textuel borné de la commande shell, sans supposer
  ECHO désactivé ; un échec au démarrage reste reconnaissable sans payload ;
- distinguer `receiving`, `unknown`, `received_D`, `complete` et `returned_error` ;
- ne déclarer `complete` qu'après `D` final de bonne taille **et** marqueur de
  retour au shell de code0 ; le seul `D` n'autorise aucune commande shell ;
- après une erreur ou un signal, n'effectuer qu'une lecture bornée du marqueur
  de retour ; aucun paquet d'abandon, retransmission ni commande shell ;
- en état inconnu, bloquer également la vérification de conservation GM1 et
  toute récupération automatique qui nécessiterait d'écrire dans le shell.

Le lancement du récepteur ajoute un marqueur shell exact, ancré en début de
ligne et lié au nom temporaire. L'écho de la commande contient `%s` et ne peut
pas satisfaire son format numérique. Ce marqueur ne constitue pas une preuve
contre une corruption arbitraire et intentionnelle du flux ; les conditions
initiales, les noms neufs et les contrôles complets du payload restent requis.

Une erreur conserve `receiver_abort_error` et `cleanup_blocked` si le retour
n'est pas confirmé. Elle n'est jamais convertie en réussite ni en preuve que
GM1 a été arrêté ou restauré. Root devra alors reprendre le diagnostic console.
`manual_recovery_required` l'indique explicitement. Un signal reçu pendant
la réception peut laisser le récepteur historique bloqué en lecture : aucune
annulation binaire n'est tentée dans cette version, même sur frontière de paquet.
Après confirmation du retour shell, les gardes normales vérifient GM1 et sa
sauvegarde. Après une erreur terminale confirmée, un unique Ctrl-C/Ctrl-U/newline
annule d'abord une éventuelle ligne binaire partielle ; un marqueur shell borné
doit ensuite être reçu. Cette resynchronisation est interdite en état inconnu,
`receiving` ou `received_D`. Son échec bloque toute vérification ultérieure.
Le lancement/récupération des processus GPU conserve le correctif
r2 : `not_sent` / `sending_unknown` / PID publié / EXIT reçu.

## Limite précise de cette correction

Le récepteur historique utilise un en-tête non protégé par CRC. Une corruption
`len=512` vers `len=0` peut provoquer `F` puis la sortie après les 16 octets du
header. Le sender écrit un paquet entier avant de lire sa réponse : **les512
premiers octets de payload peuvent donc déjà atteindre le terminal après cette
sortie**. La garde supprime les retransmissions et abandons après détection ;
elle ne rappelle pas ce paquet en vol et ne prétend pas rendre ce protocole
entièrement robuste. Empêcher aussi cette classe de sortie prématurée demandera
un nouveau récepteur/protocole (en-tête validé avant payload, fin distincte,
CRC d'en-tête et/ou superviseur qui garde le terminal).

Le premier ACK d'échec de l'essai réel r2 n'a pas été conservé. L'injection de
longueur prouve une possibilité déterministe ; elle ne prouve pas la cause
initiale de l'incident de la carte. Aucun défaut DDR/GPU n'est déduit de cet essai.

## Preuves locales

`receiver_exact.json` lie trois tests Linux/QEMU+PTY au binaire RV32 historique
exact SHA `5964389b8244dc73b58bf916a7856da3cc3aba2c2efa58779d1f755bb8410ae4` :
CRC de données faux → N puis poursuite ; longueur512→0 → F, exit1 et terminal
restauré ; bloc déjà accepté réémis → A sans duplication. ISIG=0, VMIN=1,
VTIME=0 sont observés sur le vrai tty du récepteur. Ce n'est pas un essai FPGA.

`test_transport_guard.py` injecte les réponses dans l'ancien sender réel et
la garde candidate. L'ancien écrit encore plus de5ko après F lu ; la garde n'en
écrit aucun après détection. Les512octets du paquet initial restant possibles
sont explicitement comptés. Les tests couvrent aussi ACK incomplet, timeout,
texte, N incorrect, D hors phase, écriture ambiguë, marqueur shell manquant et
signal juste après D. `test_trial.py` vérifie notamment que l'état inconnu
interdit les commandes de nettoyage. `test_launch_recovery.py` conserve les
contre-exemples de récupération avec les fonctions réelles et une cible simulée.

Le helper/delta ont été reconstruits localement et liés à R9. Leurs contrôles
sur cible restent taille/CRC reliés aux SHA locaux, pas un SHA calculé sur carte.
La sauvegarde et le helper sont relus entièrement avant utilisation.
Le payload en mémoire est aussi revérifié contre le manifeste immédiatement
avant son premier envoi. La preuve QEMU est liée au SHA du récepteur et à
l'initrd exact conservé dans le bundle ; les séquences R/N/A/D/F sont listées.

## Fenêtres et revue finale

La campagne reste celle de r2 : cinq fenêtres manuelles de120images (quatre
jeux et jardin), puis450images de visite automatique ; GM1 est restauré après
succès ou erreur lorsque l'état du transport/processus permet de le vérifier.
Les fenêtres manuelles mesurent le rendu **au repos**, pas les FPS animés des
jeux. La visite450 ne garantit pas les quatre jeux. Aucun pixel matériel n'est
comparé par ce contrôleur. Aucun FPGA, JTAG, noyau, SD, flash ou save n'est écrit.

Sans `--run`, `festival_trial.py` effectue seulement le précontrôle local.
Avant un essai, root doit produire une revue extérieure liée aux empreintes
finales du manifeste et du contrôleur, avec les mêmes champs que r2 :
`approved:true`, `reviewer:"root"`, `ssh_host:"ax15"`,
`local_hostname:"michael-AX15"`, `board:"prodock"`, `expected_identity`,
`fpga:"G22r0"`, `fpga_sha256`, `continuity_confirmed:true`, `kernel`,
`save_sha256`, `manifest_sha256`, `controller_sha256`.
Aucune revue n'est auto-approuvée dans ce bundle.
