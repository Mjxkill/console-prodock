# Collecteur UTW1 préparé, sans essai matériel

Ce dossier prépare le diagnostic de N56r22r1 et son retour à **R19 exact**.
Il ne qualifie ni le FPGA ni la DDR. Aucun outil JTAG, programmateur ou accès
à une carte n'a été lancé pour développer ou tester ce collecteur.

Le bitstream du candidat et son audit de timing ne sont pas encore connus.
La revue préparée garde donc `hardware_ready=false`, `candidate=null` et
`timing_audit=null`. `--run` est refusé avant le verrou, l'identification USB
et toute création d'IO matérielle. Root est le seul propriétaire du futur essai.

## Séquence bornée et données conservées

Le contrôleur reprend les gardes et l'IO de
`../../neo_common_cause_20261027/utna_activity_prepared_01`, dont le chemin
et les empreintes sont épinglés dans `collector.py`. Il vérifie CPU stationné en
M-mode, ROM d'attente, GPU 720p sur mire interne et compteurs NCP/UTNA frais.
Cette garde utilise `halt` et des lectures : elle ne doit pas être employée
sur un Linux actif. Elle ne constitue pas une attestation du bitstream chargé.

Après programmation SRAM du candidat exact, le Tcl vérifie l'identité UTW1,
l'ABI et les registres de témoin initialement nuls, puis exécute uniquement :

| Étape | Commande écrite à `0xe900200c` | Séquence attendue |
|---|---:|---:|
| ARM | 1 | 1 |
| DISARM | 6 | 2 |
| STOPPED | 2 | 3 |
| STABLE | 2 | 4 |

Chaque étape contrôle l'état avant écriture, attend au plus 100 sondages ou
2 secondes pour l'acquittement, puis collecte les contrôles avant/après et
**deux images entières** : banque `+40..BC` (32 mots) et témoin `+C0..FC`
(16 mots). Cela fait 102 lignes JSONL canoniques par étape, 408 au total.
Les pauses entre étapes sont de 200, 100 et 100 ms. Le processus OpenOCD est
borné à 30 secondes, chaque programmation SRAM à 120 secondes, par l'IO
existante ; la durée réelle de collecte à 100 kHz reste à
mesurer. Un dépassement est un échec avec restauration, pas une capture valide.

Le décodeur refuse les acquisitions partielles, les clés JSON dupliquées,
les valeurs non-u32, les adresses/phases inattendues et les lignes en trop.
Il compare les deux images, les contrôles avant/après, les aliases CC/D4,
les tags, les compteurs, EC et F0. Le collecteur ajoute les relations
ARM/DISARM et la stabilité du compteur arrêté. Les journaux bruts restent
conservés même si le décodage échoue. Une version zéro cohérente conserve
ses données et son interprétation conditionnelle, mais reste **FAIL**.

## Liaison à la netlist normalisée

La façade figée `../offline_binding_r22r1_01/offline_capture.py` accepte
la vraie netlist normalisée
`0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191`.
Le décodeur d'origine pour `fa018540…` reste inchangé. La copie de décodage
ne diffère que par la constante d'identité, réversible octet pour octet.
L'adaptateur vérifie les SHA de la preuve de sérialisation, de l'assemblage
et des tests. Le paquet strict contient le SHA normalisé ; aucune donnée
de capture n'est réécrite vers l'ancienne identité.

Ces preuves établissent le lien de code/netlist, pas la fidélité physique
des observations après routage. CC et D4 sont deux accès au même registre,
pas deux observations indépendantes. `qualification_status` reste `FAIL`
dans le rapport d'essai même si les contrôles locaux passent.

## Garde du futur lancement

Les SHA de l'adaptateur, du décodeur, de l'ancre R19, des scripts utilisés,
des outils hérités et des résultats de tests sont figés dans la revue.
L'ancre est le résultat restauré du 28 octobre à 00:09:42, avec ses fichiers
vérifiés. Une ancre historique ne prouve pas à elle seule l'état courant.
Root devra vérifier que personne n'a changé de cible ou lancé un système.

