# Observateur COPY et événements mémoire : validation locale

Helper exact testé :
`TESTS/neo_720p_20261012/capture_memory_20261027/neo_capture_memory.v`,
SHA-256 `1051163608ea69c7f56ebb2a4363a7ac773285e7284e3f532b377054602f7a90`.

Aucun accès matériel, synthèse ou routage dans ce dossier. Le helper est
fourni par le coordinateur ; les tests ne changent pas son fonctionnement.
Les résultats ne qualifient pas le futur routage de cet observateur.

## Protocole AHB et CDC

`protocol_02/result.json` : **PASS, 221 contrôles**. Le banc reprend le bus
NCP1 inchangé et le contrôleur AHB de diagnostic existant. Cinq rapports
d'horloge, pauses des deux domaines, reset en cours de requête, réarmement,
capture correcte, CE absent, reset prioritaire et Q non capturé sont exercés.

Les seize combinaisons des quatre événements sont distinguées. Un ARM efface
l'historique ; les événements continuent après un SNAP jusqu'au prochain ARM.
`held` ne change qu'au SNAP. Un événement apparaissant uniquement sur le front
qui traite SNAP est inclus, avec `mem_seen` explicitement nul avant ce front.

`protocol_01` reste un résultat historique PASS à 220 contrôles, avant cet
ajout de cas frontière. Les fichiers et journaux antérieurs sont conservés.

## COPY réellement mappé et injections explicites

`mapped_copy_02/result.json` : **PASS, quatre cas de douze contrôles**.
Les modules extraits de la netlist R19 et les primitives officielles sont
réutilisés octet pour octet depuis `copy_mapped_02`. Une vraie commande TARGET
configure les champs avant COPY. Aucun modèle ne remplace la validation COPY.

Pour coexister avec l'ancien observateur déjà dans cette netlist, seul le nom
de module du **nouveau helper externe de test** est changé en
`neo_capture_observed_test`. Son corps est vérifié identique au helper fourni.
Le DUT mappé n'est pas réécrit. Les fautes suivantes sont injectées explicitement
dans le banc ; elles ne représentent pas des observations faites sur la carte.

| Cas | Trace 64 bits | `descriptor_bad` |
|---|---|---|
| Capture correcte, largeur 16 | `d2670010100d0010` | `000` |
| CE COPY forcé à zéro | `d0470000100c0010` | `011` |
| Q largeur forcé à zéro | `d0670000100d0010` | `001` |
| D largeur forcé à zéro | `d0670000000d0000` | `001` |

Ce banc s'arrête à la première requête mémoire du COPY valide. Il ne comprend
pas le slot ni l'arbitre ; ses événements pending/accepted sont explicitement
zéro. Le résultat prouve la distinction des signatures observées, sans
qualification du chemin DDR ni du timing physique.

`mapped_copy_01` conserve un **échec du banc initial** : l'assertion de résultat
lisait les impulsions `copy_valid`/`done` après l'attente de snapshot. Elles
avaient déjà disparu normalement. Dans r2, le même contrôle est effectué au
premier événement, avant le snapshot. Le helper et les modules mappés sont
inchangés entre ces deux essais.

## Producteurs réels, slot et arbitre

`real_memory_events_01/result.json` : **PASS**. Le helper est raccordé aux
signaux réels de `gpu_accel`, de ses moteurs et de l'arbitre DDR. Aucun signal
interne n'est forcé et aucun producteur n'est remplacé. Le seul changement
du RTL R19 est le candidat CSR local documenté dans
`../neo_fable_sim_01/CSR_CANDIDATE.md`, nécessaire à Icarus quatre états.

- CLEAR : événements `1111`, en-tête **DF**. Treize comparaisons mémoire avec
  masques, pauses, backpressure séparé et annulation d'un slot au reset.
- COPY : événements `1110`, en-tête **DE**. Deux lectures et deux écritures
  réelles via le slot/arbitre, mémoire et gardes exactes.
- Détection explicite des X/Z sur les compteurs de commandes, le rejet GPU,
  les quatre événements et le payload d'un slot occupé.

Le premier Q privé COPY avant sa première capture est X dans le RTL non
initialisé, tandis que les FF mappées ont INIT=0. Ce champ pré-capture est
donc volontairement X dans la trace du banc RTL ; les bits d'événements et
le Q après capture doivent être connus. Le banc mappé ci-dessus vérifie
séparément le comportement INIT du matériel synthétisé.

## Portée du format

D/Q ne couvrent que les huit bits faibles de la largeur source. Les deux
échantillons sont pris au COPY_START et au cycle suivant, normalement
CAPTURE_WAIT. Les bits CHECK/VALIDATE/bad/done de ces échantillons ne sont
donc pas la cause finale de rejet. Les quatre sticky bits indiquent qu'un
événement a eu lieu ; ils n'en donnent ni le nombre ni l'ordre.
