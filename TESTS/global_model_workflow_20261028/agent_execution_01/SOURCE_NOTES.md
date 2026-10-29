# Sources et périmètre du candidat

Documentation primaire consultée le 28 octobre 2026 :

- https://opencode.ai/docs/agents/ : agent primaire, champ `steps`, borne des itérations internes.
- https://opencode.ai/docs/permissions/ : les permissions contrôlent les actions, elles ne remplacent pas une isolation OS.
- https://opencode.ai/docs/tools/ : les outils permettent lecture, édition et exécution.
- https://opencode.ai/docs/cli/ : `run --format json`, choix d'agent et reprise explicite par `--session`.

L'aide du CLI local1.19.4 a aussi été lue. Les schémas d'événements retenus
sont vérifiés sur les événements réellement enregistrés, pas uniquement sur
une documentation externe. Le prototype est Linux avec Bubblewrap ; les
outils sont isolés, tandis que le contrôleur OpenCode et le relais fournisseur
sont des composants hôte de confiance.

La démonstration `live_minimax_01` est une seule invocation CLI. Elle utilise
les octets sauvegardés dans son `runtime_snapshot`, antérieurs à la
séparation finale des compteurs. Sa métrique historique des tests reste
inchangée ; `evidence_01.json` distingue les trois commandes de test de
l'agent et les deux du superviseur.

Le module agent_audit généré a été relu et accepté par root avant intégration
au candidat. Son contrat porte surtout sur les résultats de commandes ;
un doublon tool_start/tool_finish qui changerait de nom n'est pas un cas de
conflit détecté par ce module. Le relais réel associe les réponses aux appels
qu'il a lui-même observés. Ne pas prétendre que ce compteur constitue un
validateur universel de tous les flux MCP.

Le launcher final corrige aussi l'enregistrement des réponses MCP
`isError:true`, sans réécrire la preuve MiniMax antérieure. Les tests
d'isolation finaux sont `isolation/tests_r4/result.json`.

Les continuations externes sont une option distincte, désactivée dans la
démonstration. Elles ne sont pas présentées comme les étapes internes de
cette session. Aucune intégration aux sources initiales ni aucun accès carte
n'a été effectué par le modèle.
