# Revue indépendante MC1 r2 — 27 octobre 2026

**Verdict : FAIL pour lancement matériel du bundle r2.** Le nettoyage peut être interrompu par un signal pendant le repli d'une erreur. L'acceptation de performance ignore aussi les phases d'entrée/repos et n'impose aucune borne de dérive aux témoins A. Un nouveau bundle figé et ses contre-tests sont nécessaires avant essai.

Revue sans accès carte, SSH, port série ou JTAG. GM1 n'a pas été interrogé ni interrompu. Aucun fichier du bundle n'a été modifié. Instructions lues : `AGENTS.md`, `ARCHI/COMPATIBILITE_CARTES.md`, `tang/boards/ownership.json`. Les pilotes communs ne sont pas reclassés en Pro Dock du fait de leur nom. Cette revue n'est ni une campagne dual-board, ni une qualification FPGA/Linux/matérielle.

## Paquet et preuves relus

- Bundle : `games/luma3d/tests/hardware/mesh_cache_20261027_mc1_prepared_r2/`.
- Manifeste SHA-256 : `cc374648e1fd7c999bd1a1b244f5fc6c9a19d1c8de94a50f8757f75ba1a59400`.
- Contrôleur effectif : `prodock_mesh_cache.py`, SHA-256 `751efe35b744e0f61a42bf241f8b4111ea10efe5e12f03d6167e1e664f6e7bf4`.
- Les 102 fichiers du manifeste correspondent à leurs tailles, SHA-256 et CRC32. Les deux logs de `mesh_cache_20261027_mc1_local_review_r2/` correspondent aussi aux SHA du résultat : préflight PASS et sept tests PASS. Ces tests existants n'ont pas été rejoués.
- Relus également : reconstruction locale des deux deltas, test des rectangles du helper, validation native des huit fenêtres, seize fixtures natives, seize fixtures RV32/QEMU et quatre fenêtres RV32, unités cache, équivalence de 80 images sélectionnées et résultat GM1 antérieur. Ces preuves restent locales lorsqu'elles sont marquées `hardware=false`.

## Échecs bloquants

### F1 — signal pendant nettoyage d'une erreur

`prodock_mesh_cache.py:96-97` garde les handlers qui lèvent `KeyboardInterrupt` actifs pendant tout le nettoyage. À `154-164`, une erreur initiale entraîne `guard.recover`, mais un SIGINT/SIGTERM/SIGHUP reçu dans ce repli est capturé par le `except BaseException` interne : seul `cleanup_error` est rempli. L'erreur initiale est ensuite relancée et les contextes série/verrou se ferment. Il n'y a plus de tentative de terminer le repli, même si la liaison et le PID connu restent exploitables. Le problème concerne un seul signal reçu pendant le nettoyage d'une erreur, pas uniquement un arrêt forcé SIGKILL.

Un contre-exemple supplémentaire a été exécuté hors carte, en mémoire, à partir du harnais mocké de `test_trial.py` : échec `TimeoutError` au lancement de `mc1_window0`, puis `KeyboardInterrupt('SIGTERM during recovery')` dans le repli. La série, le transport, les verrous et les gardes matériels étaient remplacés par les mocks existants. Résultat :

```text
passed=False
error=TimeoutError('initial window failure')
cleanup_error=KeyboardInterrupt('SIGTERM during recovery')
restored_gm1 absent
```

Le harnais conserve alors son producteur « probe » ; ce résultat démontre le défaut de contrôle, sans prétendre reproduire une panne matérielle. Aucun fichier du test figé n'a été modifié.

Correction attendue : différer ou ignorer les trois signaux de terminaison pendant une section de repli protégée, y compris l'arrêt ciblé du producteur courant, le lancement/recontrôle de GM1, sa progression, la publication du PID et la relecture finale de sauvegarde/identité. Préserver la cause initiale, la journalisation et le refus d'un deuxième producteur en cas d'identité indéterminée.

### F2 — acceptation partielle des performances

