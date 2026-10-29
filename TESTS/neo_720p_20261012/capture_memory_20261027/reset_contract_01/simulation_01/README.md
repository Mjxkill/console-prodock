# Reproduction exécutée sur les sources exactes R19/R21

Cette campagne ajoute des preuves au dossier `reset_contract_01`, sans réécrire son analyse papier. Les deux blocs de synchronisation et l'instance du séquenceur sont extraits textuellement des sources figées ; le séquenceur et son récepteur UART sont copiés sans modification. Les fragments et modules concernés sont identiques entre R19 et R21. `source_manifest.json` conserve chemins, lignes et empreintes. Le banc ne substitue aucun comportement de CPU ou PLL : il observe les entrées POR/HW produites par le fabric, avec LOCK et DDRready comme stimuli numériques.

Les compteurs utilisent leur valeur réelle : 2 500 000 cycles de référence pour 50 ms. L'état établi est atteint par un démarrage légal, sans force interne. Les horloges sont exactement50 et80 MHz ; trois phases AHB sont testées :1 ;3,125 ;11 ns.

## Résultats

| Exécution | Scénarios | Violations qualification2ms | Violations attente50ms | Releases POR pendant done=0 |
|---|---:|---:|---:|---:|
| Verilator, phase1ns | 9 | 6 | 7 | 1 |
| Verilator, phase3,125ns | 9 | 6 | 7 | 1 |
| Verilator, phase11ns | 9 | 5 | 6 | 0 |
| Icarus4états, phase1ns | 9 | 6 | 7 | 1 |
| Icarus4états, phase11ns | 3 | 1 | 1 | 0 |

Les journaux d'événements Verilator/Icarus à phase1ns sont identiques octet par octet. Les cas communs à phase11ns concordent aussi. Les cinq bancs finaux terminent avec code0 : **cela valide la reproduction des échecs, pas les propriétés du DUT**, qui restent explicitement FAIL dans `result.json`.

Scénarios : démarrage sans perte, impulsions LOCK de1/4/6/8/30ns à plusieurs positions, perte traversant un front50MHz, perte pendant l'attente puis juste avant sa fin. Les campagnes complètes simulent250ms réelles de fonctionnement.

## Défaut1 : qualification périmée

Après le premier démarrage de50ms, une impulsion LOCK basse de t=6 à14ns entre deux fronts50MHz :

- réinitialise immédiatement les bascules AHB ;
- ne modifie ni ready_meta=11 ni delay_done=1 ;
- relève POR/HW à t=63,5ns dans le cas canonique, soit49,5ns après le retourLOCK.

Ce résultat reproduit exactement la trace papier. Près de la fin du premier délai, la release peut aussi intervenir moins de160ns après une nouvelle remontéeLOCK. En début d'attente, la durée restante peut dépasser2ms mais rester inférieure à50ms : les deux propriétés sont vérifiées séparément.

## Défaut2 : impulsion POR malgré la réinitialisation du compteur

Pour LOCK bas de t=16 à24ns, le front50MHz à20ns échantillonne bien la perte. Toutefois :

| Temps relatif | ready_meta | delay_done | init_sync | POR/HW |
|---:|---|---|---|---|
| 40ns | 01 | 1 | 00 | 0 |
| 51ns | 01 | 1 | 01 | 0 |
| 60ns | 11 | 0 | 01 | 0 |
| 63,5ns | 11 | 0 | 10 | 1 |
| 76ns | 11 | 0 | 00 | 0 |

Un ancien bit d'autorisation est déjà entré dans init_sync[0] avant le retrait de trial_release. Il atteint la sortie malgré delay_done=0, produisant une release de12,5ns. Ensuite le compteur réalise bien une nouvelle attente50ms. Le défaut dépend de la phase : présent à1 et3,125ns, absent à11ns dans les cas exécutés.

Le banc initial attendait un seul relâchement dans ce témoin et a échoué au comptage. Cette découverte n'a pas été supprimée : `tb_initial.sv`, les premiers journaux et les traces Icarus sont conservés. Seuls le journal et les assertions du banc ont ensuite été étendus pour vérifier explicitement ce second relâchement ; aucun codeDUT n'a changé.

## Limites

Ces tests prouvent deux propriétés RTL défaillantes sous les stimuli numériques exécutés. Ils ne mesurent pas une impulsion deLOCK sur la carte, ne représentent pas la métastabilité, ne comportent pas de SDF et ne qualifient pas la largeur minimale d'une commande asynchrone physique. Ils n'établissent pas pourquoi R21 échoue au démarrage alors que R19, doté de la même chaîne de reset, démarre.

Aucun RTL commun, référence, bitstream ou carte n'est modifié. Le correctif éventuel reste un candidat séparé à tester.
