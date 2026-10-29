# Disposition de la revue Fable TX

Réponse source : `TESTS/assisted_reviews_20261026/neo_fable_uart_tx_r1/answer.txt`.
Elle ne constitue pas un compte rendu d'essai. Aucun nouvel accès carte ici.

Retenu : retour write(8) différent de réception ; TIOCOUTQ ne mesure pas
la FIFO du pont ; la dernière fermeture annule les URB et vide la FIFO host,
sans annuler rétroactivement une livraison déjà acceptée. Le témoin R19
frais 0/0 ne décèle pas un reset retardé, qui redonnerait aussi 0/0. Une
preuve avec compteurs non nuls est donc utile avant/après tout contrôle de
transport. L'effet post-programmation JTAG et l'effet propre à R21 ne sont
pas séparés par cet essai.

Corrections nécessaires aux conclusions Fable :

- `out_waiting > 0` ne prouve pas à lui seul un URB soumis qui reçoit NAK :
  la somme contient aussi la FIFO host. La complétion d'un URB en erreur
  retire ses octets, mais d'autres données pourraient rester en FIFO.
- `latency_timer_show` renvoie `priv->latency` (ou 1 en low-latency), sans
  requête USB. La sonde EP0 proposée via cet attribut est donc invalide.
- Un GET_LATENCY réussi ne prouverait de toute façon pas qu'un RESET_SIO
  différent serait exécuté. Un ACK USB ne valide pas à lui seul la fidélité
  d'une émulation de firmware.
- Un statut modem reçu ne prouve pas que toute la tâche TX du pont fonctionne.
  Le contrôle endpoint et les transferts de données restent distincts.
- Une chute NCP pendant une ouverture sans trame est un reset observé, pas
  une preuve exclusive de l'émission d'une ancienne trame. DTR/RTS/reset
  spontané demeurent des causes possibles jusqu'à observation séparée.
- La règle de décision fondée obligatoirement sur une fermeture proche de
  30 s n'est pas justifiée : ce délai est un maximum et ne distingue pas
  seul livraison, erreur et interruption. La durée exacte n'a pas été
  enregistrée dans l'essai. Ne pas la reconstruire à partir du temps de
  programmation/restauration entier.
- Les statuts usbmon renseignent la complétion du transfert host. Ils ne
  permettent pas de déclarer à eux seuls qu'aucune donnée n'a atteint la
  logique interne du pont, surtout sans actual_length exact et chronologie.

Le fichier supplémentaire `tty_port.c` confirme le closing_wait initial de
30 s et l'appel wait_until_sent avant shutdown. L'attente peut cependant
finir plus tôt ; aucun résultat de durée n'est inventé pour l'essai passé.
Le chemin réel de tcflush n'a pas de callback spécifique USB-serial dans
les sources étudiées ; ne pas présenter reset_output_buffer comme purge
garantie du firmware.

La proposition de reset USB automatique est rejetée comme conclusion
prématurée. Le parent garde seul la décision d'un contrôle borné du pont.
Les améliorations utiles de capture restent : valeur TIOCOUTQ avant/après,
durée de close même en exception, résultat des contrôles EP0 effectivement
envoyés et distinction host/firmware. Le contrôleur matériel déjà utilisé
reste figé et ses preuves historiques ne sont pas modifiées.
