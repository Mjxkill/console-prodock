# Revue indépendante MC1 r3 — 27 octobre 2026

**Verdict : PASS pour la revue du contrôleur préparé r3, avant essai matériel coordonné.** Les défauts F1 et F2 du [rapport r2](game_controller_review.md) sont corrigés. Le verdict r2 reste **FAIL** ; aucun résultat matériel MC1, gain mesuré ni promotion du candidat n'est établi par cette revue.

Relecture sans accès série, SSH, JTAG ou carte et sans modification des bundles. GM1 n'a pas été interrogé ni interrompu. Les instructions et l'inventaire lus lors de r2 restent applicables ; aucune source commune, FPGA ou référence protégée n'a changé pour cette correction.

## Identité vérifiée

- Bundle : `games/luma3d/tests/hardware/mesh_cache_20261027_mc1_prepared_r3/`.
- Manifeste SHA-256 : `122e5573e1f1d4d86642692213c34f97f25086c69cf417c2a2aa4b6efb47671c`.
- Contrôleur SHA-256 : `603774e4aa5adae1bb978ee659230b49479f5c09ff0d743b30482e56b788e76a`.
- Les tailles, SHA-256 et CRC32 des 102 fichiers sont corrects. La comparaison octet par octet avec r2 confirme seulement trois changements parmi ces fichiers : `PLAN_MC1.md`, `prodock_mesh_cache.py`, `test_trial.py`. Les binaires, helpers, oracles, deltas, gardes PID et preuves locales de rendu sont inchangés.
- Résultat local relu : `games/luma3d/tests/hardware/mesh_cache_20261027_mc1_local_review_r3/result.json`. Les SHA des deux logs correspondent : préflight PASS et neuf tests PASS. La suite existante n'a pas été répétée.
- Le manifeste r2 est toujours `cc374648e1fd7c999bd1a1b244f5fc6c9a19d1c8de94a50f8757f75ba1a59400`.

## F1 corrigé — repli protégé

`CleanupSignals` installe explicitement les handlers SIGINT, SIGTERM et SIGHUP. Avant le nettoyage, un signal lève encore `KeyboardInterrupt` pour déclencher le chemin d'erreur. `begin()` est la première opération du repli nominal et du bloc de traitement d'erreur : les mêmes handlers consignent ensuite les signaux et retournent sans exception. La protection reste active pendant l'arrêt du producteur courant, le repli GM1, sa progression, la publication du PID, les vérifications tardives de sauvegarde/identité et l'archivage final.

Les tests relus couvrent la réception réelle des trois signaux, répétés, dans des sous-processus locaux ; le harnais du contrôleur injecte également chacun d'eux avant/après son repli mocké après erreur, pendant le repli nominal et pendant la lecture finale de sauvegarde. Le résultat exige GM1 restauré, aucun `cleanup_error` et la conservation des signaux différés. Les tests antérieurs d'idempotence, d'identité finale et de PID non publié sont conservés. Ces tests n'exécutent pas de commandes carte ; les sous-processus ne testent pas une rupture physique du transport.

`CleanupLogPath` empêche qu'une erreur locale d'écriture de journal interrompe les commandes de restauration. Il conserve l'erreur et l'empreinte des données manquantes ; le verdict impose alors `passed=false` et `evidence_complete=false`. Les erreurs du protocole restent fatales : le test vérifie qu'une commande non nulle lève toujours `RuntimeError` même si l'écriture du journal échoue. L'écriture du résultat final intervient après le repli et son échec est reporté vers stdout si possible.

## F2 corrigé — décision par phase et dérive

`compare()` évalue maintenant entrée, repos et mouvement pour chacune des paires AB et BA, dans chaque scène. Chaque phase conserve ses rapports, p99, maxima et gardes détaillées. La dérive symétrique des témoins est fixée avant essai à `max(A_final/A_initial, A_initial/A_final) <= 1.03`. L'acceptation de la scène exige l'acceptation de toutes les phases ; l'acceptation globale exige les deux scènes. Le préflight lie cette politique au manifeste.

Outre les tests r3 déjà archivés, un contrôle indépendant purement local a extrait en mémoire la fonction exacte du bundle et utilisé les structures des résultats locaux. Le cas conforme passe. **72 contre-exemples sont refusés**, couvrant les deux scènes, les trois phases, les deux B et les régressions suivantes : durée ×100, p99 nul/hors histogramme, p99 excessif, maximum excessif ; dérives des témoins ×2, ÷2, ×1,04 et ×0,96 avec B adjacent modifié pour maintenir un rapport A/B favorable. Aucune mesure matérielle ni modification de fichier n'a été effectuée par ce contrôle.

Le plan expose maintenant la courte durée de l'entrée à deux images, conserve ses refus éventuels et interdit les répétitions opportunistes. Ces gardes restent une comparaison diagnostique ; elles ne qualifient pas une visite temps réel ni 30/60 FPS.

## Portée opérationnelle à conserver lors de l'essai

Les garanties positives de la revue r2 restent valables : carte Pro Dock par CDC série 11252024, verrou exclusif et port exclusif sur ax15, ancre GM1 exacte PID 2925/startticks 26240721 à revalider, aucun accès Neo, arrêt ciblé, fichiers `/tmp` nouveaux, sauvegarde V4 inchangée, oracles exacts hors fenêtres, lecture UART seule pendant les mesures, repli GM1 idempotent et aucune promotion automatique. Les références FPGA/Linux protégées ne sont pas remplacées.

Les limites déclarées restent effectives : G22r0 identifié par continuité et signature G3D1, pas par relecture SHA de la SRAM ; ELF contrôlés localement par SHA et sur carte par taille/CRC32 ; startticks des probes acquis à l'arrêt ; absence de watchdog carte autonome et de `write_timeout` série. Si une identité devient indéterminée ou le transport réellement irrécupérable, le contrôleur doit conserver son échec fermé et ne pas annoncer de restauration acquise.

L'exploitation doit lire le résultat final : `passed`, `evidence_complete`, `performance_accepted`, `restored_gm1`, l'identité finale et le SHA de sauvegarde ont des significations distinctes. Un essai fonctionnel avec retour GM1 peut avoir `passed=true` et `performance_accepted=false`. Une erreur d'archivage après le repli peut laisser un code de sortie du contrôleur nul mais un verdict JSON `passed=false`, voire seulement le résultat sur stdout ; un code shell nul seul n'est donc pas une preuve de succès.

La prochaine étape justifiée est l'essai coordonné du **bundle r3 exact**, après revalidation sous verrou de l'ancre actuelle. Le compte rendu matériel devra conserver séparément correction, performance et restauration GM1. Tout changement ultérieur du bundle ou de son ancre invalide cette identité de revue.
