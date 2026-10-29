# Résultat local figé

`result.json` confirme le PASS complet du cône mappé exact et de la comparaison
RTL couplée :16scénarios,15libérations attendues,707,106732260ms simulées.
La qualification physique et les essais carte restent distincts et en attente.
Le résultat complète le README rédigé pendant les essais, sans réécrire cette
preuve déjà liée par son empreinte.

L'audit postroute est prêt : `audit_preparation.json`, avec huit contrôles
positifs/négatifs et vérification du lecteur de rapports sur R21r1. Le lecteur
retrouve exactement les quatre anciens chemins init_sync (recovery8,851ns,
removal1,416ns) ; ces nombres ne sont pas des résultats du nouveau candidat.
La première version de l'aplatissement de ports avait produit up[2][2] au lieu
de up[2] pour un port déclaré[2:2]. Le témoin a rejeté ce graphe, puis le lecteur
a été corrigé en vérifiant la largeur et l'indice. Aucun RTL n'a changé.

Après achèvement du routage, uniquement sur revue de la session principale :

```sh
python3 TESTS/neo_720p_20261012/capture_memory_20261027/reset_contract_01/candidate_02/audit_routed.py --out TESTS/neo_720p_20261012/capture_memory_20261027/reset_contract_01/candidate_02/postroute_01.json
```

Cet audit refuse un routage incomplet, vérifie les empreintes avant et après
lecture et conserve les preuves manquantes. Il ne charge pas la carte et
ne remplace pas les audits complets DDR/GPU/observateur et le timing global.
