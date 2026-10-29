# Bornes d’exécution OpenCode — candidat hors installation

Seulement deux fichiers de runtime changent : `agent_runner.py` et
`agent_provider.py`. Le patch est `bounds.patch`, contre les SHA de
`inputs.json`. Aucun fichier global ni processus déjà lancé n’a été modifié.

| Limite | Avant | Proposé |
|---|---:|---:|
| Étapes par invocation, défaut | 16 | 64 |
| Étapes par invocation, maximum accepté | 32 | 256 |
| Requêtes HTTP, défaut CLI et ProviderProxy | 48 | 128 |
| Requêtes HTTP, maximum CLI et ProviderProxy | 96 | 512 |
| Durée défaut / maximum CLI | 900 / 3600 s | inchangé |
| Plafond de sortie défaut / maximum | 65536 / 131072 tokens | inchangé |

64 étapes par défaut avec 128 tentatives HTTP évitent qu’un plafond HTTP
inférieur interrompe automatiquement une session nominale de 64 étapes.
Les appels de reprise restent comptabilisés ; 128 n’est pas une garantie
de finir toute mission. Aucun compteur n’est gonflé et aucun nombre minimal
de requêtes n’est exigé. L’agent doit s’arrêter une fois le travail terminé.
L’isolation MCP, l’absence de réseau dans les outils, les tests après édition,
la révision humaine et les limites de durée restent identiques. Les tâches
déjà en cours conservent leur CLI/configuration et leur module chargé.

Le contre-avis ROM Beam illustre la borne trop courte : le second lot a livré
16 tests valides mais a atteint 32 étapes avant son rapport et son test final.
Ce constat ne transforme pas son résultat FAILED en succès. Le premier lot
était tronqué sur la sortie de 16000 tokens : c’est une limite distincte,
qui n’est pas corrigée en augmentant seulement le nombre d’étapes.

## Validation

8 tests ciblés PASS : défauts, bornes inclusives/exclusives, types refusés,
transmission 64/256 à OpenCode et 128/512 au proxy, conservation des permissions
d’isolation. Le test HTTP réel local réalise 512 requêtes sur un fournisseur
simulé puis vérifie le rejet 429 de la 513e, sans appel amont supplémentaire.
28 tests existants runtime/événements/queue PASS avec les modules candidats.
Aucune clé réelle, appel modèle, carte ou connexion fournisseur n’est utilisé.
La première tentative dans le bac à sable a été bloquée à la création du
socket ; `sandbox_failure_01.json` est conservé. Les mêmes sources ont ensuite
passé avec autorisation explicite d’exécuter ce test localhost.

L’ensemble contient une copie figée des fichiers installables pour importer
les dépendances exactes. Ce n’est pas un nouveau paquet à publier directement :
root relit les deux changements, adapte les docs puis reconstruit son manifeste
et publie local/gx10-1. Les tests ne démontrent pas une future mission réelle
à 64 étapes ; ils vérifient les bornes et leur transmission sans accès externe.
