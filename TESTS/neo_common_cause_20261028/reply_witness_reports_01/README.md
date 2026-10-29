# R22r1 : lancement isolé avec rapports ciblés

État : prêt à la relecture root. Aucun lancement Gowin ou accès carte par cet agent.
Cette copie est un témoin diagnostique UTW1 ; ce n'est pas un correctif Neo.

## Cause précise du refus R22

R22 a échoué en 1,23 s à la lecture `.vg`, avant placement/routage : PA2060 sur
les ports bus sans sélection explicite et des nets `[0:0]` nommés avec un point,
puis PA2000 sur une affectation comportant sélection de tranche/concaténation.
Ces erreurs relèvent du format de sérialisation accepté par le lecteur Gowin.
Elles ne constituent ni une preuve de défaut matériel, ni un échec de timing.
Le journal R22 et le candidat original sont conservés.

R22r1 sérialise le graphe mappé existant : 1 213 primitives, paramètres et connexions
bit à bit conservés. Aucun algorithme ni synthèse globale n'a changé. Les noms
internes sont scalaires simples, les cinq ports bus du témoin ont une sélection
complète explicite et les aliases ont été résolus dans le graphe des bits.
La réversion des deux blocs modifiés retrouve exactement les octets R22.

Les deux scoreboards de 12 013 cycles, six injections de débordement et neuf
simulations d'intégration (trois relations d'horloge × trois scénarios) passent.
Les scénarios séparent faute au mot 1 de la FIFO et faute de validité en banque ;
ils ne démontrent pas la cause de l'anomalie matérielle R19. Les 11 groupes
Pro Dock/Neo de `TESTS/dual_board/20261028_utw1_format_r1` passent également.
La preuve est `../reply_witness_format_r1/tests_02/result.json`.

## Cette copie change uniquement les demandes de rapports

Parent intact : `tang/impl/console_neo_n56r22r1_utw1_format`.
Copie à lancer : `tang/impl/console_neo_n56r22r1_utw1_reports`.
Netlist dans les deux dossiers :
`0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191`.

Le CST, le RTL du snapshot, les options et la netlist sont identiques.
Les chemins absolus du Tcl pointent vers la copie. Le SDC garde le parent entier,
byte pour byte, et ajoute 2 604 `report_timing` : pour chacun des 402 FF témoins
et des 32 FF hrdata, setup et hold ciblent individuellement D, CE et RESET.
Aucune contrainte d'horloge, de délai ou d'exception n'est ajoutée/modifiée.
`sources.json` ne diffère que par l'empreinte de ce SDC. Les rapports globaux
préexistants sont conservés sans modification.

La syntaxe est documentée dans SUG940-2.0.4E §5.5.1 p.73–75, document local
identifié par SHA dans `reports_assembly.json`. Huit contrôles locaux passent,
dont l'analyse réelle des 2 604 appels par Tcl avec stubs inertes et le refus
contre mutations de contrainte, endpoint, suppression de rapport et borne.
Ces contrôles ne prouvent pas la résolution de noms dans Gowin.

Les requêtes utilisent `max_paths 10000`, `max_common_paths 3`. Cette borne élevée
peut augmenter la taille et la durée de génération des rapports. Elle a été
conservée après gel pour ne pas créer une nouvelle variante. Un endpoint sans
chemin actif, introuvable, ou un rapport tronqué reste à qualifier, jamais PASS
par défaut. Le pire slack de chaque endpoint et les violations globales seront
à examiner après le routage. Les tests de logique restent liés à la même netlist.

## Commande root et garde

```sh
python3 TESTS/neo_common_cause_20261028/reply_witness_reports_01/launch_reports.py --check-only --review <revue-root.json>
python3 TESTS/neo_common_cause_20261028/reply_witness_reports_01/launch_reports.py --run --review <revue-root.json>
```

La revue exige `passed: true`, `purpose: "UTW1 syntax and reports full PNR"`,
les SHA `netlist_sha256`, `format_assembly_sha256`, `reports_assembly_sha256` et
`launcher_sha256`. Les valeurs sont dans `tests.json` et les manifestes du build.
Lancer seulement cette copie, jamais le parent en parallèle. Le P&R est complet ;
aucune hypothèse `inc_pnr` sur une netlist modifiée. Le verrou et les journaux
sont propres à ce build ; aucun autre compilateur n'est arrêté.

L'audit structurel à venir vérifiera les 402 FF, leurs CLK/RESET, tous les pins,
les paramètres et les drivers, les 32 mux de lecture et l'absence de retour
vers les chemins anciens. La présence dans les rapports ne vaut pas fermeture
STA. Le bitstream, le timing et l'essai matériel restent distincts et non qualifiés.

Le décodeur offline gelé du témoin initial est lié au SHA original `fa0185…`.
Il refusera cette netlist `0eb563…` sans adaptateur de provenance isolé et revu.
Ne pas modifier ce décodeur gelé ni lancer une collecte avec une garde affaiblie.
