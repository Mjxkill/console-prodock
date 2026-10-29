# MetricsR4 — phase1 : transfert et reconstruction seulement

Ce paquet est séparé de RX2r3 figé. Le programme actif reste GM1 pendant toute
la phase1, y compris après succès. Aucun jeu n'est signalé, arrêté ou exécuté.
Root seul peut lancer `transfer_trial.py --run --expected-plan SHA --review
review.json --out NOUVEAU_DOSSIER` sur michael-AX15. Par défaut, préflight local
seulement. La revue engage la continuité G22r0/GM1/helper et le shell exclusif.

Identités locales : GM1 SHA `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`;
metricsR4 SHA `6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7`,
16 640 496octets. La cible reste sous la limite16MiB du helper, marge136720octets.

| Voie | Octets transmis avant encodage RX2 |
|---|---:|
| ELF brut | 16 640 496 |
| LZ4 complet | 5 805 324 |
| Delta GM1 + LZ4 retenu | 2 027 641 |

Le delta est envoyé à `/tmp/rx2-fm4a.delta.lz4.part` par huit sessions de512blocs
au plus (256KiB/session). Chaque session se termine STOP ou FIN puis RETURN frais,
annulation de ligne et prompt. Une interruption ne déclenche pas de nouvel envoi
automatique. `--resume` exige une nouvelle revue après retour shell confirmé :
le nouveau nonce et le CRC du préfixe vérifient le fichier partiel. La réserve
initiale compte conservativement le payload entier, même pour une reprise.

Le pacing16octets/2ms impose un plancher372,332s, hors ACK, charge système et
vérifications. C'est un calcul, pas une mesure. Les six probes RX2 sur Pro Dock
sont PASS et conservées, mais ne remplacent pas une mesure de ce transfert2Mo.
Chaque session a un délai total15min et un idle5s ; une erreur conserve l'état
pour diagnostic sans reset matériel ni binaire dans le shell.

Espace requis avant transfert :27 056 745octets (delta+cible+8MiB), à recontrôler
sur /tmp tmpfs. Avant reconstruction :25 029 104octets encore libres (cible+8MiB).
Le helper peut allouer environ35,3Mo au pic ; MemAvailable≥64MiB est exigé.
La preuve RX2 récente indiquait33 628KiB libres. Aucune suppression automatique.

Le RX2 de13 132octets est relu intégralement par od-b-v et SHA256 avant usage.
Le helper221180octets est identique à la relecture complète déjà faite par root ;
sa continuité est explicitement attestée puis ses permissions et son CRC runtime
revérifiés. GM1 sur disque et `/proc/3158/exe` sont vérifiés avant le delta.

Le helper historique reconstruit `/tmp/luma3d-fm4a` avec O_EXCL. Le target entier
est revérifié par CRC32 avant chmod700, **sans exécution**. Les SHA source/cible
sont des identités locales ; le contrôleur ne prétend pas mesurer un SHA256
matériel de l'ELF16,64Mo. La liaison résulte du delta/helper exacts, de la preuve
QEMU comparant chaque octet reconstruit et des CRC complets sur carte.

La phase2 restera distincte : arrêter GM1 seulement après phase1 PASS, vérifier
PID3158/start27508908 immédiatement avant TERM, exécuter les six fenêtres du
plan sans option de sauvegarde, puis restaurer exactement GM1 `--showcase`.
Ne jamais lancer deux propriétaires GPU. Un lancement incertain n'autorise ni
un deuxième jeu ni une restauration en double. Utiliser les gardes de lancement
revus de FestivalR6 (not_sent/sending_unknown/published/completed), avec nouveaux
pidfiles/logs et publication atomique. En cleanup, arrêter uniquement le PID
candidat prouvé, puis restaurer GM1 une fois, contrôler son nouvel identifiant,
la progression du GPU et le SHA de la sauvegarde inchangée. Les marqueurs PID
non publiés restent un refus, sauf preuve certaine qu'aucun lancement n'est parti.

Les fenêtres sont dans plan.json et le parseur exact est read_metrics.py :
Othello/Solitaire/Chroma/Pendu4actions, Memory24actions, jardin120images manuel.
Séparer entrée/publication d'atlas des phases animées. Ne pas appeler repos FPS
de jeu, ni les temps hôte FPS matériels. Le parseur refuse hardware=0 et les
actions manquées/fins non stabilisées lorsqu'on lui demande une preuve carte.
