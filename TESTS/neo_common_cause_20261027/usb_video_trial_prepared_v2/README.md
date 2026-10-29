# Contrôleur d'observation Neo v2 — préparation hors carte

La v2 corrige le défaut du contrôleur signalé par la contre-revue : un signal
pouvait lever une exception à l'entrée du `finally`, avant l'installation du
masquage, et empêcher toute tentative de retour à R19. Cela corrige l'outil
d'essai ; ce n'est pas une explication de la panne FPGA Neo.

**Aucun essai matériel effectué. `hardware_ready=false` reste obligatoire
jusqu'à la revue root.** Les bitstreams, le RTL, le Tcl, les contraintes, les
imports d'IO et la version préparée originale n'ont pas été modifiés.

## Modification ciblée

Chaque invocation utilise un `StopRequest`. Ses handlers SIGINT/SIGTERM/SIGHUP
enregistrent les signaux sans lever d'exception. Des checkpoints arrêtent les
opérations expérimentales entre deux appels bornés. Il n'y a aucun checkpoint
dans le nettoyage ou la restauration.

L'unique branche `finally` restaure R19 dès que l'observateur peut avoir été
touché. Une interruption reçue pendant la restauration est conservée dans le
rapport et levée seulement après son terme. Les signaux ne sont ni effacés
ni transformés en réussite. Avant toute mutation de l'observateur, aucune
reconfiguration inutile n'est imposée.

Si une sauvegarde du rapport échoue pendant le traitement d'une erreur,
l'erreur initiale reste `report.error` et celle du journal est conservée dans
`error_log_errors`. En cas d'échec de restauration, `restore_error` reste
distinct et l'exception conserve le contexte initial. Les sauvegardes du
nettoyage restent best effort comme dans l'original.

Le verrou Neo, les identités USB exactes, les SHA du candidat/R19 et des
dépendances, ainsi que les timeouts sont conservés. Les fonctions
`local_checks` et `restoration_guard` sont identiques syntaxiquement à
l'original. Le Tcl et ses tests sont identiques octet par octet. Les quatre
captures vidéo et la séquence UTNA n'ont pas changé.

## Contre-vérification de la proposition Beam

Avis source : `../../assisted_reviews_20261026/neo_signal_repair_beam_r1/answer.txt`.
Le principe d'un handler non levant est retenu. Le diff proposé n'est pas
appliqué tel quel :

- Ses tests ajoutent directement un entier au drapeau ; ils n'envoient pas
  les « vrais signaux » revendiqués dans le texte de l'avis.
- Effacer les signaux dans le `finally` peut faire terminer normalement un
  essai interrompu pendant le nettoyage. La v2 conserve cette information.
- Plusieurs appels expérimentaux restaient sans checkpoint intermédiaire.
  La v2 contrôle l'arrêt avant de lancer l'opération suivante.
- Un booléen local `restored_once` autour d'une branche déjà unique n'ajoute
  pas d'idempotence entre invocations. Ici, l'unicité est celle du `finally`
  et elle est vérifiée, y compris en cas d'échec de la restauration.

## Preuves locales

- `signal_tests_result.json` : 67 cas PASS. Les signaux sont réellement
  envoyés avec `os.kill` dans des processus isolés, les IO matériel sont
  simulées. 22 frontières × 3 signaux, puis une réception des trois signaux
  pendant le même nettoyage. Couverture de l'entrée du `finally`, de la
  première sauvegarde, des opérations normales, de la restauration et des
  erreurs simultanées. Zéro ou une tentative R19 selon qu'une mutation était
  possible, jamais deux ; erreur initiale et erreur de restauration distinctes.
- `controller_tests_result.json` : les 13 tests de restauration existants
  passent, y compris les erreurs de programmation, de garde et de journal.
- `protocol_tests_result.json` : les 13 tests du Tcl inchangé passent.
- `offline_result.json` relie ces résultats à la preuve RTL figée existante,
  avec trois phases valides et un témoin négatif. Cette preuve n'est pas une
  nouvelle simulation du routage et ne change pas son statut timing FAIL.
- `probe_usb_video.py --review .../review_prepared.json --check-only` passe
  avec `hardware_access=false`, sans ouvrir de sonde ni de caméra.
- Régression commune : `TESTS/dual_board/20261027_neo_usb_signal_controller_v2/result.json`,
  11 groupes PASS, `hardware_validation=false`. Elle ne remplace pas les
  tests spécifiques du contrôleur ci-dessus ni une future qualification carte.

Contrôleur : `4ea2b9f7d00fddba19fb00f1dd13816244c2b301c792464b6cf6291a3b86f9fe`.
Revue préparée : `67fa810404a592fcf721c82c2031a2795955dcdfd8231f192512ee093c4407e0`.
Le détail des changements est dans `controller.diff` et le paquet autonome
dans `review_packet.txt`.

## Limites conservées

Un signal peut attendre la fin de l'opération bornée en cours : programmeur
120 s, OpenOCD 30 s, caméra 15 s. La restauration requiert ensuite ses propres
opérations bornées ; ce n'est pas un engagement d'arrêt immédiat. Le verrou
reste acquis pendant cette restauration. Aucun contrat de survie à SIGKILL,
coupure électrique ou échec physique du programmateur n'est revendiqué.

« Internal bars » signifie mire sélectionnée et compteurs vérifiés, pas image
HDMI visuellement attestée. La photographie reste à examiner séparément.
Le contrôle POST_USB et l'extraction conservent leurs limites déjà décrites
dans `../usb_video_counterreview_01/README.md` ; aucune qualification USB HS
ou fréquence physique n'est déduite des temps hôte.
