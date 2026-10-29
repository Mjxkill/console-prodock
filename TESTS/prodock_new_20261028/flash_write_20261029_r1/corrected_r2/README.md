# Écriture persistante R2 — candidat préparé, aucune carte touchée

Cible exclusive : Pro Dock FTDI `0403:6010 / 2025071717`, FPGA `0001081b`,
carte `tangmega138k`, hôte `michael-AX15`. La première Pro Dock `2023112818`,
son UART7.3 et le J-Link sont exclus. Root seul transfère et exécute.

**Root rapporte une détection NEW réussie : ef4018, Winbond W25Q128,
256secteurs,16MiB. Cette revue ne réinterroge pas la carte. Aucun succès
SRAM R5, dump complet ou écriture n’est déduit de cette information.** Les tests construisent des preuves
synthétiques dans des répertoires temporaires, avec les vrais parseurs et le
coordinateur de lecture figé. Ils n’ouvrent aucun périphérique.

## Prérequis et séparation des étapes

1. Root doit avoir accepté le boot SRAM du `.fs` exact sur la nouvelle carte.
   Utiliser le `result.json` final du coordinateur `load_sd_candidate.py`,
   avec configuration, lecture des marqueurs de boot et lancement du jeu
   réussis, programmateur terminé et aucun cleanup en échec.
2. Exécuter séparément la détection puis les **deux dumps complets indépendants**
   via le coordinateur `flash_readonly_20261029_r1/prepared_r2`. Garder les
   JSON, commandes, journaux et fichiers complets. Le writer ne refait pas
   ces étapes. JEDEC et capacité doivent provenir de ces preuves, jamais du
   nom de la carte. Leur table de composants doit être relue par root.
3. Root produit une attestation explicite associant le candidat, le résultat
   SRAM et les sauvegardes. Il y confirme l’acceptation, l’autorisation de
   programmer et que la flash n’a pas changé depuis les sauvegardes. Cette
   attestation est une déclaration de root, pas une mesure automatique.
4. Préparer localement l’image et faire relire ses SHA, sa cible et ses preuves.
5. Root exécute une fois l’écriture puis une relecture complète sous un même
   verrou. Un échec ne déclenche aucune reprise ni restauration automatique.
6. Une correspondance complète des octets donne `coldboot_pending` : root doit
   encore tester le boot autonome, le GPU et une vraie coupure/réalimentation.

Chaque accès flash Gowin interrompt la configuration SRAM : c’est vrai aussi
pour la détection et les dumps. Le garde partagé est
`/tmp/prodock-diagnostic.lock`. L’état du FPGA n’est pas déduit du seul argv.
`program_attempted` indique l’entrée dans le runner, pas un nombre mesuré
 d’écritures terminées. `completed_flash_writes` reste inconnu (`null`).

## Fichiers et formats d’entrée

Tous les chemins sont absolus, réguliers, sans symlink ni composante `..`.
Les preuves vivent sous `/home/michael/console-validation-20261001/TESTS` ;
le `.fs` peut vivre ailleurs dans cette même racine. Les sorties doivent être
nouvelles et rester dans `TESTS`.

La requête root JSON doit contenir :

- `version: 1`, `target_serial: "2025071717"`, `physical_idcode: "0001081b"` ;
- `jedec` : six chiffres hexadécimaux minuscules réellement détectés ;
- `capacity` : capacité réelle en octets, nombre entier ;
- cinq objets `{ "path": chemin_absolu, "sha256": empreinte_exacte }` nommés
  `bitstream`, `sram_result`, `detection`, `backups`, `acceptance`.

`detection` désigne `detect.json`, `backups` désigne `dump.json` de la rev2.
Les journaux et les deux fichiers référencés sont relus, reparsés et hachés ;
les champs `passed` seuls ne suffisent pas. Les deux dumps et leurs journaux
ont des chemins/inodes distincts. Les SHA, tailles, géométries, commandes et
comparaisons enregistrés doivent correspondre aux octets observés.

L’attestation root `acceptance` contient :

- `target_serial`, `physical_idcode`, `bitstream_sha256` ;
- `sram_result_sha256` et `dump_result_sha256` des preuves exactes ;
- `sram_boot_accepted`, `permission_to_program`,
  `flash_unchanged_since_backup`, chacun explicitement vrai.

Aucun fichier d’attestation exploitable ni requête réelle n’est généré par
l’agent. Toute modification d’une preuve invalide le plan précédent.

## Commandes destinées à root, pas exécutées ici

Avant de lancer, vérifier le manifeste de livraison et les SHA des fichiers
transférés. Les variables ci-dessous désignent des preuves réelles fournies
par root ; aucune valeur JEDEC ou capacité n’est devinée.

```sh
python3 -B flash_write.py prepare \
  --request "$REQUEST" --request-sha "$REQUEST_SHA" --out "$NEW_PREPARE_DIR"

# Inspection seulement : aucun verrou matériel, programmeur ou fichier créé.
python3 -B flash_write.py program \
  --plan "$PLAN" --plan-sha "$PLAN_SHA" --out "$NEW_RUN_DIR"

# Après revue du plan : une écriture et un dump complet, sans autoretry.
python3 -B flash_write.py program \
  --plan "$PLAN" --plan-sha "$PLAN_SHA" --out "$NEW_RUN_DIR" --run
```

