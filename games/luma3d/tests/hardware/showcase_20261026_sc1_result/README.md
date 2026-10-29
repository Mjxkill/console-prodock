# SC1 — Démonstration complète validée sur Pro Dock

Résultat : **PASS**, une seule conduite, terminée normalement. Le jeu laissé visible est `/tmp/luma3d-sc1 --showcase`, PID **2200**, startticks **19653856**. Il tourne en boucle autonome en arrière-plan, avec stdin `/dev/null` : les touches E/Q du shell ne pilotent pas cette instance. Le support interactif E/Q a été testé localement avec le vrai main et un faux GPU ; il nécessite un lancement au terminal. Aucun retour à NEBULA.

La conduite a fermé le port CDC et libéré son verrou en sortant normalement (code 0). Aucun accès carte supplémentaire après cette fin. La sauvegarde utilisateur V4 `/tmp/op2-live.save` est restée byte-identique, SHA256 `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`. OP2 et son fichier de sauvegarde restent disponibles ; aucun repli n’a été nécessaire. La démo n’a ouvert aucune sauvegarde.

## Ce qui a réellement été exécuté

- Identité fraîche OP2 PID 2011 / startticks 15755109 ; CRC de son ELF et de l’image en cours vérifiés avant arrêt.
- Récepteur de transfert relu exactement ; quatre fichiers RAM, 440 883 octets, 12 retransmissions CRC gérées. Aucun FPGA, noyau, flash ni carte SD écrit.
- Premier écran SC1 : **96 000 pixels RGB565 exacts** et plan HUD natif banque 20 exact. Palette/descripteurs validés localement, pas une capture photographique LCD.
- Vrai ELF `--showcase-once`, sans avance ni sauvegarde : **17 étapes, huit victoires**, boss, checkpoint, cristaux, vrais chemins et retour dans la vallée. **1 079** commandes des conseillers exécutées via les entrées normales avec dt positif et acquittement de présentation.
- Fin de tour correcte, contrôle du fichier V4 puis lancement frais `--showcase` ; progression des présentations vérifiée avant publication du nouveau PID.

## Durées et débit observés

Durée simulée : **829.742 s**. Durée murale : **834.916 s**, soit environ 13 min 55 s. Le processus a présenté **9023 images** ; moyenne globale **10.81 FPS**. Cette moyenne mélange déplacement 3D, lecture, puzzles 2D et activités 3D : ce n’est ni un gain, ni le débit d’une pose témoin, ni une garantie de régularité.

Les fenêtres d’environ 5 s sont conservées dans `performance_windows.json`. Le classement repose sur les compteurs réels d’instances/DRAW ; une fenêtre peut traverser une transition, ce qui limite sa portée. Il ne calcule pas de p95 ou p99.

Erreurs GPU, erreurs géométrie, underflows, couches invalides, sprites invalides et fault : **zéro**. Le compteur géométrie `slivers` vaut **5** sur le parcours complet (6 484 973 sommets, 2 357 179 triangles rasterisés) ; il est conservé séparément des compteurs d’erreur, sans le présenter comme nul.

## Identité et portée

- FPGA historique G22r0 conservé, continuité contrôlée par l’ABI/signature G3D1 ; aucun JTAG/reset/rechargement.
- Linux `6.12.112-prodock-luma3d-g3d1-r1` conservé.
- ELF : `b88685f36fe18d8fbdab53652a0683d8ff666c1aae8e3f8b245154fabec88ff6` ; 5617260 octets ; CRC32 `64fa6a0a`.
- Paquet : `showcase_20261026_sc1_prepared_r1`, manifeste `2021915b269e5a6f8853eaeff7351b90dfc5d49a4471701b46879d76485b7885`.
- Sources : `games/luma3d/build/showcase_20261026_r3/source` ; contrat des deux profils, 34 vues et 13 contrôles RV32 liés à ce même ELF.
- Les 654 entrées des 11 régressions communes sont restées identiques ; résultat 11/11 conservé sans nouvelle exécution.

Les 13 min 55 s mesurent **une visite guidée avec pauses de lisibilité**, pas une campagne de plusieurs heures. Les graphismes des activités, notamment du shooter, restent simples. Véhicules 3D, musique matérielle qualifiée et grande campagne restent absents. Aucun essai Neo n’est déduit de cet essai Pro Dock.

`result.json` et tous les journaux copiés depuis ax15 sont les preuves brutes. `tour_log.log` conserve chaque étape et fenêtre ; `sc1_tour_wait.log` conserve l’attente EXIT sans écriture UART. Les preuves AR1/OP2 et les paquets précédents sont inchangés.
