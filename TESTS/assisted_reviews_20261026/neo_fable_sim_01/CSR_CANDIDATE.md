# Candidat CSR local et simulation quatre états — 27 octobre 2026

Le multiplexeur CSR du `gpu_accel` figé suffit à créer une boucle d'événements
delta sous Icarus. Quatre blocs `always @*` écrivent chacun un octet du même
vecteur, en lisant cet octet pour accumuler les OR. La simulation minimale du
patron original ne progresse plus lorsque plusieurs octets sélectionnés sont
non nuls. Il ne s'agit pas d'une preuve de boucle combinatoire matérielle ni
de la cause des pannes de la Neo.

Le candidat remplace seulement l'accumulation dans `response_data` par un
accumulateur local à chaque octet, puis une affectation finale de l'octet.
Les trois fichiers préparés sont des copies sous `csr_candidates_01/`, pour
R19, Pro Dock G22r0 et la source commune actuelle. Aucun fichier commun ou
snapshot de référence n'a été modifié. Chaque diff et SHA sont consignés.

## Résultats exécutés

`check_csr_candidates.py` → `csr_candidates_01/result.json` : **PASS**.

- Pour chacun des trois candidats : 3 584 comparaisons quatre états. Les
  256 adresses sont testées avec douze motifs de données, dont X et Z ;
  512 sélecteurs arbitraires incluent X, Z et plusieurs bits sélectionnés.
  L'oracle est une réduction OR indépendante par bit, conforme à la valeur
  combinatoire du patron initial ; il n'exécute pas en parallèle le patron
  initial qui boucle dans Icarus.
- Pour les snapshots R19 et G22r0 : `gpu_accel`, géométrie, pixels, COPY,
  FIFO et arbitre DDR réels compilés sous Icarus. L'unique changement de RTL
  est le mux CSR candidat. Aucun `force` interne, aucun remplacement du
  producteur, du slot ou de l'arbitre. Seul l'endpoint DDR externe est modélisé.
- CLEAR : treize comparaisons de 73 728 octets, accès legacy/native à la même
  adresse, masques partiels, pauses d'horloge AHB, backpressure commande et
  données séparées, reset d'une requête en attente. Quatorze chargements du
  slot = treize requêtes acceptées et une annulée par reset. Treize ACK.
- COPY : deux cas réels, aligné 16 pixels puis source x5 vers destination x3
  sur sept pixels ; deux lectures et deux écritures au total, mémoire et
  gardes exactes.

`check_csr_bus.py` → `csr_validation_02/result.json` : **PASS**.

- Sur chaque profil : 512 lectures AHB réelles des 256 adresses, 512 cycles
  d'attente attendus, 2 110 contrôles de pipeline, deux resets et pauses
  de l'horloge AHB pendant certaines lectures. Aucun accès DDR émis.
- Les bancs complets CLEAR et COPY sont rejoués avec des détections explicites
  d'inconnues X/Z sur les contrôles de commande, le slot, son payload lorsqu'il
  est occupé et les transactions DDR actives.
- Pour G22r0, le seul ajustement de câblage du banc est le retrait des trois
  sorties de diagnostic absentes de cette ancienne interface.

## Limites

Ces tests qualifient la transformation CSR au niveau RTL et lèvent l'obstacle
de simulation quatre états de ce banc. Ils ne corrigent ni ne reproduisent
le rejet COPY matériel. Les contrôles mappés COPY sont distincts dans
`copy_mapped_02/result.json`. La qualification timing R19 demeure FAIL.
Une intégration commune doit conserver les références et relancer la campagne
locale des deux cartes ; une éventuelle nouvelle synthèse reste à qualifier.
