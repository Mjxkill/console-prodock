# Lecture des rapports Neo avec GAO

Les rapports contenant GAO ajoutent une section de ressources. Le tableau
`Global Clock Signals` passe de6 à7, sans disparition des huit PRIMARY.
Les parseurs imposaient le numéro6 et produisaient deux faux diagnostics
d'absence de table/horloges sur R10.

Le correctif ne change que
[timing_closure.py](../../../../tools/neo/timing_closure.py) et
[gpu_reset.py](../../../../tools/neo/gpu_reset.py), avec leurs deux tests
existants. Le premier fournit désormais un lecteur commun du tableau par
son titre. Il exige une section unique, une fin délimitée, des lignes complètes
et des types de ressources connus. Les doublons, tables vides ou tronquées
sont refusés. Un net peut apparaître sous PRIMARY et HCLK, comme dans les
vrais rapports ; aucune présence LW ne peut être masquée par une autre ligne.
Le contrôle spécifique demandant PRIMARY seul reste strict.

Résultats :

- 27 tests ciblés PASS, comprenant anciens/nouveaux numéros, changement
  réel de PRIMARY vers LW, table absente, dupliquée, tronquée et malformée.
- [Vrais rapports R9 et R10](real_report_validation.json) : huit PRIMARY
  identiques, `timing_closure` PASS, reset4LW toujours refusé.
- [Campagne complète](../../../dual_board/20261024_neo_gao_report_parser/result.json)
  11/11PASS, entrées inchangées, SHA
  `3fb3335591146562f1922d3538c3dfe9347aa9a691c6ebb5c77f105638a84309`.

La [qualification complète séparée](qualification_after_parser.json), SHA
`5e35d051311d3605729327b484a15636755af3c024e59a170de17070e7711dc3`,
reste **FAIL** : setup−0,849ns, hold−0,384ns, recovery−0,364ns,
removal+0,196ns ; le seul audit structurel restant FAIL est le reset4LW.
Les dix audits sont présents. Aucun seuil de timing, SDC, CST ou contrôle
fonctionnel n'a été modifié.

[qualify_separately.py](qualify_separately.py) exécute le qualificateur
inchangé et ne redirige que son unique écriture finale vers ce dossier.
Le [journal d'exécution](qualification_run.json) vérifie le SHA de l'outil
et la conservation du `qualification.json` initial. La destination originale,
ses logs et les quatre sources/tests avant modification sont archivés dans
`before/` et identifiés par [before_sha256.json](before_sha256.json).
Les empreintes finales sont dans [after_sha256.json](after_sha256.json).
Le rapport physique précédent reste figé avec son ancienne qualification.

Aucun rebuild, accès carte ou modification du candidat R10 n'a été effectué
pour cette correction. Les essais matériels restent distincts.