La production n’a aucun paramètre de substitution d’hôte, de série ou de
racine. Les seules injections `root`, `runner`, `guard_factory(root)` sont des
interfaces Python utilisées par les tests. Le runner matériel réutilise le
`process_guard` figé : masquage du signal pendant la prise de possession du
processus, kill/reap borné avant de quitter le verrou. Un processus noyau non
interruptible peut empêcher le reap ; cette situation ne peut pas donner PASS.

La durée par commande vaut 900s par défaut, configurable de1 à1800s. Un signal
ou timeout après tentative rend l’état `inconclusive` ; un refus avant
lancement reste `failed` ou une exception de validation/exit2 sans tentative.
Un retour non nul ou une comparaison incorrecte est en échec. Le journal
partiel et son SHA sont conservés dès qu’un fichier de journal a été ouvert.

## Préservation et vérification

Le vrai `FsParser(false)` exporte les octets du `.fs`. Le vrai `RawParser(false)`
contrôle que la route `.bin` n’inverse, ne cadre ni n’ajoute d’octets. L’image
comprend le payload puis les **anciens octets** jusqu’à la frontière64KiB ;
les octets plus loin ne sont pas reprogrammés. Le dump final est comparé sur
**toute la capacité**, y compris ce reste de flash.

Cela protège la mémoire SPI ordinaire ; les registres d’état/protection,
OTP et fusibles ne sont pas une sauvegarde de ces dumps. Aucun bulk erase,
unprotect, accès OTP ou changement de protection n’est demandé.

Le programmeur peut imprimer deux identifications JEDEC identiques. Un
échantillon de progression arrondi à100.00% peut aussi précéder le100.00%
forcé de `done()`. Le parseur accepte ces doublons légitimes, mais exige une
seule fin de chaque phase, l’ordre écriture/vérification, un code retour nul
et enfin le dump complet. « after program flash » est imprimé **avant**
l’écriture et n’est pas une preuve de succès.

## Validation locale et provenance

`python3 -B test_contract.py -v`, `test_owned.py -v` et `test_hardening.py -v` :
**43 tests réussis**, avec `test_image_contract.py -v` et
`test_producer_schema.py -v` en complément. Détail dans
`../reviews/corrected_r2_tests.json` avec empreintes.
Ils couvrent notamment état froid séparé, mauvais serial/acceptation/SHA,
preuves contradictoires, fichiers/symlinks existants, deux dumps indépendants,
arrondis de progression, sortie prématurée, signal/timeout sans retry, défaut
cleanup, relecture tronquée, et corruption hors de la zone programmée.
Les défauts reproduits avant correction restent archivés dans `../reviews`.

MiniMax via OpenCode a produit les trois modules principaux, mais a atteint
1200s avant de livrer ses tests d’intégration et son rapport : son résultat
`FAILED` reste intact (70 requêtes,104 appels d’outils). Le superviseur Codex
a fini les tests/docs et corrigé les points reproduits. Les résultats de
l’agent ne sont donc pas transformés en réussite autonome.

Les snapshots `refs/` restent strictement identiques aux livraisons relues ;
ce ne sont pas des sources concurrentes. Aucun RTL, pilote, noyau ou
constructeur commun n’est modifié. Pas de nouvelle synthèse/timing ou de
qualification matérielle revendiquée. Les helpers natifs sont exécutés dans
une copie temporaire vérifiée puis supprimée ; les preuves utiles sont gardées.

## Correctif R2 : cohérence avant toute écriture

Le contre-exemple conservé dans `../cross_review_02/supervisor_image_race.py`
modifie un octet de fin de secteur après le contrôle natif mais avant le SHA
du plan. R1 détectait la faute à la relecture, après une écriture simulée.
R2 refuse cette incohérence **avant** le runner de programmation.

`image_contract.py` est l’implémentation commune, appelée à la préparation
et sous le verrou juste avant l’écriture. Il recalcule à partir des octets
réels : SHA/longueur du payload, image exacte avec fin de secteur issue des
sauvegardes, SHA de toute la flash attendue et tailles des parties préservées.
Chaque champ doit correspondre au rapport offline et au plan. Un nouveau
passage du vrai FsParser/RawParser lie aussi le contenu à la sourceFS acceptée,
et les SHA sont revérifiés après ce contrôle natif.

Les12nouveaux tests injectent des mutations entre phases, des SHA réécrits
mais contradictoires, un mauvais expected-full et un payload rendu cohérent
avec l’image mais différent du FS accepté. Un13e produit réellement le JSON
par `load_sd_candidate.run_session` avec ses seules frontières matérielles
simulées, puis le fait consommer par le writer. Cela vérifie les schémas,
pas le boot de la carte. Les30tests précédents restent inchangés et passent.

La discipline demeure un seul propriétaire des fichiers/du verrou. Une
modification hostile après la dernière vérification n’est pas éliminée par
un contrôle logiciel de fichiers ; ce paquet ne prétend pas sécuriser un
hôte compromis. La vérification complète après écriture reste obligatoire.

La contre-revue GLM/OpenCode porte sur R1, dans `../cross_review_02`. Son
rapport brut et ses limites seront conservés séparément ; il ne constitue
pas une qualification matérielle ni une modification silencieuse de R1.
