# Contrôleur Neo v3 — relecture root requise

La v3 corrige deux points démontrés lors de la relecture Fable : le rapport
conserve désormais l'erreur d'une interruption reçue pendant le retour R19,
et le contrôleur refuse Python optimisé (`-O`, `-OO`, `PYTHONOPTIMIZE`) qui
désactive les gardes `assert`. La v2 et les imports partagés restent intacts.

**Aucun accès carte effectué. `hardware_ready=false`.** La qualification
et le timing global du bitstream restent FAIL. Aucun FPGA n'a été recompilé.

Contrôleur SHA :
`ed322fb1041023087540aed6ba3c63fc00613318112156370f4238fddc5a38d7`.
Revue préparée SHA :
`d98eb02808a7d2f5f00608b3a6cd2176bf3780a47f116879da086d6a77d39005`.
`controller.diff` compare v3 à la v2 figée. Les checks SHA, le verrou,
l'identité USB, les timeouts et le Tcl restent ceux du plan précédent.

## Résultats hors carte

| Campagne | Résultat | Portée |
|---|---:|---|
| Frontières de nettoyage et erreurs | 73 PASS | Vrais SIGINT/SIGTERM/SIGHUP, IO carte mockées ; comprend panne du journal après interruption tardive et erreur primaire active à l'entrée du `finally`. |
| Vrai helper `run_child` | 15 PASS | Enfants Python inoffensifs, signaux asynchrones au PID/groupe pendant expérience ou restauration ; timeout, récollection et conservation du handler vérifiés. |
| Python optimisé | 14 refus corrects | Sept points d'entrée × `-O`/`PYTHONOPTIMIZE=1`. Aucun faux résultat PASS écrit. |
| Restauration existante | 13 PASS | Erreurs de garde, de programmeur et de sauvegarde ; une seule tentative de restauration. |
| Protocole Tcl inchangé | 13 PASS | Lectures/écritures simulées ; ordre UTNA1,6,2,2 conservé. |
| Préflight | PASS | `--check-only`, aucun IO matériel ouvert. |

`offline_result.json` et `review_prepared.json` lient les sources et résultats
exacts. La preuve RTL figée antérieure (trois phases et un témoin négatif)
reste distincte de ces tests du contrôleur. `REVIEW_FABLE.md` conserve la
réponse contradictoire avec preuves, sans appliquer automatiquement son avis.

## Contrat de restauration

Les handlers de signal enregistrent sans lever. Les checkpoints expérimentaux
arrêtent le déroulement entre opérations ; aucun checkpoint n'interrompt le
nettoyage. Après toute mutation possible de l'observateur, la branche unique
`finally` tente le retour au bitstream R19 exact, vérifie la garde et conserve
les erreurs de test, de restauration et de journal séparément.

Le marqueur `touched` est conservateur : s'il est posé juste avant un arrêt,
R19 peut être rechargé même si la première commande UTNA n'est finalement pas
émise. Cette décision évite d'assumer un état intact après une opération
potentiellement partielle.

Le signal peut attendre le terme de l'appel bloquant en cours, puis la
restauration. Les sous-processus restent bornés (programmeur120s,
OpenOCD30s, caméra15s), avec leurs vérifications et délais périphériques.
Ces valeurs ne constituent pas une borne totale égale au seul timeout du
programmeur. Le verrou reste détenu pendant le retour R19.

Les processus enfants utilisent des sessions distinctes ; les tests envoient
le signal au contrôleur ou à son groupe, jamais au groupe privé du programmeur.
Aucune survie à SIGQUIT, SIGKILL, coupure électrique, échec physique de
programmation ou arrêt du système n'est promise. Une erreur finale d'écriture
du rapport peut encore empêcher sa persistance ; elle survient après la
branche de restauration et ne doit pas être interprétée comme un succès.

« Internal bars » désigne la mire sélectionnée et les compteurs vérifiés,
pas une image HDMI attestée. La photographie devra être examinée séparément.
