# Contre-revue locale — comptabilisation des modes, release_02

**Conclusion : aucune réserve bloquante restante dans le périmètre relu.**
Un défaut de liaison du mode lors de la reprise de file a été reproduit puis
corrigé par root. Le contre-test confirme son refus sur les octets finaux.
Les 47 tests ciblés passent avant et après la correction ; ils ne suffisaient
pas seuls à détecter ce défaut, d'où les quatre cas adverses supplémentaires.

Cette revue concerne `pack/metrics.py`, `runner.py`, `dispatch_queue.py` et leurs
tests. Elle n'est pas la validation du futur moteur agent multiétape, de son
isolation, d'un appel fournisseur réel ou de la publication sur deux machines.
Aucun accès réseau, clé, carte ni registre global n'a été effectué. Les tests
ont tourné sur copies temporaires, supprimées après exécution. L'agent relecteur
n'a modifié aucun fichier de `pack/` ou `tests/`.

## Empreintes finales relues

| Fichier | SHA-256 |
|---|---|
| `pack/metrics.py` | `b1c0abc3e609e79d2a33836b0276ee0e6a3e62e9823bc7d379ff2ffabb33dbfb` |
| `pack/runner.py` | `389be0c6474cbab07fd09001f6921de3b46c2061896215f0a32282ac98b60f69` |
| `pack/dispatch_queue.py` | `e6e601d5d8f7b11ab4919d9c08eff832afeef29099cd2ceedf78d97cae347c9d` |
| `tests/test_queue.py` | `ceab060b2507a14e6e7c435445d4b2ce4f974204c4bce95e49332ef7f8f943d2` |

Toutes les autres empreintes du lot exécuté et le contrôle d'absence de
modification pendant les tests figurent dans
`root_accounting_checks_r1/final_checks.json`, SHA-256
`cf34daa0e3aa5875308576d08d55d9cbc05f4f54bcee5e7f3598a8e3a16dad1f`.

## Défaut trouvé, puis fermé

Dans la version initiale de `dispatch_queue.runner_status`, les identifiants de
tâche/tentative, modèle, paquet, statut, métriques et preuve d'import étaient
liés, mais **le mode d'exécution du résultat n'était pas comparé à celui de la
tâche**.

Contre-exemple injecté, sans processus fournisseur : une tâche explicitement
`review`, préalablement marquée `RUNNING`, reçoit un résultat portant
`execution_mode=execution`, avec tous les autres identifiants corrects et une
preuve d'import liée au SHA des métriques. La reprise adoptait
`COMPLETED_REVIEW_PENDING_VALIDATION` et rendait prêt un dépendant `on_success`.
Ce n'était pas un comportement observé du runner actuel, qui produit bien
`review`, mais un trou dans la barrière d'adoption d'un résultat inattendu.

La preuve initiale est conservée dans
`root_accounting_checks_r1/adversarial_r2.json`, sur la file SHA-256
`a839340806518a512e8fa6d227a3740c0e40849c7129835fdd9ad0c73851121c`.
Les fixtures initiales de tests produisaient elles-mêmes des résultats sans
mode ; elles expliquent pourquoi la suite existante passait.

Root a ajouté la vérification à `dispatch_queue.py:109` et enrichi les fixtures.
La relecture finale vérifie quatre résultats adverses :

| Résultat proposé à une tâche review | Résultat final constaté |
|---|---|
| Mode `execution` | Refus |
| Mode absent | Refus |
| Mode `review`, configuration déclarée `execution` | Refus |
| Mode `review`, `model_config` non objet | Refus |

Dans les quatre cas, la reprise laisse la tâche `NEEDS_REVIEW`, le dépendant
`BLOCKED_UNRESOLVED` et ne rend pas `on_success` prêt. Le résultat antérieur
erroné n'est pas réétiqueté comme réussite de test.

Preuve finale : `root_accounting_checks_r1/adversarial_final.json`, SHA-256
`7af48d233b486585be1c9ba017899a8bc5cab883436a6123a5219aaafc125056`.
Le futur adaptateur de file des agents devra conserver la même liaison entre
mode demandé et mode obtenu ; cette revue ne prétend pas l'avoir testé.

## Contrôles satisfaits

### Modes et ancien registre

- `metrics.py:198` refuse les modes inconnus et la contradiction entre le champ
  principal et `model_config.execution_mode`.
