# Publication du workflow global — 28 octobre 2026

Objectif : installer les mêmes outils et consignes sur le PC local et gx10-1,
préserver les données et vérifier l'idempotence, sans changement de configuration
modèle ni de permissions Codex.

Root a réalisé les installations réelles. Une vérification indépendante a
ensuite lu les fichiers et exécuté le contrôle `--prepare-only` installé sur
chaque hôte. Aucun outil de modèle ni accès carte n'est déclenché par ce contrôle.

- Manifeste : `fc664faf94a39ea2e2b55a0ae2ddf0af9bab1f0b715ae2c2355e88146fc294b7`.
- Douze fichiers explicitement installables, plus le manifeste.
- AGENTS.md : `6684c4f408f2401ecdec42317d7a80012d12c8e42eb028168d4e271c0582d1ae`.
- Les deux copies de chaque fichier correspondent au manifeste ; aucun fichier
  supplémentaire dans les deux dossiers installés lors de la vérification.
- AGENTS.override.md absent sur les deux hôtes ; `changed=false` pour les deux
  contrôles d'installation. L'atomicité annoncée reste **par fichier**, pas une
  transaction globale.

La publication a été précédée de 65 tests locaux du paquet : 15 runner,
12 file, 18 registre/statistiques, 12 installation et 8 contrôle de taille.
Cinq tests proposés par DeepSeek, adaptés à l'interface finale, passent aussi.
La copie temporaire complète a passé les contrôles CLI sans fournisseur.
Résultats exacts et journaux : `../release_01/result.json`. Tous les fichiers
Python distribués restent sous 1 000 lignes physiques.

Le registre n'attribue aucune note par défaut. Les dispositions externes de
ce lot doivent être lues avec la rectification d'attribution de consigne dans
`../metrics_checks_01/REVIEW_ATTRIBUTION_CORRECTION.md`.

Nettoyage autorisé : l'archive root `/tmp/codex-model-workflow-fc664faf20261028.tar`
a été vérifiée puis supprimée localement et sur gx10-1. Sur gx10-1, les treize
fichiers exacts du répertoire temporaire du même nom ont été vérifiés puis
supprimés, ainsi que leur répertoire. Aucun autre répertoire ni donnée globale
n'a été supprimé. Les rapports projet sont conservés comme preuves.

Preuves de publication : `local.json`, `gx10-1.json`, `result.json` et le
vérificateur `verify_publication.py`. Les sessions Codex déjà ouvertes doivent
relire les nouvelles consignes ; leur injection automatique n'est pas revendiquée.
