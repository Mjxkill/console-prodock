# Purge EP1 — banc par interfaces, sans accès matériel

Le banc `ep1_flush_interfaces_tb.sv` pilote les ports réels de `usb_fifo`,
`sync_tx_pkt_fifo` et `sync_rx_pkt_fifo`. Il ne remplace pas les FIFO, ne lit
aucun état interne et n'utilise ni `force`, ni `deposit`, ni hiérarchie `dut.*`.
Le paquet EP2 non acquitté est créé par de véritables écritures et lectures,
puis trois octets sont ajoutés derrière lui pour distinguer une reprise
conservée d'une nouvelle offre trop longue.

Le lanceur `run_interfaces.py` ne modifie pas la production, le candidat,
son patch ou son manifeste. Il vérifie leurs SHA, crée un répertoire de
preuve neuf, compile les variantes et conserve chaque journal et résultat.

Résultat `interfaces_r2/result.json` : **86 cas avec attentes satisfaites**.

- 75 cas du candidat réussis : purges de 1, 2 et 64 cycles sur EP0/EP1/EP2,
  `txact` bas/haut, strobe POP, ACK et ACK+POP ; six changements EP2→EP1
  pendant la purge ; longueurs EP1 1/64/512 et EP2 1/63.
- Production : les trois témoins avec EP1 sélectionné réussissent ; les
  six cas EP0/EP2 échouent réellement sur une offre périmée après purge.
  Ces échecs restent enregistrés avec `simulation_passed: false` et leur
  code de sortie non nul, distincts de `expectation_met: true`.
- Deux mutations isolées sont détectées : conserver `tx_pending[1]` bloque
  le nouveau paquet ; effacer tous les endpoints détruit la longueur de
  reprise EP2. Aucune mutation n'est appliquée au fichier candidat du parent.

Les simulations réussies comptabilisent 10 006 vérifications, 7 672 octets
contrôlés et 780 paquets. Chaque octet attendu dépend de son rang, y compris
au-delà de 256 octets. Les comparaisons utilisent `!==` pour rejeter les X/Z.

Chaque scénario vérifie la perte d'ACK d'EP1 et d'EP2, la longueur gelée malgré
de nouveaux octets, la purge, la conservation de la reprise EP2 (ou son ACK
normal s'il coïncide avec la purge EP1), puis un **nouveau paquet EP1 de cinq
octets exacts**. Ce paquet perd à nouveau un ACK ; quatre octets sont ajoutés,
la reprise doit toujours contenir exactement les cinq premiers. Les compteurs
publics `o_ep1_tx_sent` doivent ensuite valoir 5, 9 et 10 après les ACK.
Un poll vide avec `txact` haut suivi d'un octet tardif vérifie aussi que la
purge n'a pas laissé de réservation vide bloquant les arrivées suivantes.

Le contrat des strobes est explicite : un ACK EP2 est émis seulement après
lecture du paquet annoncé, sur EP2 encore sélectionné. Un POP simultané est
alors une impulsion spéculative supplémentaire, avant la retombée de `txact`.
Les changements d'endpoint pendant purge n'emportent aucun ACK/POP de l'ancien
endpoint vers le nouveau. Un endpoint nouvellement sélectionné peut conserver
une ancienne longueur enregistrée si CORK reste haut ; le banc ne transforme
pas cette valeur invalide en fausse offre. La purge EP1 sélectionnée impose
en revanche CORK haut et longueur zéro immédiatement, conformément au patch.

Les horloges EP1, EP2 et contrôleur sont identiques, comme dans l'intégration
actuelle décrite par F01. Ce banc prouve des transitions numériques aux
interfaces du FIFO ; il n'est ni un test de métastabilité, ni de routage CDC,
ni un essai PHY/câble. La suite HS du modèle officiel exécutée séparément par
le parent dans `official_r1` est une autre preuve et n'est pas revendiquée ici.
Les avertissements Icarus de timescale et de nets implicites hérités sont
conservés dans les journaux de compilation ; aucune réduction de la suite.

```sh
python3 -B TESTS/assisted_reviews_20261026/usb_ep1_candidate/run_interfaces.py \
  --out TESTS/assisted_reviews_20261026/usb_ep1_candidate/interfaces_nouveau
```

Outils locaux : `/tmp/console-usb-sim-tools/extracted/usr/bin/{iverilog,vvp}`.
`interfaces_r1` conserve uniquement une mise au point du premier cas ; le
rapport complet et identifié est `interfaces_r2/result.json`.
