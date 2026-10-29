# Missions OpenCode avec exécution

Ce mode délègue un travail complet : lecture des fichiers autorisés, édition
de la copie de tâche, tests réels, examen des échecs et corrections dans la
même session OpenCode. Il ne s'agit pas d'une succession de prompts présentée
comme une session autonome. Les éventuelles continuations externes sont
bornées et comptées séparément ; elles ne sont pas nécessaires au cas courant.

## Prérequis et limites

Linux, Python 3, OpenCode et Bubblewrap avec espaces de noms utilisateurs.
Le préflight vérifie l'isolation effective et échoue si elle est indisponible.
Les outils n'ont ni accès aux cartes ni réseau, ni répertoire personnel, ni clé
du fournisseur. `/usr` et les bibliothèques système sont montés en lecture
seule comme environnement d'exécution de confiance. Les tests sont bornés en
durée, mémoire et sortie. Ce mode ne remplace pas un essai matériel.

Un relais hôte transmet uniquement les requêtes du modèle sélectionné à
Ollama et compte les POST observés. La vraie clé n'est transmise ni à OpenCode
ni à son serveur d'outils. Les résultats conservent les noms de modèles
déclarés dans les réponses HTTP, sans prétendre connaître leur architecture
interne. Ne jamais placer de secret dans les fichiers autorisés ou le prompt.

La copie de tâche possède des entrées explicites : pas de copie générale du
dépôt. Les fichiers de contexte et de tests sont protégés en lecture seule ;
chaque fichier possédé est un montage modifiable distinct. Les répertoires
parents restent protégés. Les fichiers nouveaux doivent être déclarés dans
`owned` ; les compilations temporaires doivent écrire dans `/tmp`.
Les entrées sont actuellement limitées à 512 fichiers et 1 MiB par fichier.
Ne pas minifier ou découper artificiellement une ressource pour contourner
ces limites ; préparer un autre périmètre ou adapter le contrat explicitement.

## Préparer une mission

Exemple `tasks/repair_counter.json` dans le projet :

```json
{
  "schema": 1,
  "execution_mode": "execution",
  "task_id": "repair_counter",
  "domain": "tooling",
  "task_type": "implementation",
  "difficulty": "medium",
  "inputs": ["src/counter.py", "tests/test_counter.py", "CONTRACT.md"],
  "owned": ["src/counter.py"],
  "tests": [["/usr/bin/python3", "-B", "tests/test_counter.py"]],
  "timeout_seconds": 30,
  "require_initial_failure": true,
  "require_changes": true,
  "max_continuations": 0,
  "acceptance_criteria": "Corriger le compteur selon le contrat, tests protégés réussis et originaux inchangés.",
  "prompt": "Lis CONTRACT.md et les fichiers utiles avec les outils taskbox. Les chemins sont relatifs à /work. Lance run_tests avant modification, corrige uniquement src/counter.py, relance run_tests et répare les échecs constatés. Livre le résultat et ses limites."
}
```

`require_initial_failure` convient à une correction reproduite ; le mettre à
`false` pour une évolution partant de tests déjà verts. `require_changes` est
`false` pour une mission de tests seule ; `owned` peut alors être vide.
Fixer des critères observables, sans imposer de requêtes inutiles. Les chemins
passés aux outils de fichiers sont relatifs au dossier de tâche.

```sh
python3 -B ~/.codex/model-workflow/agent_runner.py --mode execution \
  --project /chemin/projet --spec /chemin/projet/tasks/repair_counter.json \
  --out /chemin/projet/results/repair_counter_minimax_r1 \
  --model minimax-m3.1-flash --run-id repair_counter_minimax_r1 \
  --registry /chemin/projet/results/metrics.sqlite \
  --credential-file /chemin/prive/secrets.env --prepare-only
```

Retirer `--prepare-only` pour exécuter. Le répertoire parent de `--out` doit
exister et la sortie doit être nouvelle. La clé peut aussi venir de
`OLLAMA_API_KEY`. Les quatre modèles autorisés restent exactement DeepSeek
`deepseek-v4.1-flash`, GLM `glm-5.3-flash`, MiniMax `minimax-m3.1-flash` et `beam`.
Le contrôle sans exécution ne prouve pas la disponibilité de l'isolation :
le préflight réel se fait lors du lancement. Aucune intégration dans le
projet original n'est automatique.

## Relire les preuves

Examiner `state.json`, les événements OpenCode, l'audit des outils, les retours
du relais fournisseur, la validation indépendante et le diff. Vérifier les
empreintes des entrées, les fichiers effectivement modifiés, les erreurs,
les interruptions et les processus résiduels. Un test en échec suivi d'un
test réussi doit apparaître dans les appels de l'agent lorsqu'il faisait
partie du contrat ; des tests du superviseur ne peuvent pas s'y substituer.

`metrics.json` sépare mode d'exécution, requêtes modèle, étapes, appels
d'outils, tests de l'agent et tests du superviseur. Les champs inconnus restent
inconnus. Une commande de test peut contenir de nombreux cas unitaires : ne
pas confondre ces deux nombres. Les sorties historiques antérieures conservent
leur périmètre de mesure d'origine ; leur preuve complémentaire le précise.

`COMPLETED_REVIEW_PENDING_VALIDATION` signifie qu'un candidat a été produit
et contrôlé, puis attend la revue du responsable. Ce n'est pas une acceptation
de qualité ni une autorisation de chargement sur carte. Codex évalue le
résultat, mesure sa revue quand possible et intègre les changements acceptés.

## File de missions

`agent_queue.py` adapte le moniteur commun aux missions avec outils. Les tâches
d'exécution déclarent `execution_mode: "execution"` et leur `packet` désigne
le JSON de spécification, lié par SHA256. La file d'avis `dispatch_queue.py`
exige explicitement `execution_mode: "review"`. Les deux modes réutilisent
la gestion des états, identités, dépendances et reprises ; aucune substitution
silencieuse. Consulter `agent_queue.py --help` pour le lancement.

## Contrôle local sans fournisseur

```sh
python3 -B ~/.codex/model-workflow/test_agent_isolation.py \
  --out /tmp/model-workflow-isolation-check-01
```

Choisir une sortie nouvelle. Ce test contrôle les restrictions et le cycle
test échoué → édition autorisée → test réussi via le serveur d'outils réel,
sans appeler de modèle. Il complète une preuve OpenCode réelle, sans la remplacer.

## Bornes des missions — 29 octobre 2026

Le lanceur autorise désormais 64 étapes et 128 tentatives HTTP par défaut.
Les plafonds configurables sont 256 étapes et 512 requêtes. La durée reste
900 secondes par défaut, avec un maximum de 3600 secondes. Ce sont des
limites de protection, jamais des objectifs de consommation : arrêter la
mission dès que les critères sont satisfaits. Choisir les bornes selon le
travail réel ; ne pas recopier systématiquement les anciennes limites
24/32 qui ont interrompu plusieurs missions utiles avant leur livraison.

Une limite atteinte reste un échec ou une livraison incomplète mesurée.
Conserver les preuves et préparer une reprise bornée, sans transformer
le résultat antérieur en succès. Les invocations déjà en cours conservent
leurs paramètres ; cette mise à jour ne les relance pas et ne les interrompt pas.
