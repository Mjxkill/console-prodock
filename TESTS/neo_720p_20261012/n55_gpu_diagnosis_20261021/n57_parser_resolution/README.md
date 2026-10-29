# Résolution réelle des alias par le parseur Gowin

Le premier lancement N57, manifeste
`76160fdf0a4dd030d79c4b9abb1b1b56bc987fe85a017f2daca150c9196035fd`,
s'est arrêté avec code 1 à la lecture du CST, avant tout placement.
Le journal contient treize erreurs CT1000 de contraintes redéfinies.

Les douze noms internes `u_accel/gpu_debug_state_44` à `_55` sont reconnus
par le parseur comme les mêmes nets que `gpu_debug_state[44]` à `[55]`.
Cela réfute l'hypothèse d'une simple absence de reconnaissance des noms au
niveau supérieur. Leur LOCAL_CLOCK n'empêchait pourtant pas les routes LW
observées sur R3/R5 : le contrôle physique après routage reste nécessaire.

Gowin normalise également la contrainte sur la sortie d'inverseur
`u_accel/v1_tx_addr_27_12` sur le même contrôle canonique `v1_pending`.
Il ne permet donc pas les deux lignes simultanément. Ce constat porte sur
la gestion des contraintes, pas sur une équivalence logique entre un signal
et son inverse.

`result.json` conserve les treize numéros de ligne, noms canoniques, contraintes
en cause et SHA. Le dossier du lancement rejeté reste intact. Aucun retrait
de contrainte, relancement ou accès matériel n'a été fait pour produire ce
rapport.

`proposed_unique_controls.cst` propose les huit lignes sans doublon : les neuf
fonctions initialement étudiées restent couvertes par la preuve sémantique,
mais pending et son inverse partagent une contrainte canonique. Les douze
contraintes top des resets doivent être conservées. Cette proposition exige
une nouvelle revue et un nouveau manifeste avant routage ; l'audit final doit
encore contrôler les deux polarités et les douze resets physiquement.