`compare()` à `prodock_mesh_cache.py:31-37` compare uniquement `phases[2]` (« moving »). La durée de l'entrée, celle du repos, leurs p99/maxima et la dérive des témoins ne peuvent pas faire échouer `performance_accepted`. La dérive A finale/initiale est calculée, mais n'est confrontée à aucun seuil. Cela ne réalise pas entièrement le contrôle des régressions de chaque phase annoncé dans `PLAN_MC1.md`.

Trois contre-exemples purs, avec extraction en mémoire de la fonction exacte et lignes issues des résultats locaux, ont confirmé :

```text
entry_100x        accepted=True   baseline_drift=1.0
rest_100x         accepted=True   baseline_drift=1.0
witness_drift_2x  accepted=True   baseline_drift=2.0
```

Pour le troisième cas, le témoin A final et son B adjacent ont chacun une durée doublée ; les deux rapports A/B restent favorables. Ces contre-exemples portent sur la décision, pas sur une nouvelle mesure de vitesse. Les données brutes des phases sont bien conservées et aucune promotion automatique n'est prévue, mais le booléen ne doit pas être interprété comme une non-régression générale.

Correction attendue : calculer et conserver les gardes moyenne/p99/max pour entrée, repos et mouvement, pour chacune des paires AB et BA ; fixer avant essai une limite explicite de dérive symétrique des témoins par phase. Une limite proposée de 3 % doit être déclarée dans le manifeste et appliquée aux deux sens, par exemple `max(A_final/A_initial, A_initial/A_final) <= 1.03`. L'entrée de deux images reste un échantillon court, susceptible de refus bruités ; cela ne justifie pas d'assouplir le seuil après mesure.

## Contrôles satisfaisants et limites