Avant d'autoriser un essai, root doit créer une **nouvelle revue**, gardant
ces preuves, avec les champs suivants :

```json
{
  "hardware_ready": true,
  "candidate": {
    "path": "chemin/dans/le/depot/console_neo.fs",
    "bitstream_sha256": "SHA256 exact du fichier terminé",
    "netlist_sha256": "0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191"
  },
  "timing_audit": {
    "path": "chemin/dans/le/depot/audit_root.json",
    "sha256": "SHA256 exact de cet audit",
    "reviewed": true
  }
}
```

L'audit JSON doit contenir `reviewer="root"`, la décision explicite
`decision="diagnostic_trial_allowed"`, `bitstream_sha256` identique au
candidat et `input_netlist_sha256` identique à la netlist normalisée.
Ce contrôle lie une décision de revue aux fichiers ; il ne fabrique pas
un PASS de timing et ne remplace pas l'inspection du rapport de routage.

Après validation locale, le lancement prend `TESTS/neo_board.lock` sans
attente, refuse un autre OpenOCD/programmateur/GAO actif et vérifie les deux
identités USB Neo attendues. L'IO vérifie de nouveau le SHA et l'identité
au moment de chaque programmation. Il n'y a aucune sélection Pro Dock,
écriture flash, CPU resume, accès SD ou écriture DDR/GPU dans ce protocole.

## Restauration et limites

Avant la première tentative de programmation du candidat, le contrôleur
arme son `finally`. Dès lors, succès, échec, mauvais diagnostic ou signal
doivent tenter exactement une restauration du fichier R19 de SHA :

`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`

La garde finale vérifie CPU stationné, mire et UTNA frais. Une erreur de
restauration reste explicitement une erreur ; elle n'est jamais transformée
en succès. SIGINT, SIGTERM et SIGHUP sont enregistrés et différés pendant
le nettoyage. Un échec d'écriture des journaux ne doit pas empêcher la
programmation de retour. En revanche SIGKILL, panne électrique, disparition
physique de la cible et défaillance du programmateur ne peuvent pas être
corrigés par ce `finally` : aucune promesse de restauration absolue.

L'état initial du bitstream est déclaré, pas lu physiquement :
`initial_reference_declared_sha256` est séparé de `last_programmed_sha256`,
qui commence à `null`. Seule une programmation réalisée par l'IO remplit
ce dernier champ.

## Validation hors carte

`test_collector.py` exécute le **Tcl exact** sous Tclsh avec des registres
simulés, et le **contrôleur exact** avec IO simulées. Il teste les captures,
les erreurs de chaque étape, les preuves préalables et la restauration.
Les signaux sont de vrais `os.kill()` dans des processus isolés ; la cible
est toujours simulée. Les résultats ne sont ni des mesures de temps JTAG,
ni des preuves de stabilité FPGA. Le détail et les empreintes sont dans
`tests_result.json` et le dossier de tests final indiqué par `DELIVERY.json`.

Les premières tentatives sont conservées : `tests_r1` a révélé une erreur
du banc de signaux (point de trace placé dans une fonction imbriquée),
corrigée dans le banc ; `tests_r2` testait encore le SHA de netlist original.
Les tests suivants utilisent la façade normalisée. Aucune réduction de la
suite n'a été faite pour produire un PASS.

La contre-revue Beam utilise seulement un paquet de texte, sans outils.
Le premier appel a échoué sur la résolution DNS dans le bac à sable ;
la relance séparée conserve cet échec et son résultat. Le relevé final
indique les suggestions retenues ou rejetées.

Seule la commande suivante effectue le préflight local, sans matériel :

```sh
python3 TESTS/neo_common_cause_20261028/utw1_collector_prepared_01/collector.py \
  --review TESTS/neo_common_cause_20261028/utw1_collector_prepared_01/prepared_review.json \
  --check-only
```