- Une ligne historique dépourvue de mode reste `legacy_unspecified` dans le
  rapport. Elle n'est pas convertie silencieusement en review ou execution.
- Le mode fait partie de la clé de cohorte, en plus du projet, du domaine, du
  type, de la difficulté, du modèle et de sa configuration. Les mêmes tâches
  réparties entre les trois modes produisent trois cohortes distinctes.
- Aucun `UPDATE` ni migration des lignes historiques n'est ajouté. Le test
  compare les lignes complètes de `runs` avant et après JSON/CSV/HTML : elles
  restent identiques, y compris le `raw_json` ancien sans mode. Cela qualifie les
  données, pas une identité octet par octet du fichier SQLite/WAL.
- Les conflits de réimportation du même `run_id` avec des métriques modifiées
  restent refusés ; les évaluations conservent leurs preuves et leur historique.

### Inconnu n'est pas zéro

- Les quatre compteurs `model_requests`, `tool_calls`, `test_runs`,
  `test_failures` admettent `null`/absence ; valeurs négatives, booléens et plus
  d'échecs que de tests connus sont refusés.
- Pour les anciennes lignes sans compteur, les totaux restent `null`, avec le
  nombre de valeurs inconnues. Un zéro explicitement observé reste zéro.
- Dans une cohorte mêlant une mesure nulle et un zéro observé, le rapport donne
  le **total des observations connues** égal à zéro et `unknown=1`. Il ne faut
  pas interpréter ce total partiel comme une mesure exhaustive de la cohorte.
- Le runner review déclare zéro outil/test, cohérent avec son exécution sans
  outils, et laisse le nombre réel de requêtes modèle `null` : il n'invente pas
  une requête par processus OpenCode.
- Qualité et fin de génération restent distinctes : le runner conserve
  `pending_independent_evaluation`, sans score automatique.

### Exports et barrières de lancement

- CSV contient `execution_mode` ainsi que total et nombre d'inconnus pour chaque
  compteur. Une valeur entièrement inconnue est une cellule vide avec son
  compteur d'inconnus, distincte de la chaîne `0`.
- HTML montre le mode et les inconnus. Les protections d'échappement HTML/CSV
  existantes restent couvertes par les tests de labels malveillants.
- `runner.py:37` exige `--mode review` ; une commande autrement complète sans
  cette option est refusée au parseur, avant accès aux identifiants ou réseau.
- `dispatch_queue.py:49` refuse les jobs de mode absent, legacy ou execution.
  La commande lancée comporte explicitement `--mode review` à la ligne 218.
  Il n'y a pas de conversion automatique d'une demande execution vers review.
- Après correction, les résultats inattendus sont également refusés à la
  reprise de file, et non seulement à la validation de sa description initiale.

## Tests et preuves conservées

Les modules `test_runner`, `test_queue`, `test_metrics` et
`test_execution_metrics` totalisent **47 tests PASS** sur copies du lot final.
Ils couvrent notamment erreurs, troncature, timeout, import concurrent,
évaluations, empreintes, dépendances et redémarrage de file.

Les cas complémentaires utilisent de vraies bases SQLite temporaires et les
fonctions exactes du lot copié. Ils contrôlent trois modes, compteurs absents
versus zéro, exports, absence de réécriture et les quatre refus de résultats.

- `root_accounting_checks_r1/unit_tests.log` : résultat initial, avant correction.
- `root_accounting_checks_r1/unit_tests_final.log` : résultat final.
- `root_accounting_checks_r1/inputs.json` : empreintes du premier lot.
- `root_accounting_checks_r1/adversarial_r2.json` : contre-exemple initial.
- `root_accounting_checks_r1/adversarial_final.json` : refus après correction.
- `root_accounting_checks_r1/reproduce.py` : producteur local reproductible.
- `root_accounting_checks_r1/final_checks.json` : empreintes et contrôles finaux.

Pour rejouer les cas complémentaires sans accès externe depuis la racine :

```sh
python3 -B TESTS/global_model_workflow_20261028/release_02/reviews/root_accounting_checks_r1/reproduce.py
```

Un changement des entrées invalide ce rattachement ; il faut alors relire le
diff concerné et rejouer les contrôles affectés. Cette conclusion est bornée au
lot identifié ci-dessus, sans garantie générale d'absence de toute erreur.
