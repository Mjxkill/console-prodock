# Festival R9 : transfert interrompu avant lancement

L'essai réel sur Pro Dock est **FAIL au transfert**. Aucune fenêtre du jeu R9
n'a été exécutée ; aucun FPS matériel R9 n'est donc mesuré. Le contrôleur r2
et son manifeste gelés sont conservés dans `../festival_20261027_r9_prepared_r2/`.

La vérification initiale retrouve GM1, PID 3158, startticks 27508908, le noyau
`6.12.112-prodock-luma3d-g3d1-r1`, la sauvegarde attendue et des présentations
qui progressent sans erreur GPU. Le helper est transféré, puis le transport
du delta abandonne au paquet 376 avec une réponse incohérente. Les dernières
réponses contiennent du texte du shell et l'écho de données binaires.

L'échec précède `stop_baseline` : le contrôleur n'a ni arrêté GM1 ni lancé R9.
La vérification automatique de conservation échoue cependant par timeout.
Ce résultat reste FAIL ; l'absence de commande d'arrêt ne remplace pas une
preuve de vie du jeu.

## Récupération séparée vérifiée

`../festival_20261027_r9_recover_console.py` rétablit un prompt par Ctrl+C,
Ctrl+U et nouvelle ligne, sous le même verrou exclusif Pro Dock. Il n'émet
aucun arrêt/lancement de jeu, reset, chargement FPGA ou écriture de fichier
sur la cible. Les lectures sont conservées dans
`../festival_20261027_r9_console_recovery_r1/`.

- Même GM1 : PID **3158**, startticks **27508908**, argv exact.
- Présentations : **3027334 → 3027395**, sans erreur GPU, underflow ou faute.
- Sauvegarde de 5292 octets relue intégralement, SHA-256 inchangé :
  `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.
- Aucun FPGA, noyau, fichier SD, flash ou sauvegarde modifié par cet essai.

## Ce qui est établi et ce qui reste à expliquer

Le transport courant réémet des paquets même après une réponse terminale ou
inconnue. Le contrôleur considère aussi tout octet de réponse `D` comme une
sortie du récepteur sans vérifier son contexte. Ces deux défauts sont examinés
dans un nouveau candidat et des tests d'injection, sans réécrire r2.

L'en-tête du protocole ne protège pas la longueur par CRC : une longueur
corrompue vers zéro peut provoquer une sortie prématurée du récepteur. C'est
un scénario explicatif à tester ; les ACK intermédiaires n'ayant pas été
consignés, la cause du premier arrêt réel n'est pas établie. Cet incident
ne prouve ni un défaut du rendu R9 ni une nouvelle cause du portage Neo.
