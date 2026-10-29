# Validation de la contre-revue exécutée

La réponse DeepSeek est conservée dans `../usb_deepseek_bot_r2_executed_retry/answer.txt`, avec statut, modèle, usage et empreinte du paquet. La première tentative a échoué sur DNS et n'a produit aucun avis. La reprise autorisée a terminé normalement. Le modèle n'a exécuté aucun test ; les résultats Icarus lui ont été fournis.

Conclusion retenue : aucun faux PASS démontré sur F01. Le témoin original échoue au point prévu et le candidat passe. Cette conclusion reste limitée au défaut de réservation IN après purge et à la reprise simulée documentée dans `INTEGRATION_R2.md`.

## Deux propositions PID rejetées après vérification primaire

La contre-revue suppose à tort qu'un CBW devrait toujours utiliser DATA0 et un CSW toujours DATA1. Les endpoints bulk conservent leur séquence de toggles entre transactions réussies ; ils repartent à DATA0 après configuration ou réinitialisation du toggle par la requête de récupération appropriée. Un CBW DATA1 ou un CSW DATA0 n'est donc pas une faute à lui seul. Réinitialiser le modèle hôte avant chaque CBW/CSW créerait au contraire un oracle erroné. Source primaire : [USB 2.0, §5.8.5, page55](https://bitsavers.trailing-edge.com/components/usb/USB_2.0_2000.pdf#page=83).

Le reset de classe BOT doit lui-même préserver les toggles bulk. La procédure Reset Recovery enchaîne ensuite les deux CLEAR_FEATURE ; le banc réinitialise ses PID hôte après ces requêtes, pas après chaque commande. Source primaire : [Mass Storage Bulk-Only Transport1.0, §3.1 et §5.3.4](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf).

`msc_in_pid` est un état hôte indépendant calculé sur les ACK envoyés et comparé au PID reçu ; il n'est pas copié depuis le DUT. Ce n'est donc pas un oracle auto-référentiel au sens affirmé par la revue. Le banc reste toutefois un hôte de simulation, pas une suite de conformité USB exhaustive.

## Limites utiles retenues

- L'argument `lose_ack` de l'ancien helper `empty_packet` n'est pas utilisé. Les reprises de données sont testées ailleurs, mais la reprise d'un CSW sans ACK n'est pas prouvée par F01. Corriger ce helper et ajouter un vrai CSW non ACKé/rejoué constitue un complément permanent utile, sans changer les attentes PID bulk.
- Le NAK F01 est observé après handback/reclaim. Le commentaire « handback ne purge pas » désigne l'absence d'impulsion `ep_flush` ; le handback remet bien à zéro des compteurs de staging du port. L'original échoue malgré les mêmes transitions. Pour isoler encore mieux la fenêtre, le parent peut ajouter une sonde NAK immédiatement après `quiet_h=0`, puis conserver celle après reclaim.
- F01 sous modèle officiel couvre volontairement EP0 pendant purge. Le chemin de masquage sous EP1 et les interactions ACK/POP sont couverts séparément par les 75 cas candidats du banc d'interfaces (`interfaces_r2/result.json`), dont changements d'endpoint et maintien de vrais octets EP2. Ne pas attribuer cette couverture au seul scénario BOT.
- F01 ne couvre pas la purge d'un OUT firmware en attente, une troisième commande après le CSW final ni un nouvel assert du bit `lost` en fin de F01. Ce sont des extensions possibles, pas des preuves acquises.
- Le paquet externe contenait les 60 dernières lignes des journaux, mais les journaux complets et leur SHA sont bien archivés dans les deux dossiers de résultats. Il n'y a aucun besoin de forcer ou lire `tx_pending` pour constater le paquet interdit sur l'interface UTMI.

Aucune suggestion externe n'a été appliquée automatiquement. Le RTL de production, les sources R2 et les traces exécutées restent inchangés. La proposition permanente est remise au parent ; la prochaine campagne globale relève de lui après adoption éventuelle.
