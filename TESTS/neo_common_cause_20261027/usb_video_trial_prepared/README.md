# Observation UTNA fraîche avec comparaison vidéo — préparation

Aucun accès à la carte n'a été exécuté. `review_prepared.json` garde
`hardware_ready=false`. Root doit examiner les sources et créer sa revue
explicite avant toute exécution matérielle.

Le contrôleur reprend le relevé vidéo précédemment validé. Son seul accès MMIO
en écriture est `0xe900200c`, commandes UTNA **1, 6, 2, 2**, sur R19 puis sur le
candidat R21r2 couplé. Chaque commande attend une séquence nouvelle, un statut
idle sans rejet, puis lit deux fois la banque complète sous contrôles de statut
et de séquence. Les valeurs brutes sont journalisées avant leurs assertions.

La commande 6 capture le dernier état armé. Le snapshot 2 suivant doit montrer
un tick supplémentaire (incrément au front de désarmement), puis le second
snapshot 2 doit conserver ce compteur et le bit armed nul. Cette règle provient
du RTL figé ; la simulation existante est liée, pas réinterprétée d'après un avis
externe. Il n'y a ni powercycle, ni commande UART, ni reset USB.

Le relevé vidéo original est conservé avant la séquence USB. Une lecture vidéo
supplémentaire suit la dernière capture. Deux photos du candidat sont prévues,
avant DMI puis après les observations ; leur netteté et leur cadrage restent
à vérifier humainement. Une photo floue ne sera pas une preuve de noir.

Dès la première tentative de commande UTNA sur la référence, le bloc finally
restaure **une seule fois** le bitstream R19 exact, même si l'observation initiale
échoue. Le garde initial R19 doit avoir réussi avant toute mutation. La
restauration conserve la protection contre signaux et les sauvegardes best effort
précédemment revues ; DONE reste enregistré immédiatement par l'IO commun.
Le garde final ajoute une vérification ID/statut/séquence UTNA frais.

Le même verrou exclusif Neo, la même identité carte, les SHA exacts, l'ancre
fraîche `video_readonly_20261027_155600/result.json` et les limites de durée
OpenOCD/programmeur/caméra sont conservés. Chaque commande attend au plus
100 polls et une borne locale de 2 s ; la session OpenOCD reste bornée à 30 s.
Aucune écriture GPU, DDR, SD ou flash, aucun Linux ni resume debugger n'est prévu.
Une reconfiguration peut naturellement redémarrer la ROM CPU avant le halt.

## Vérifications hors carte

- 13 cas sur le Tcl **exact**, avec un périphérique MMIO simulé : succès, ACK
  retardé, mauvaise identité, rejet, busy persistant, séquence incorrecte,
  header erroné, banque instable/courte, ticks nuls, tick final absent, compteur
  continuant après désarmement, armed persistant. Tous détectés comme prévu.
- 13 cas du flot Python avec IO mockée : succès et pannes avant/après mutation,
  panne chargement candidat, double panne de restauration, journal en erreur
  OSError/KeyboardInterrupt persistante. Une seule restauration est tentée.
- Preuve RTL Icarus existante : trois phases/rapports d'horloges passent ; le
  témoin négatif exigeant à tort l'égalité des ticks 6→2 échoue. Les hashes des
  sources originales sont revérifiés ; USB trace et FIFO sont identiques dans
  les deux snapshots utilisés.
- `--check-only` passe avec la préparation non autorisée pour le matériel.

Les modèles MMIO vérifient le contrôleur, pas la logique physique du FPGA. Le
banc RTL existant ne qualifie pas le routage. Le FAIL timing du candidat reste
inchangé, et ses captures dynamiques NCP D/Q/CE ne sont pas utilisées.

Une capture UTNA fraîche avec ticks positifs démontre une activité du domaine
USB et de son protocole de transfert pendant cette fenêtre. Elle ne démontre
pas l'énumération HS, la fréquence 960 MHz ni l'absence d'un défaut commun
transitoire antérieur. Un timeout de capture ne localise pas à lui seul la panne.

`controller.diff` expose le delta du flot vidéo d'origine. Le nouveau contrôle
valide directement les preuves immuables de l'ancienne revue, puis lie tous les
imports du nouveau contrôleur à **sa nouvelle revue**. Appeler l'ancien calcul
dynamique des dépendances ajouterait ce script au manifeste ancien déjà figé ;
aucun manifeste historique n'est réécrit pour contourner ce problème.
