# Contre-revue du writer flash — 29 octobre 2026

Aucun accès matériel. Les faits JEDEC/capacité fournis par la racine ne sont pas
une preuve de boot SRAM ni de sauvegardes déjà terminées.

## Défaut de cohérence reproduit, corrigé dans R2

`supervisor_image_race.py` injecte une modification de fin de secteur entre le
contrôle natif et la capture du SHA dans le plan R1. R1 soumettait l'image
incohérente au runner simulé, puis refusait la relecture : ce n'était pas un
faux PASS final, mais le refus arrivait après une écriture qui aurait dû être
empêchée. La preuve initiale et sa reproduction sont conservées.

`../corrected_r2/image_contract.py` recalcule les rapports entre les octets
réels du payload, du FS accepté, de l'image, des deux sauvegardes et du SHA
attendu de toute la flash. L'appel est commun à la préparation et à l'exécution
avant le runner de programmation. Les 43 tests incluent les mutations et le
vrai schéma produit par run_session avec frontières matérielles simulées.
Voir DELIVERY_r2.json et reviews/corrected_r2_tests.json. R1 est inchangée.

## Travail GLM indépendant : incomplet, pas qualifié PASS

GLM5.3Flash/OpenCode a atteint sa limite900s :50requêtes,58appels d'outils,
49étapes. Le statut FAILED, les sorties et métriques brutes sont conservés
sous glm_execution_r3. Il a écrit review_schemas.py (879lignes), mais a laissé
review_tail.py/review_tests.py/REPORT.md/findings.json inachevés.

Le superviseur a exécuté le fichier brut : échec d'import par mauvais chemin
PROJECT. Une copie séparée ne corrigeant que ce chemin obtient2tests exécutés
et3erreurs de setup : les fakes du processus ne finissent pas correctement.
Les fichiers gelés du modèle ne sont pas retouchés. Ces échecs ne constituent
pas des défauts du writer. Preuves : supervisor_glm_check/result.json.
Autres limites visibles du code inachevé : le marqueur de19octets remplace
une tranche de20octets de la sauvegarde et la tronque ; plusieurs champs de
plan attendus ne correspondent pas au vrai schéma. Aucun résultat de ces
fixtures n'est utilisé pour autoriser une écriture.

## Hypothèse GLM vérifiée séparément

Le vrai producteur, piloté par nos frontières simulées, produit returncode0.
Si ce champ est changé en1 et que les SHA du résultat ET de l'attestation root
sont volontairement réécrits, proofs.validate_sram_result accepte la
contradiction avec passed/configuration_completed=true. La preuve séparée
supervisor_glm_check/contradictory_sram.py est reproductible et conserve la
limite : aucun chemin naturel du producteur donnant cette contradiction n'a
été montré. C'est une vérification de cohérence absente sur une preuve
re-signée, pas une panne de carte ni une violation des SHA non modifiés.
La racine en a été avertie ; R2 gelée n'a pas été modifiée pour ce point.

## Oracle de conservation indépendant du modèle

supervisor_tail_oracle.py teste le vrai offline.py gelé avec des payloads
1,65535,65536,65537octets, puis une géométrie16MiB. Il utilise une substitution
de tranche d'une image complète pour construire son attendu indépendant.
Les cinq cas passent. Une corruption du début, de la dernière donnée, de la
première donnée conservée ou du dernier octet, ainsi qu'une troncature de la
relecture, sont refusées. Preuves : supervisor_glm_check/final_results.json.

Ces essais valident des relations de fichiers, des schémas et des refus
logiciels. Ils ne qualifient ni le programmateur réel, ni une écriture flash,
ni le boot à froid. La racine demeure seule propriétaire des essais carte.
