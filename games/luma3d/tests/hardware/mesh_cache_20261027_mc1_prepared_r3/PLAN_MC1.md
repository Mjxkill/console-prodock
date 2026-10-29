# MC1 — comparaison de publication, préparation locale

Ce document ne lance pas la carte. Le bundle final et son contrôleur doivent
être revus par le parent avant l'essai. L'autorisation utilisateur de conduire
des essais logiciels existe déjà ; la coordination du nouvel essai reste requise.

## Identités et état à préserver

- Pro Dock USB série11252024, G22r0 conservé, noyau
  `6.12.112-prodock-luma3d-g3d1-r1`, aucun FPGA/noyau/SD/flash écrit.
- Témoin ET repli : GM1 `/tmp/luma3d-gm1 --showcase`, ELF
  `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.
- Dernière ancre connue : PID2925/startticks26240721. Relecture exacte sous
  verrou ; tout changement refuse cet essai et demande un nouveau paquet.
- `/tmp/op2-live.save` V4 reste identique, SHA
  `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.
- Candidat logiciel : `build/maze_publish_cache_20261027_r3`, ELF
  `8d2b54d7b4f3b2fa27628c019860f36c3299e0b574b733bc5684c29710df942a`.
  Deux ombres CPU, mêmes ressources/meshes/commandes, uniquement écritures
  des blocs32B différents dans les banques dynamiques26/27MiB.

## Séquence

1. Préflight local de tous les SHA, reconstruction exacte des deltas et liens
   source/probe/oracle. Dossier résultat neuf et noms `/tmp/mc1-*` absents.
2. Verrou `/tmp/prodock-diagnostic.lock` exclusif et port CDC exclusif sur ax15.
   Vérifier uname, ABI/caps/G3D1, tmpfs, compteurs et identité complète
   PID/starttime/argv via lecture octale. Aucun `--save` admis.
3. Transférer et contrôler les CRC en RAM pendant que GM1 continue à tourner.
4. Annonce dix secondes avant changement visible. Revalider la même identité
   juste avant TERM ciblé ; arrêt confirmé avant toute nouvelle instance GPU.
5. Oracles de scènes maison/exploration/tour, avec états normaux, restart et
   BACK. Captures exactes du RGB publié, des sources UI publiées et des compteurs
   de la dernière image. Aucun test arbitraire des trous VRAM non initialisés.
6. Fenêtres chronométrées, chacune2images d'entrée +12repos +360mouvantes :
   maison A/B/B/A, puis exploration A/B/B/A. A=GM1, B=cache. Un seul pas
   logique60Hz par image, mêmes états/commandes ; cela mesure une charge
   comparable, pas le débit d'une visite entière en temps réel.
7. Aucun envoi UART pendant chaque fenêtre : attendre le marqueur EXIT du
   superviseur. Extraire ensuite les journaux et contrôler leurs signatures.
8. Restaurer GM1 en boucle autonome, en succès comme en échec de MC1.
   Le cache ne sera pas promu automatiquement à partir d'une moyenne.
   Vérifier progression des presents, identité avant/après progression puis
   après lecture de sauvegarde et publication du PID. Libérer CDC et verrou.

## Mesures et portée des preuves

Chaque fenêtre rapporte simulation, préparation, publication des meshes,
octets demandés/publiés/comparés, allocation, commandes/batches/triangles,
feed/wait/cache/PRESENT, p95/p99 et maximum avec indices. Les coûts de copie
sont inclus dans la préparation ; ceux du pilote sont inclus dans SUBMIT.
Aucune addition qui compterait deux fois les mêmes durées.

Le contrôle local existant compare exactement80images sélectionnées des deux
profils : commandes, codecs et32MiB, après528rendus avec transitions et restart.
Il est lié au bundle. La partie matérielle lit les plages publiées des oracles,
sans revendiquer une lecture composite LCD ni70captures intégrales de32MiB.
Seize fixtures RV32/QEMU lient les probes aux octets de référence ; quatre fenêtres RV32 vérifient aussi états et volumes.

Les deux paires A/B et B/A sont conservées séparément pour chacune des phases
entrée, repos et mouvement. Les gardes de non-régression s'appliquent à toutes
ces phases (moyenne +10 %, p99 +25 % +4 ms, maximum +50 % +20 ms).
La dérive symétrique des témoins A est limitée à 3 % dans chaque phase :
max(Afin/Adebut, Adebut/Afin) <= 1,03. Une phase qui régresse ou dont le témoin
dérive refuse `performance_accepted`. Deux images d'entrée constituent une
mesure courte et bruitée : un refus reste conservé, sans répétition opportuniste.
Ces gardes ne constituent pas une qualification 30/60 FPS.
Zéro p99 avec overflow signifie hors histogramme, jamais zéro latence.

## Nettoyage

SIGINT/SIGTERM/SIGHUP passent par le même nettoyage. Avant sa première action,
le contrôleur inhibe leur effet d'interruption ; les signaux supplémentaires
sont consignés et ne peuvent interrompre le repli, sa vérification tardive
de sauvegarde/identité ou la publication du PID. Cela s'applique aussi au repli
normal. Une erreur locale d'écriture de journal pendant le nettoyage est
consignée sans bloquer les commandes de restauration ; elle interdit un PASS
de preuves complètes. Le dernier résultat peut lui-même rester non archivé
si le stockage local est indisponible, mais sa tentative vient après le repli.

Abandon contrôlé du
récepteur en transfert ; après arrêt de GM1, terminer uniquement le processus
de l'essai dont le PID est publié. PID inconnu ou remplacé : échec fermé,
aucun deuxième producteur GPU. Repli idempotent et identité complète de la
reprise, jamais un simple `comm`. Les résultats FAIL restent archivés.

Limites opérationnelles conservées : les startticks des probes sont acquis par
le contrôle de nettoyage, pas à leur lancement. Le port série n'a pas de
`write_timeout` explicite ni de watchdog autonome. Un transport réellement
bloqué ou une identité indéterminée ne permet donc pas de garantir le repli ;
le contrôleur échoue fermé et ne doit pas annoncer GM1 restauré sans preuve.
Le refus de revue R2 est conservé dans
`TESTS/neo_common_cause_20261027/game_controller_review.md` ; R3 corrige les deux
contre-exemples concrets, sans changer les binaires, oracles ou gardes PID.
