# OpenCode : exécution réelle et publication globale

28 octobre 2026. Le paquet est installé sur cette machine et sur
`michael@gx10-1`, dans `~/.codex/model-workflow`. Les consignes globales
`~/.codex/AGENTS.md` distinguent maintenant exécution et avis.

## Changement livré

Le précédent runner fournissait un avis textuel sans outils. Il reste
disponible avec `runner.py --mode review`. Pour une implémentation ou des
tests, `agent_runner.py --mode execution` donne à OpenCode une copie des
fichiers autorisés : lecture, modifications, tests, corrections dans la
même session. Les outils travaillent dans Bubblewrap. Tests et contexte
sont protégés, seuls les fichiers possédés sont modifiables. Aucun accès
matériel, réseau ou secret fournisseur depuis les outils.

La file d'exécution réutilise le moniteur commun : identités, verrous,
dépendances, reprises bornées et résultats vérifiés. La finalisation d'une
mission attend toujours la revue de Codex. Les tests peuvent réussir sans
que la mission soit acceptée, notamment si sa session est tronquée.

Les mesures séparent missions, requêtes HTTP réellement observées, étapes
du modèle, outils, commandes de tests de l'agent et du superviseur. Les
modes avis et exécution forment des cohortes distinctes. L'historique n'est
pas réécrit ; les valeurs inconnues restent inconnues.

## Versions et preuves

- Manifeste des 26 fichiers :
  `df4663d5224a6897c1e38636eac2c43dda0bcd0713acbd56aec77b96b484c493`.
- [Publication et contrôles d'identité](publication.json) : les deux
  installations correspondent au paquet ; seconde préparation sans changement.
- [Validation locale](local_validation.json) : 95 tests au total. Le premier
  passage a 94 succès et un refus de socket par le bac à sable extérieur ;
  ce test HTTP local passe ensuite hors de ce bac à sable. Ce refus reste
  dans le journal initial.
- [Isolation locale](local_isolation_02/result.json) et
  [isolation ARM distante](gx10_proof/isolation_01/result.json) : 14 groupes
  chacun, dont restrictions d'accès, erreurs MCP, délais, limites de sortie,
  échec avant modification et réussite après modification.
- [Migration](migration_test.json) : 12 vers 26 fichiers, sauvegardes,
  idempotence, conservation des consignes extérieures, configuration et données.

## Missions réelles

| Mission | Modèle exact | Durée | Requêtes HTTP | Outils | Résultat |
|---|---|---:|---:|---:|---|
| Première preuve locale, runtime antérieur archivé | minimax-m3.1-flash | 88,90 s | 15 | 16 | Tests échoués, édition, tests réussis ; revue acceptée |
| Essai ARM avec OpenCode 1.15.10 | glm-5.3-flash | 104,23 s | 8 | 9 | Code testé, mais événement final absent : mission conservée en échec |
| Essai ARM final avec OpenCode 1.19.4 | glm-5.3-flash | 89,78 s | 6 | 7 | Cycle complet et 9 tests protégés réussis ; revue acceptée |

La [revue ARM finale](gx10_execution_review.json) lie les fichiers et leurs
empreintes. Les processus d'outils ont quitté et les originaux sont inchangés.
Son implémentation alternative reste une preuve de validation ; elle ne
remplace pas le module MiniMax déjà relu dans le paquet. La première preuve
MiniMax conserve les compteurs de sa version : ne pas la présenter comme
une exécution du paquet final.

Sur gx10-1, la mise à jour npm du binaire système a échoué. OpenCode 1.19.4
est installé dans l'espace utilisateur ; la consigne propre à cet hôte
demande `PATH=/home/michael/.local/bin:$PATH` avant le runner ou la file.
Le binaire système 1.15.10 reste intact. Les deux essais ne suffisent pas à
attribuer définitivement l'événement absent à cette seule différence de version.

## Utilisation et limites

Voir [AGENT_EXECUTION.md](pack/AGENT_EXECUTION.md) pour le contrat de mission,
les commandes et les preuves à relire. Les quatre modèles autorisés restent
DeepSeek, GLM, MiniMax et Beam avec leurs identifiants exacts. Des missions
réelles séparées travaillent sur le jeu et le diagnostic Neo ; leurs résultats
ne sont pas une qualification de ce paquet ni une validation matérielle.

Ces tests couvrent un environnement Linux et une tâche Python bornée, pas
toutes les chaînes de compilation. Prévalider les commandes exactes d'une
mission dans la boîte : les liens vers `/etc/alternatives` et les compilateurs
installés uniquement sous `/tmp` ne sont pas disponibles implicitement.

Les nouvelles sessions découvrent les consignes globales. Une session déjà
ouverte doit les relire ; aucune injection dans ces sessions n'est revendiquée.
Les paramètres Codex et les références FPGA ne sont pas modifiés. Les caches
de dépendances copiés par erreur avec la première preuve ARM sont inventoriés
puis retirés ; événements, audits, sources, base OpenCode et résultats restent
conservés. Aucun secret fournisseur n'est inclus dans le paquet publié.
