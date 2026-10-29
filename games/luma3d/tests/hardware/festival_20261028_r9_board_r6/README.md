# Festival R9 : essai R6 arrêté pendant le transfert

Le paquet R6 exact (manifeste `66e113ea17517cbf53b847138b1e33b3201323faa13d0bef4133d7c35a66e316`) réutilise le helper relu intégralement et vérifié. Après nettoyage de quatre anciens exécutables, la garde de capacité trouve plus de 32 Mio libres avant le transfert. Cet essai est distinct du précédent échec avec tmpfs plein.

Le receiver annonce R0, puis acquitte correctement les paquets 0 à 115. La réponse au paquet 116 reste vide pendant la fenêtre ACK, et aucun marqueur de retour au shell n'est reçu. Le contrôleur s'arrête sans retransmettre ni envoyer d'abandon ou de commande shell. Une écoute passive supplémentaire de 15 secondes, sans flush, écriture série ni changement termios, reçoit également zéro octet.

**Résultat FAIL : R9 non lancé, aucune fenêtre de jeu exécutée.** GM1 PID3158/start27508908, sauvegarde et compteurs GPU ont été vérifiés avant le transfert ; aucun arrêt/redémarrage de GM1 n'a été envoyé. Leur état après échec ne peut pas encore être revérifié sur ce canal. L'état du receiver est inconnu et la récupération reste en attente. Aucun FPGA, noyau, SD, flash ou sauvegarde modifié. Aucun FPS R9 disponible.

Le receiver historique n'a pas de délai maximal de lecture. Le timeout d'ACK est de 0,5 s, suivi d'une attente de marqueur de 1 s. Fermer le port côté PC ne prouve pas que le processus cible soit terminé. Le silence n'établit ni une panne USB matérielle ni un problème GPU. La saturation précédente du tmpfs ne suffit pas non plus à expliquer ce nouvel échec.

Preuves : `result.json`, `festival-r9f.delta.lz4.transport.json`, `space_before_transfer_festival-r9f.delta.lz4.log`, et `../festival_20261028_r6_passive_r1/result.json`.

## Récupération du 28 octobre au matin

La séquence bornée de récupération, vérifiée auparavant sur l’ELF exact sous QEMU, est envoyée une seule fois : N116, F59392 puis marqueur de sortie code1 et prompt reçus. La ligne est annulée seulement après cette sortie confirmée. Le receiver bloqué est terminé ; aucun nouvel envoi de R9.

Le premier contrôle échoue sur `readlink` absent, le suivant sur `wc` absent et son remplacement sur le format court de `ls` sans date. Ces échecs du script sont conservés. Le contrôle final utilise les commandes réellement disponibles et passe : même GM1 PID3158/start27508908, save5292B inchangé, +68présentations, erreurs/underflow/fault nuls. 34244Kio disponibles en tmpfs. Delta partiel59392B, explicitement inutilisable. Aucun arrêt/redémarrage de jeu ni changement FPGA/noyau/SD/flash/save.

Preuves : `../festival_20261028_r6_recovery_board_r1/` et `../festival_20261028_r6_health_resume_r3/result.json`. La récupération ne qualifie pas le transport pour un nouvel envoi : un récepteur borné séparé est en développement.
