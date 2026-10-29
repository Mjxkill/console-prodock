# Audit des lancements OpenCode du 28 octobre 2026

Périmètre : cinq lots récents listés dans result.json ; hors historique complet du compte. Chaque tentative possède une réponse OpenCode, un événement de fin et une empreinte de réponse vérifiée.

| Modèle demandé | Tentatives | Complètes | Tronquées | Tokens déclarés |
|---|---:|---:|---:|---:|
| beam | 6 | 5 | 1 | 99604 |
| deepseek-v4.1-flash | 5 | 4 | 1 | 138307 |
| glm-5.3-flash | 2 | 2 | 0 | 70332 |
| minimax-m3.1-flash | 2 | 2 | 0 | 81572 |

Les configurations ciblent https://ollama.com/v1 avec un seul modèle déclaré, identique au modèle demandé. Le runner ne prévoit pas de remplacement par DeepSeek. Ces preuves ne constituent pas un relevé de facturation : les journaux ne conservent pas le champ modèle de la réponse HTTP brute ni l’identité du compte du tableau utilisateur. L’écart signalé dans les compteurs externes reste à expliquer.

Une réponse complète n’est pas une proposition techniquement validée. Les évaluations sont séparées.

## Compteurs du fournisseur

Lecture authentifiée de `/api/usage?range=24h&scope=self&group_by=model`, le 2026-10-28T14:58:48.292406+00:00. Fenêtre effective : 2026-10-27T14:00:00Z → 2026-10-28T14:58:48.445722316Z.

| Modèle enregistré par Ollama | Requêtes |
|---|---:|
| deepseek-v4.1-flash:1017 | 4613 |
| beam | 394 |
| minimax-m3.1-flash | 74 |
| glm-5.3-flash | 2 |

Total : 5 083 requêtes, dont 90,8 % DeepSeek. Ce relevé couvre le compte de la clé configurée, toutes sessions confondues ; il ne permet pas d’attribuer 5 083 requêtes à ce projet. Beam est présent côté fournisseur. La cause du zéro vu dans la page utilisateur (période, filtre ou métrique) reste inconnue. Les compteurs locaux de cinq lots et ces compteurs du compte ne sont pas le même périmètre.

Le runner actuel désactive les outils et ne lance qu’une génération par mission. Ce choix explique qu’une tâche longue puisse ne consommer qu’une requête ; ce n’est pas une limitation d’OpenCode. Le mode agent avec modification/tests/correction doit être validé séparément avant d’être annoncé opérationnel.
