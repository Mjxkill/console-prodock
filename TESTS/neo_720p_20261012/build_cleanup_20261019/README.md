# Nettoyage des builds Gowin — 19 octobre 2026

Nettoyage demandé par Michael, limité aux sorties anciennes de `tang/impl`.

- **64.06 Go libérés** (59.67 Gio alloués).
- **881 fichiers supprimés dans 257 builds terminés**.
- 257 jeux de caches privés du routeur (`.pr`, `.p`, `.db`) retirés.
- 32 anciens bitstreams sans référence identifiée retirés, avec leurs formats binaires associés ; sept anciens modèles de simulation et leurs SDF également retirés.
- Les répertoires gardent leurs sources figées, commandes, netlists de synthèse et rapports. Ils constituent des archives de résultats ; ceux dont les caches ont été retirés ne peuvent plus servir directement au routage incrémental sans recompilation.

## Conservation

Les références Pro Dock G22r0, C37, C28 et R31, les dépendances des scripts, les générateurs DDR, les builds en cours ou récents et l'ensemble des expériences Neo à partir de N38 sont conservés. Les autres résultats historiques cités dans la documentation ou les preuves gardent leurs bitstreams, netlists après routage et SDF.

Les essais en cours N50r4/N52r1, leurs parents de synthèse, N50r2 chargé sur la carte, N47r0 et N43r0 restent intacts. Aucun autre projet, fichier suivi par Git, dossier Linux, processus Gowin ou contenu de carte n'a été modifié par ce nettoyage.

## Vérification

- 49 empreintes de fichiers protégés vérifiées, aucun écart.
- 23413 sources figées des builds concernés vérifiées contre leurs manifestes, aucun écart.
- Diff des fichiers suivis par Git inchangé.
- Toutes les suppressions prévues ont été réalisées.

Le détail des décisions et des chemins est dans [plan.json](plan.json), le journal des suppressions dans [removed.jsonl](removed.jsonl), et les contrôles dans [verification.json](verification.json). Le script `cleanup.py` est une trace de cette opération ponctuelle ; ce n'est pas une politique de nettoyage automatique.
