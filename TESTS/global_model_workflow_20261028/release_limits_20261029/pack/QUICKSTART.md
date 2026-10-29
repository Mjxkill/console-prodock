# Exécuter et suivre les tâches déléguées

Prérequis : Python 3 sous Linux, OpenCode et Bubblewrap pour l'exécution. Ce paquet n'installe ni
modèle, ni clé. Les commandes suivantes supposent le paquet installé dans
`~/.codex/model-workflow`. Adapter les chemins du projet et les identifiants.
Choisir le mode avant de déléguer. Une mission d'implémentation/tests utilise
`agent_runner.py` et une spécification de copie isolée. Un avis textuel utilise
explicitement `runner.py --mode review`. Ne mettre aucun secret dans les paquets.

## Exécution avec outils

Le mode exécution donne à OpenCode les outils du périmètre de la tâche :
lecture, modification des seuls fichiers possédés et tests prévus au contrat.
Les tests s'exécutent dans une isolation système sans réseau, périphériques
ou secrets. La clé fournisseur reste dans le relais de l'orchestrateur.
OpenCode peut enchaîner les outils et les appels modèle dans la même session.
Codex garde la validation du résultat et son intégration dans le projet vivant.

Une preuve d'exécution conserve les requêtes HTTP observées, les appels
d'outils, les tests et leurs retours, les changements et le résultat des tests
indépendants. Une réponse qui annonce simplement « terminé » ne suffit pas.
La démonstration de correction exige un échec observé puis des tests réussis
dans une même session ; cette exigence ne force pas toutes les tâches futures
à échouer initialement ni à consommer un nombre artificiel de requêtes.

Les commandes et le schéma du mode exécution sont dans `AGENT_EXECUTION.md`.
Si l'isolation requise est indisponible, l'exécution s'arrête explicitement.
Elle ne se transforme pas silencieusement en simple avis textuel.

## Un avis textuel et sa preuve locale

Préparer `tasks/diagnostic.txt` dans le projet : faits, périmètre, livrable,
interdictions et tests attendus. Le parent de `--out` doit déjà exister ; le
dossier de sortie lui-même doit être nouveau. `--prepare-only` vérifie les
arguments sans lire la clé, contacter le service ou créer les résultats.

```sh
python3 -B ~/.codex/model-workflow/runner.py --mode review \
  --project /chemin/projet --packet tasks/diagnostic.txt \
  --out /chemin/projet/results/diagnostic_beam_r1 \
  --model beam --task-id diagnostic --run-id diagnostic_beam_r1 \
  --domain fpga --task-type diagnosis --difficulty medium \
  --acceptance-criteria 'Séparer faits et hypothèses ; proposer un test discriminant.' \
  --max-output-tokens 65536 --timeout 900 --prepare-only
```

Retirer `--prepare-only` pour exécuter. La clé provient de `OLLAMA_API_KEY` ou
d'un fichier explicite `--credential-file /chemin/prive/secrets.env` contenant
son affectation. Ne pas passer la clé dans les arguments. Les quatre noms
acceptés sont `deepseek-v4.1-flash`, `glm-5.3-flash`, `minimax-m3.1-flash`,
`beam`. Claude exige `--model claude --allow-claude --claude-model NOM`.
`--reasoning-effort` n'est configuré que pour DeepSeek ; laisser `unspecified`
pour les autres adaptateurs. Le budget est une demande au fournisseur ; les
résultats effectifs et les éventuelles troncatures restent enregistrés.

`status.json` suit l'exécution ; `metrics.json`, `answer.txt`, `events.jsonl`
et `registry_import.json` conservent le résultat. Le statut de génération
`COMPLETED_REVIEW_PENDING_VALIDATION` n'est pas une acceptation technique.
Un échec, un dépassement de délai ou une réponse tronquée sort avec un code
non nul. Une erreur d'import dans le registre est également explicite et
conserve la preuve locale ; ne pas relancer le modèle pour réimporter celle-ci.

## File d'avis isolée par session