| Point | Constat de revue |
|---|---|
| Carte et verrou | PASS statique : port exact `usb-Electrosens_MegaPro_Console_11252024-if00`, verrou non bloquant `/tmp/prodock-diagnostic.lock` tenu pendant toute l'opération, ouverture série exclusive. La commande préparée vise uniquement `michael@ax15`. Aucun chemin d'accès Neo dans le contrôleur exécuté. |
| FPGA/noyau | Continuité G22r0 explicitement déclarée, noyau attendu `6.12.112-prodock-luma3d-g3d1-r1`, contrôle ABI/caps puis signature G3D1 par les probes. Le SHA de la référence protégée est `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f` ; MC1 ne relit pas la SRAM FPGA. Ce n'est pas une nouvelle identification cryptographique matérielle. Toute rupture de continuité invalide ce présupposé. |
| ELF et ancre GM1 | PASS statique : SHA GM1 `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`, PID 2925/startticks 26240721, argv complet octal exactement `/tmp/luma3d-gm1 --showcase`. Fichier GM1 et `/proc/2925/exe` contrôlés sur carte par taille/CRC32 avant arrêt ; SHA des artefacts vérifiés localement. L'ancre est une dernière identité connue, à revalider sous verrou. |
| Probes et candidat | PASS : A est la probe dérivée GM1 SHA `6585cf9d12fda6a8e80ba305b4b8e28f59717759f57c616e16259b3678410a6b`, B la probe cache SHA `054220ca930cda39e452d98ee2ceb1b85f90760edfc98644805380a041494d1b`. Le jeu candidat normal SHA `8d2b54d7b4f3b2fa27628c019860f36c3299e0b574b733bc5684c29710df942a` n'est pas le binaire chronométré et n'est pas transféré/promu. Les deltas ont été reconstruits et vérifiés lors du gel. |
| Arrêt ciblé | PASS pour l'ancre GM1 : identité relue juste avant TERM, PID fixe et startticks revérifiés dans la commande shell, disparition ou zombie confirmé avant nouveau producteur. Pour les probes, le PID propre à chaque lancement est utilisé et startticks est vérifié immédiatement avant TERM puis lors de la confirmation ; il est acquis à l'arrêt, pas enregistré au lancement. La garantie contre un remplacement antérieur par un processus de même nom dépend donc de l'exclusivité de l'essai. |
| Délais | Fenêtres bornées à 600 s et fixtures à 240 s ; `wait_exit` ne fait que lire l'UART et prend en compte le marqueur déjà reçu au lancement. Les commandes et ACK possèdent aussi des délais. Ce n'est pas un watchdog autonome sur carte : disparition du contrôleur ou liaison irrécupérable ne garantit pas le retour GM1. Les écritures/flush série n'ont pas de `write_timeout` explicite. |
| Sauvegarde | PASS : lecture structurée V4 et SHA `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6` avant/après. Aucun `--save` admis pour GM1 ni les probes ; aucun remplacement de `/tmp/op2-live.save`. Aucun FPGA, noyau, SD ou flash écrit par ce contrôleur. |
| Repli nominal | PASS hors F1 : même binaire GM1, `--showcase`, stdin `/dev/null`, un seul lancement de reprise, identité complète avant/après progression puis après publication et sauvegarde. Une tentative dont la réponse est perdue est réadoptée uniquement par son identité ; aucun second lancement aveugle. Un PID absent/inconnu/remplacé échoue fermé : la restauration reste alors non acquise. |
| Oracles | PASS statique : huit fixtures candidat hors fenêtres, ROI RGB565 publié 400×240 et chaque source UI active, compteurs de la dernière image, exactitude octet par octet via helper, restart/BACK inclus. Ni trous VRAM non initialisés, ni capture LCD composée, ni preuve matérielle des 32 Mio complets revendiqués. |
| Comparaison | Charge pertinente : maison puis exploration chacune A/B/B/A, mêmes états/codecs/commandes/volumes attendus, deux images d'entrée, douze de repos, 360 mobiles et un pas logique 60 Hz par image. L'exploration sans publication dynamique sert de témoin. Les deux paires sont conservées séparément. Ce n'est pas le débit d'une visite temps réel complète. F2 empêche l'acceptation globale annoncée. |
| Mesures | Coûts de publication inclus dans préparation ; feed/wait/cache du pilote inclus dans SUBMIT, sans somme double. Histogrammes par tranches de 4 ms, p95/p99 supérieurs et huit pires images avec indices. Zéro percentile avec overflow est rejeté par la garde de performance mobile et doit rester « hors histogramme ». Le champ `cycles_mod32` explicite le compteur modulo. |

Les scripts historiques du bundle sont des dépendances de fonctions ; leurs `main()` et leurs anciennes routines d'arrêt ne sont pas exécutés par MC1. Le contrôle ABI est effectué après arrêt de GM1, contrairement à l'ordre plus précoce annoncé dans le plan ; l'échec passe alors par le repli, qui doit donc impérativement résister à F1.

## Validation minimale du remplaçant r3

1. Conserver r2 et ses preuves FAIL ; nouveau manifeste et dossier local distincts, sources corrigées liées par SHA aux tests.
2. Injecter chacun des SIGINT/SIGTERM/SIGHUP pendant le cleanup d'une erreur et pendant le repli normal, notamment avant/après TERM, lancement GM1, progression, publication et lecture de sauvegarde. Vérifier un seul lancement, absence de deuxième producteur, identité finale exacte, sauvegarde inchangée et conservation de l'erreur initiale. Tester aussi un signal répété pendant cleanup.
3. Conserver les refus PID/startticks remplacés, PID non publié et liaison réellement perdue : ne pas prétendre restaurer quand la preuve manque et ne pas relancer à l'aveugle.
4. Faire échouer séparément les contre-exemples entrée×100, repos×100, p99 hors histogramme, maximum régressé et dérive A ×2/÷2. Vérifier les trois phases des deux paires et le cas conforme ; joindre les limites au manifeste.
5. Relire le nouveau plan et les résultats locaux avant accès carte. Aucun résultat local ni cette revue n'autorise à revendiquer une qualification Neo, une promotion du candidat, ou la disparition des limites historiques de timing/USB de G22r0.
