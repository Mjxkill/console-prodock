# R14 préparé : initialisation complète du parseur Proxy

R14 reprend exactement les entrées FPGA de R13, avec les chemins isolés sous `tang/impl/console_neo_n56r14_gao_tck_cst_seeded`. R13 et son échec sont conservés. Par rapport à R10, la seule contrainte ajoutée reste le CST GAO séparé `CLOCK_LOC "control0[0]" BUFG = CLK;`, passé au backend par `-gao_cst` ; netlists applicative et GAO, CST applicatif, SDC et options de routage restent identiques.

Le wrapper précharge les sept sélecteurs attendus dans le mode Proxy : composant, part number, netlist, device.cfg, CST, SDC et netlist GAO. Il conserve `readInUserCommand(3, argv, false)`. Après parsing, il contrôle la présence et la valeur exacte des sept sélecteurs, du CST GAO et de `-cst_error`, puis les cinq chemins résolus dans `globalMem`. Toute différence refuse le routage. Les gardes de licence via le processus `gw_sh`, d'identité, de régression locale, d'interruption et les audits postroute sont conservés.

`--check-only`, `--prepare` et `--verify-prepared` ont passé localement. La compilation du module hôte passe avec `-Wall -Wextra -Werror` et résolution complète des symboles. Les [tests locaux](tests/result.json) ASan/UBSan avec moteur/Tcl factices refusent chacune des sept seeds manquantes et altérées, un mauvais CST GAO, l'absence du garde CST et les cas déjà couverts (frontend, invocation unique, erreur/exception parseur, identité, cleanup, retour moteur, cwd). Dix mutations supplémentaires du fichier de commande sont rejetées par le constructeur. Ces tests ne prouvent pas que le parseur propriétaire acceptera le candidat ; aucun binaire Gowin n'a été exécuté par cette préparation.

La [revue de préparation](prepared_review.json), le [diff constructeur](builder.diff) et le [diff module](module.diff) conservent les identités et montrent le delta exact. Le constructeur est maintenant figé.

Prochaine commande à exécuter par root sous licence, après sa revue, **arguments seulement** :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/prepare_gao_backend_seeded.py --backend-args
```

Cette commande crée un journal neuf et un résultat ; elle n'appelle pas `executePnrTask`. Aucun routage n'est autorisé avant retour et revue root. Le constructeur refuse `--route` tant que le résultat `ARGUMENTS_ACCEPTED_NOT_ROUTED` n'existe pas avec les mêmes identités et SHA de journal. Même un futur succès de parsing ne prouvera ni la résolution du net GAO, ni son allocation globale, ni la fermeture du timing. R10 conserve sa qualification FAIL.