Chaque session utilise son propre dossier, par exemple `results/session_alpha`.
Calculer le SHA256 du paquet avec `sha256sum tasks/diagnostic.txt`, puis créer
un fichier JSON de ce format (remplacer l'empreinte) :

```json
{
  "schema": 1,
  "max_active": 4,
  "jobs": [{
    "task_id": "diagnostic",
    "run_id": "diagnostic_beam_r1",
    "model": "beam",
    "execution_mode": "review",
    "packet": "tasks/diagnostic.txt",
    "packet_sha256": "SHA256_DU_PAQUET",
    "domain": "fpga",
    "task_type": "diagnosis",
    "difficulty": "medium",
    "acceptance_criteria": "Séparer faits et hypothèses ; proposer un test discriminant.",
    "priority": 10,
    "max_output_tokens": 65536,
    "after": []
  }]
}
```

```sh
sha256sum ~/.codex/model-workflow/runner.py
python3 -B ~/.codex/model-workflow/dispatch_queue.py \
  --project /chemin/projet --session /chemin/projet/results/session_alpha \
  --queue /chemin/projet/tasks/queue.json \
  --runner ~/.codex/model-workflow/runner.py --runner-sha256 SHA256_DU_RUNNER
```

Cette commande contrôle seulement. Ajouter `--run` pour lancer les tâches
prêtes ; `--credential-file` et `--registry` sont transmis au runner. Priorité
la plus élevée d'abord. Une dépendance utilise
`{"task_id":"diagnostic","condition":"on_success"}` ou `on_terminal`.
`on_success` signifie génération complète, pas revue humaine acceptée : une
tâche d'intégration exige une nouvelle décision explicite du responsable.

La file est **figée pendant une invocation**. Ajouter des tâches puis relancer
le moniteur après sa fin ; les anciennes tâches et leurs spécifications sont
immuables. Pas de rechargement à chaud ni de reprise infinie. Un résultat
incertain devient `NEEDS_REVIEW` ; ses dépendants deviennent
`BLOCKED_UNRESOLVED`. Un échec connu bloque `on_success`, mais autorise
`on_terminal`. Une interruption du moniteur ne tue pas arbitrairement ses
enfants et n'autorise pas leur double lancement : résoudre l'état enregistré
avant de préparer une nouvelle tentative avec un nouveau `run_id`.

## Registre, jugement et statistiques

Chaque tentative importe ses mesures dans
`~/.codex/model-workflow/data/metrics.sqlite` par défaut. `--registry` permet
un registre de projet explicite. Durées monotones, dates UTC et empreintes sont
observées ; tokens absents restent `null`. Un coût numérique sans devise n'est
pas une facture et un zéro fourni par un SDK ne prouve pas la gratuité.

```sh
python3 -B ~/.codex/model-workflow/metrics.py \
  --db ~/.codex/model-workflow/data/metrics.sqlite import /chemin/run/metrics.json
python3 -B ~/.codex/model-workflow/metrics.py \
  --db ~/.codex/model-workflow/data/metrics.sqlite evaluate /chemin/assessment.json
python3 -B ~/.codex/model-workflow/metrics.py \
  --db ~/.codex/model-workflow/data/metrics.sqlite report --format html \
  --out /chemin/rapport_nouveau.html
```

L'évaluation indépendante lie `run_id`, SHA du résultat, critères et preuves.
Son schéma est validé par `metrics.py` ; les notes et temps de revue ne sont
jamais inventés par le runner. Voir `WORKFLOW.md` pour la grille et les limites
des comparaisons. Les rapports existent aussi en JSON et CSV. Les tentatives
en erreur et les révisions d'évaluation restent visibles.

## Taille du code et fiche de tests

Créer un manifeste recensant explicitement les fichiers concernés :

```json
{"version":1,"files":[{"path":"src/module.py","ownership":"project"}]}
```

```sh
python3 -B ~/.codex/model-workflow/check_code_size.py \
  --project /chemin/projet --manifest /chemin/projet/tasks/code_manifest.json
```

Code projet : au plus 1 000 lignes physiques. Les exemptions `vendor` et
`archive` exigent une raison explicite. Le contrôle refuse les liens symboliques,
fichiers absents et chemins sortant du projet. Il ne découvre pas automatiquement
les fichiers oubliés du manifeste. Conserver une fiche issue de
`TEST_RECORD_TEMPLATE.md` avec versions, attentes, résultats et limites.
