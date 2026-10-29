# Lecture préalable de flash — préparation pour root uniquement

Aucun accès matériel effectué pour ce lot. Cible unique : FTDI0403:6010, série2025071717, hôte michael-AX15. La première Pro Dock2023112818, les UART et tous les J-Link sont hors périmètre.

Attention : openFPGALoader v1.1.1 prépare ces lectures en effaçant la configuration SRAM, puis réinitialise le FPGA. Détection et chaque sauvegarde interrompent donc la nouvelle configuration/Linux et peuvent redémarrer le contenu de flash existant. Aucun effacement/programmation de flash persistante n'est demandé. Aucun redémarrage de récupération automatique.

Le coordinateur présente d'abord un plan sans ouvrir périphérique ni verrou. --run explicite est réservé à root après revue. Le verrou /tmp/prodock-diagnostic.lock couvre les deux lectures d'une phase dump. Le garde historique est réutilisé avec ses empreintes ; loader original déjà présent sous ROOT/TESTS/prodock_new_20261028/load_fpga.py, SHA f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4. Runtime ROOT/runtime/openFPGALoader (pas bin/runtime).

## Commandes prévues sur ax15

ROOT=/home/michael/console-validation-20261001. Après transfert/extraction nonécrasante du paquet runtime seulement :

```sh
python3 -B /home/michael/console-validation-20261001/TESTS/prodock_new_20261028/flash_readonly_20261029_r1/prepared/flash_readonly.py --phase detect --out /home/michael/console-validation-20261001/TESTS/prodock_flash_detect_01
```

Ajouter --run après revue pour effectuer la détection. Elle produit detect.log et detect.json, avec capacité observée (secteurs×65536), JEDEC, modèle, retouroutil et SHA du journal. Root confronte ensuite la référence/capacité observée à la pièce ; aucune capacité n'est devinée avant ce résultat. Les commandes de dump ci-dessous sont un gabarit, les trois valeurs SHA/JEDEC/CAPACITE sont à remplacer par la preuve inspectée :

```sh
python3 -B /home/michael/console-validation-20261001/TESTS/prodock_new_20261028/flash_readonly_20261029_r1/prepared/flash_readonly.py --phase dump --out /home/michael/console-validation-20261001/TESTS/prodock_flash_backup_01 --detection /home/michael/console-validation-20261001/TESTS/prodock_flash_detect_01/detect.json --detection-sha SHA --jedec JEDEC --capacity CAPACITE
```

Ajouter --run après revue. Deux fichiers nouveaux backup_a.bin/backup_b.bin doivent avoir la taille complète prévue, des inodes distincts et des octets/SHA identiques. Chaque invocation nécessite son journal complet, la bonne identification et sa fin de lecture. Code retour 0 seul insuffisant. Délais :120s détection,900s par lecture ; option--timeout1..1800. Un échec/interruption ne relance rien et garde les fichiers/journaux partiels ; dossier préexistant refusé sans écraser ses preuves.

## Validation et attribution

MiniMax R1 incomplet resteFAILED. MiniMax R2 a produit le coordinateur et 21 tests d'intégration ; ses 28 tests totaux passent. La revue Codex a ensuite reproduit une fenêtre SIGTERM au retour de Popen laissant un enfant actif. Le correctif du superviseur est séparé dans process_guard.py : réutilisation de deferred_signals du coordinateur SRAM figé (copie exacte liée par SHA), puis récolte bornée. Trois signaux réels (SIGINT/TERM/HUP), timeout, enfant normal et faux noyau bloqué sont testés sans carte. Les détectionsJSON contradictoires sont également refusées. Les tests finaux et empreintes figurent dans ../supervisor_reviews/final_tests.json.

Si un processus reste bloqué dans le noyau malgré KILL, le délai utilisateur ne garantit pas sa disparition : le résultat estFAIL explicite et root doit inspecter ce processus avant tout autre accès. Ce lot ne prétend pas qualifier flash persistante, boot Linux, GPU ou coupure/remise sous tension.

REPORT.md conserve le rapport brut du modèle avant corrections ; sa phrase affirmant une récolte garantie est remplacée par la limite ci-dessus. Son essai prepare n'est pas un essaimatériel refusé : prepare indique simplement que l'hôte d'exécution est différent.

Les seules copies de références sont des instantanés figés avecSHA, pas des branches maintenues. Aucun RTL/pilote/jeu/build protégé n'est modifié. Les anciens échecs, sources de modèles et preuves sont conservés ; aucun processus localde test n'est laissé actif.
