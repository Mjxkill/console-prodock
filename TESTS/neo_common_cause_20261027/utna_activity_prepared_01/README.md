# Collecte activité UTNA R19, sans qualification

Préparation hors carte depuis la restauration R19 de snapshot_20261027_232521.
Une seule session observe ARM=1, attend 200 ms, DISARM=6, attend 100 ms,
SNAPSHOT=2, attend 100 ms, puis SNAPSHOT=2. Chaque acquittement est borné
à 100 lectures et 2 s ; OpenOCD reste borné à 30 s. Aucun transfert USB,
accès DDR, GPU, SD ou UART.

Chaque phase lit deux banques identiques. ID, compteur et commande doivent
être exacts. La seule exception de collecte est version0 : elle est affichée
ACTIVITY_CONTRACT_FAIL, conservée et impose FAIL global après collecte.
Une version autre que 0/1, une banque incohérente ou une autre garde cassée interrompt
immédiatement la séquence puis restaure R19.

Les mots 3 (ticks) et 31 (armed) servent à comparer l'état avant ARM,
avant DISARM, le tick final +1 et la stabilité après arrêt. Ils ne prouvent
aucune fréquence. Cet essai ne sépare pas la case 1 de la FIFO, la case 1
de la banque et son masque de validité.

Après possibilité de mutation, une seule restauration exacte R19 est tentée,
avec le même IO et pattern de signaux v3/SNAPSHOT. Les erreurs initiales,
restauration et journal restent séparées. Aucun reset ou redémarrage auxiliaire.
La restauration SRAM peut redémarrer la ROM, puis la garde vérifie le CPU parqué.

Revue préparée avec hardware_ready=false ; root relit et exécute exclusivement.
Aucune source RTL ni référence Pro Dock modifiée.
