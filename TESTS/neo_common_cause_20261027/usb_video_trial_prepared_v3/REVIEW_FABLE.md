# Contre-vérification de Fable — v2 puis v3

Relecture réellement exécutée par Claude Code avec le modèle demandé `fable` :
`TESTS/assisted_reviews_20261026/neo_usb_controller_v2_fable/answer.txt`.
Paquet103680octets, SHA
`711839922ce666c05a0950490b304c78f17dbe36e98497ebaf15b47306399f76`.
Le modèle n'a exécuté aucun test et aucun outil matériel. Les preuves ci-dessous
ont été exécutées localement après sa réponse. La v2 reste inchangée.

| Point Fable | Conclusion et preuve |
|---|---|
| Correction de la fenêtre de signal v1 | Confirmée. Les handlers non levants ferment cette voie d'exception avant le `finally`. Les cas réels v2 passent, sans qualification de la carte. |
| D1 : absence de `report.error` pour un signal arrivé seulement pendant le nettoyage | **Confirmé**, 34 cas dans le rapport v2 existant. La restauration était terminée et le signal figurait dans `signals_received`, mais la clé d'erreur manquait. La v3 journalise l'exception après nettoyage, puis la relève. Une panne de ce journal est conservée séparément et ne remplace pas l'interruption initiale. |
| D2 : les enfants de restauration pourraient recevoir le Ctrl-C du contrôleur | **Réfuté pour l'import réel.** `probe_route9_led_compare.py:run_child` emploie déjà `start_new_session=True`. Les 15 tests supplémentaires exécutent ce helper exact avec des enfants Python inoffensifs et des signaux asynchrones au PID ou au groupe du contrôleur. Les enfants ont PID=PGID=SID distincts du contrôleur et survivent aux signaux de son groupe. |
| D3 : `-O`/`PYTHONOPTIMIZE` désactivent les gardes `assert` | **Confirmé**, hérité de v1. Le contre-test appelle uniquement `local_checks` de v2 avec une fausse SHA et `hardware_ready=false` ; Python optimisé accepte ces fichiers, Python normal refuse. La v3 refuse l'optimisation dès `main`, avant traitement des arguments. Les scripts de test/préparation refusent également : 14 contrôles PASS. Aucun lancement matériel n'est utilisé pour reproduire le défaut. |
| D4 : reprogrammation conservatrice possible avant la première commande UTNA | Fait conservé et documenté, pas un défaut de restauration. Le marqueur `touched` invalide l'hypothèse d'état préservé avant de pouvoir entrer dans une opération potentiellement partielle. Un signal dans cette très petite fenêtre peut conduire à restaurer R19 sans commande UTNA effectivement émise. Supprimer le checkpoint ferait commencer l'opération malgré un arrêt demandé. |
| D5 : tests seulement synchrones aux frontières Python | Limite réelle de la v2. Les nouveaux tests asynchrones traversent le vrai `run_child`, avec attente bloquante, signaux pendant la restauration, erreur primaire en cours, timeout, arrêt et récollection du fils. Les IO de la carte restent mockées. |

La proposition de test Fable employait `signal.getsignal(sig) is stop.handler`.
Cette comparaison d'identité est incorrecte pour un attribut méthode lié,
qui produit un nouvel objet à chaque accès. Le test utilise l'égalité de
méthodes ; il ne signale pas à tort une réinstallation du handler.

Le helper réel tue son propre groupe enfant avec SIGKILL sur timeout et attend
sa terminaison ; il ne dépend pas du SIGTERM supposé dans l'avis. Aucun patch
de ce helper partagé, aucun `preexec_fn`, aucun nouveau masque POSIX n'est
nécessaire ni appliqué.

Les signaux sont reçus par le contrôleur, pas envoyés délibérément au groupe
privé du programmeur. La preuve concerne ce contrat précis. SIGQUIT, SIGKILL,
arrêt système et coupure électrique restent hors contrat. Les trois signaux
pris en charge sont enregistrés dans `signals_received` ; leur conversion en
`KeyboardInterrupt` n'est pas une promesse de code de sortie POSIX identique
au numéro reçu.

Fable valide le mécanisme de restauration et propose un contrôle matériel
ultérieur ; son avis ne constitue pas ce contrôle. La préparation v3 conserve
`hardware_ready=false`, qualification FAIL et timing FAIL du bitstream.
