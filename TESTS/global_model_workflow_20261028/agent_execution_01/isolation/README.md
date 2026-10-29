# Exécution d'outils isolés pour OpenCode

Ce lot fournit une isolation Linux effective aux outils, indépendante des
permissions du modèle. Il ne modifie pas la configuration installée. La première
session OpenCode réelle est conduite par le responsable du runner ; les preuves
locales de ce dossier portent sur Bubblewrap et le serveur MCP.

## Architecture et frontière de confiance

OpenCode est le client du modèle, en dehors de la boîte. Les outils natifs sont
interdits ; seul le serveur MCP `taskbox` est autorisé. Les règles OpenCode
servent à choisir les outils exposés, **pas** de frontière système. Cette
configuration est documentée par les pages officielles sur les
[permissions](https://opencode.ai/docs/permissions/) et les
[serveurs MCP locaux](https://opencode.ai/docs/mcp-servers/).

Chaque serveur MCP et ses commandes fonctionnent dans Bubblewrap : namespaces
utilisateur/PID/réseau/IPC/UTS, capacités retirées, user namespaces imbriqués
désactivés, `/proc` privé et `/dev` minimal. La racine du projet hôte n'est pas
montée. Seule une copie explicite des fichiers de tâche apparaît dans `/work`.
Le répertoire est en lecture seule ; chaque fichier possédé est un bind writable
individuel. Les nouveaux fichiers autorisés sont précréés vides. Une commande
peut écrire leur contenu, mais pas remplacer les binds par des liens ou modifier
les tests protégés. Les fichiers de compilation temporaires vont dans `/tmp`.

Le runtime système `/usr` et les répertoires de bibliothèques présents (`/lib`,
éventuellement `/lib64`) sont exposés en lecture seule pour Python/compilateurs.
Ce profil suppose ces répertoires réservés au runtime de confiance : il ne
constitue pas une image système minimale auditée fichier par fichier. `/home`,
`/etc`, `/sys`, les périphériques réels, les sockets hôte et les autres projets
ne sont pas montés. Une machine stockant des secrets dans son runtime système
nécessiterait une image de dépendances dédiée avant utilisation.

La clé fournisseur et le jeton local du proxy ne sont jamais transmis au
launcher MCP : `env -i`, puis `--clearenv` et une liste réduite d'environnement.
Le serveur PID1 est non-dumpable. Ses enfants ne peuvent rouvrir ses descripteurs
ou sa mémoire via `/proc/1`, ce qui protège la liaison MCP contre l'injection
directe de faux résultats. Le journal est écrit par le relais hôte, hors boîte.

OpenCode, le proxy du fournisseur, le launcher et les modules Python sont des
composants de confiance. Ce n'est pas une machine virtuelle, ni une garantie
contre une vulnérabilité du noyau ou de ces composants. Les permissions des
[outils natifs OpenCode](https://opencode.ai/docs/tools/) doivent rester
interdites ; ajouter un autre outil hôte invalide cette frontière.

## API et fichiers à publier

Publier dans le même répertoire que le runner global, sans duplication maintenue :

- `agent_isolation.py` : copie, manifestes, construction de commande, préflight,
  tests indépendants et collecte du diff ;
- `agent_box.py` : sous-commandes bornées et tests fixes, exécutés dans la boîte ;
- `agent_mcp.py` : protocole MCP et quatre outils contrôlés ;
- `agent_mcp_launcher.py` : relais stdio et journal hôte ;
- `test_agent_isolation.py` : contre-tests sans modèle ni clé.

Le manifeste lie les quatre modules et la politique par SHA-256. Un changement
de module exige une nouvelle préparation. Le responsable du runner doit aussi
lier ces fichiers au manifeste de release et conserver les résultats des essais.

```json
{
  "schema": 1,
  "project": "/chemin/projet",
  "inputs": ["src/module.py", "tests/test_module.py"],
  "owned": ["src/module.py"],
  "tests": [["python3", "-B", "tests/test_module.py"]],
  "timeout_seconds": 30,
  "require_changes": true
}
```

`owned: []` est accepté pour une mission de tests seule lorsque
`require_changes` vaut `false`. Les chemins doivent être relatifs, réguliers,
sans traversée ni lien symbolique. Les fichiers de secrets usuels sont refusés,
mais la sélection du contenu autorisé reste la responsabilité de l'orchestrateur.

`prepare(spec, out)` exige un dossier neuf et rend un manifeste avec
`manifest_path` et `journal_path`. `mcp_config(path)` produit l'entrée `taskbox`
pour la configuration MCP. `preflight(path)` doit réellement passer avant le
premier lancement. `run_tests(path)` exécute les commandes fixes dans une boîte
neuve ; `collect_changes(path)` vérifie les originaux/contextes et rend seulement
le diff des fichiers possédés. Aucune fonction ne fusionne ce diff au projet.

Outils exposés : `read_file(path)`, `write_file(path, content)`, `exec(argv)` et
`run_tests()`, préfixés `taskbox_` par OpenCode. Les tests officiels sont les
commandes fixes de la politique ; un `exec` exploratoire n'est pas compté comme
un test officiel. `test_runs` compte les commandes réellement lancées et
`test_failures` celles dont le code de retour réel n'est pas nul. Timeout ou
sortie excessive invalident aussi le résultat, même avec un code de retour nul.

## Vérification sur chaque hôte, sans clé

Dépendances : Linux autorisant les user namespaces, Bubblewrap, Python 3 et
ses bibliothèques standard. Aucun Docker, paquet npm, modèle ou clé n'est requis
pour le banc d'isolation. `/lib64` est conditionnel pour la portabilité ARM64.

Après déploiement du paquet sur gx10-1, exécuter avec un chemin de sortie neuf :

```sh
python3 -B ~/.codex/model-workflow/test_agent_isolation.py \
  --out /tmp/model-workflow-isolation-check-01
```

Lire ensuite `result.json` et exiger `passed: true`. La session de travail
Codex locale restreint `NETLINK_ROUTE` : le test y échoue, tandis que le même
test exécuté dans le contexte hôte explicitement autorisé passe. Aucun montage
alternatif ni assouplissement silencieux n'est utilisé. Si le préflight échoue
sur un autre hôte, le mode exécution doit rester bloqué, sans fallback vers un
simple réglage de permissions OpenCode.

## Preuves actuelles et limites

`tests_r4/result.json` : **14 groupes PASS**. Le banc observe un test réellement
échoué, une modification autorisée, puis le test réussi via le protocole MCP,
et vérifie le diff final contre les originaux. Il teste aussi lecture externe,
liens, traversée, secrets/env, connexion réseau externe/localhost hôte, accès
matériel absent, protection du parent, tests RO, timeout et sortie bornée.
Les PID/start_ticks et fins du launcher et de Bubblewrap sont journalisés.
Le contre-test supplémentaire vérifie qu'une réponse MCP `isError: true`, même
accompagnée d'un résultat de test prétendument réussi, reste une erreur et ne
produit aucun événement `test_finish` fictif.

`tests_r1` conserve l'échec initial de construction de commande : cette version
de Bubblewrap exige `--unshare-user` explicite avec `--disable-userns`.
`tests_r2` précède les identités PID. `tests_r3` est la version utilisée pendant
la première session Minimax réelle, avant le correctif de comptabilité MCP.
Aucun résultat antérieur n'a été écrasé.
La preuve finale OpenCode multiétape relève du dossier de démonstration du
runner, pas de ce banc synthétique. Aucun matériel n'a été utilisé.
