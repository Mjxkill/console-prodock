# Rectification de l'attribution des écarts externes

Relecture contradictoire root du 28 octobre 2026, après la première livraison.

Les valeurs calculées dans `result.json` sont reproductibles : le helper Beam
renvoie 5 pour quatre notes à 5 et 1 comme quantile nearest-rank à 50 % de
`[1,9]`. Elles ne satisfont pas le contrat final du registre (score sur 100,
médiane statistique 5 pour cet échantillon).

**Ce constat ne démontre pas deux erreurs intrinsèques de Beam.** Le paquet
`metric_packets/stats_helpers.txt` n'explicitait pas l'échelle sur 100 et
contenait « Median and p90 nearest-rank ». Beam a donc pu suivre littéralement
la consigne effectivement reçue. Le chef de projet avait les exigences finales
mais ne les a pas transmises assez précisément. La bonne disposition est :
non-intégration pour incompatibilité avec le contrat final, avec défaut de
spécification de la sous-tâche, pas pénalisation automatique de qualité du modèle.

De même, le paquet DeepSeek contenait les noms de schéma préliminaires avant
l'alignement avec le runner. La proposition a suivi ces noms. Les adaptations
`schema`, `event`, `elapsed_seconds` et les identités d'évaluation sont des
adaptations à notre interface finale, pas des erreurs imputables au modèle.

Les réponses originales, paquets, transformations, tests et premier rapport
sont conservés. Aucune note de qualité n'a été attribuée par ce dossier.
Une évaluation indépendante doit prendre le paquet réellement reçu comme
contrat, distinguer erreur de consigne et erreur de réponse, et lier ces preuves.
