# R13 préparé, moteur non exécuté

Le [test réel du frontend](frontend_result/frontend.log) confirme
`unknown option: -gao_cst`, retour Tcl 1. Son export d’options ne contient
pas cette propriété. Le lancement séparé préparé ci-dessous utilise donc
le lecteur backend déjà identifié ; il ne renomme aucun net.

Le constructeur est [prepare_gao_backend_cst.py](../prepare_gao_backend_cst.py).
Les identités sont figées dans [backend_review/result.json](backend_review/result.json)
et dans le [manifeste préparé](../../../../tang/impl/console_neo_n56r13_gao_tck_cst/backend_prepared.json).

## Portée exacte

- Application VG, GAO **déjà synthétisé**, CST principal, SDC et device.cfg :
  octets R10 conservés. Aucune nouvelle synthèse GAO.
- Un seul fichier source supplémentaire : `startup_clock.cst`, contenant
  `CLOCK_LOC "control0[0]" BUFG = CLK;`.
- `cmd.do` R10 est recopié avec les chemins vers le dossier isolé R13 et
  une seule option supplémentaire `-gao_cst <fichier>`. Le
  [diff normalisé](backend_review/cmd.diff) le vérifie. `-cst_error`, les
  fréquences, options de placement/routage et génération de rapports restent.
- Tous les sélecteurs d’audit R10 sont conservés dans `route.json` : dix
  audits requis, aucune exemption de reset/timing ou nouveau catalogue.
  Huit PRIMARY applicatifs et distribution TCK doivent être vérifiés après
  routage. Aucun résultat physique n’est anticipé.
- Aucun accès carte. R10, R11 et R12 restent intacts, avec leurs FAIL.

## Licence et appels

Le [petit module C++](gao_backend_tcl.cpp) est chargé **dans `gw_sh`**, après
la vérification normale de licence de cet exécutable. Il refuse de
s’initialiser dans un autre exécutable. Le constructeur épingle `gw_sh`,
`libgowin.so`, `libGWTE.so`, `libtcl8.6.so`, le module et toutes ses entrées.
Il n’existe aucun exécutable autonome de contournement de licence.

L’ABI est celle de l’outil installé, **non une API publique stable**. Les
appels sont vérifiés dans le lanceur officiel `GowinProxy::launchPnrTask` :

```text
ArgParser.clearAllArguments()
ArgParser.setWorkingDirPath(<sortie>/impl/pnr/)
readInUserCommand(3, {<IDE>/bin/gowin, -do, <sortie>/impl/pnr/cmd.do}, false)
executePnrTask() seulement si parsing == 0 et mode route explicite
freeGlobalMem(); closeLogFile(); setMessageFp(nullptr)
```

Les extraits [appel](backend_review/proxy_call.asm),
[argument -do](backend_review/proxy_do_argument.asm) et
[nettoyage](backend_review/proxy_cleanup.asm) sont conservés. Aucun accès à
la disposition mémoire interne des structures propriétaires n’est utilisé.

Après parsing, cinq getters du moteur doivent retourner les chemins exacts
VG/CST/SDC/GAO/CST-GAO. Le mode `args-only` s’arrête alors sans appeler
`executePnrTask`. Il ne prouve pas encore la résolution de `control0[0]`
dans le lecteur GAO : cette étape reste explicitement en attente.

## Contrôles locaux

`--check-only`, compilation du module hôte et `--verify-prepared` : PASS.
Le garde `before_build('neo', candidate=True)` vérifie la campagne locale
courante et la conservation de la Pro Dock avant chaque mode.

Les [tests à moteur/Tcl inertes](backend_tests/result.json) passent sous
ASan/UBSan : mauvais frontend, args-only sans route, deuxième invocation
refusée, parsing en échec, mauvaise identité, exception et nettoyage,
retour d’échec du moteur et mauvais répertoire. Ils ne chargent pas Gowin.
LeakSanitizer est indisponible dans le bac à sable sous ptrace ; son premier
échec est conservé dans `backend_tests/run.log`. La seconde exécution
contrôle ASan/UBSan avec `detect_leaks=0` et ne revendique aucun résultat LSAN.

## Commandes proposées à root, non exécutées

Premier contrôle, uniquement arguments, dans `gw_sh` sous licence :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/prepare_gao_backend_cst.py --backend-args
```

Seulement après revue du code et du résultat de ce contrôle :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/prepare_gao_backend_cst.py --route
```

Le second mode exige le résultat et les SHA du premier, puis revérifie les
entrées. Aucun log n’est écrasé. INT/TERM/HUP ou une exception tuent et
attendent uniquement le groupe enfant de ce lanceur, puis enregistrent
l’interruption. Un succès backend reste `ROUTED_NOT_QUALIFIED` ; la
qualification complète et l’audit physique GAO restent séparés.
