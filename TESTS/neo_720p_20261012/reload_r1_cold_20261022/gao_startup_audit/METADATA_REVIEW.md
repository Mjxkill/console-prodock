# Métadonnées de N56r10, sans changement des entrées

Le qualificateur [check_neo_timing.py](../../../../tools/check_neo_timing.py:109)
sélectionne le VG racine uniquement en présence de `route.json`. Le constructeur
GAO a effectivement réutilisé ce VG, mais n'a pas écrit ce marqueur. Le VG
alternatif `impl/gwsynthesis/console_neo.vg` n'est donc pas l'entrée applicative
de cette construction.

La correction proposée est le [nouveau manifeste](route_metadata.proposed.json),
SHA `5ad9c42ba6ef686b81586da57d60ba19e2e12409458368497c11603d37b2b026`.
Il décrit R9 → R10 avec instrumentation GAO, conserve le FAIL du parent et
épingle les sources, le VG, le Tcl, le CST/SDC et les preuves. Il ne réutilise
pas la description historique R8 → R9 et ses huit contraintes DMA comme si
elles étaient un nouveau changement de R10.

Le [vérificateur](prepare_metadata_proposal.py) a comparé les arbres sources,
le VG, le delta exact du Tcl et l'ensemble des fichiers générés GAO déjà
audités. Il n'écrit jamais dans le candidat. Son mode `--verify-complete`
refuse le routage tant que le résultat final et les marqueurs de fin FS/TR
ne sont pas présents ; ce refus a été vérifié pendant la compilation.

L'opérateur parent pourra, **après fin du routage et revue**, exécuter :

```sh
python3 TESTS/neo_720p_20261012/reload_r1_cold_20261022/gao_startup_audit/prepare_metadata_proposal.py --verify-complete
cp --no-clobber TESTS/neo_720p_20261012/reload_r1_cold_20261022/gao_startup_audit/route_metadata.proposed.json tang/impl/console_neo_n56r10_gao_startup/route.json
python3 tools/check_neo_timing.py tang/impl/console_neo_n56r10_gao_startup
```

Le code retour du qualificateur doit rester non nul si le timing ou un audit
échoue. Aucun PASS n'est anticipé, aucune commande ci-dessus n'a été exécutée
sur le candidat par cet audit. La présence du manifeste ne valide pas les
sondes finales ; leur audit reste distinct.

Les dix audits du parent exact sont : `copy`, `scanout`,
`gpu_owner_replication`, `timing_closure`, `cpu_ddr_fifo_registers`,
`gpu_reset_tree`, `gpu_pixel_mask`, `gpu_pixel_mask_routed`,
`gpu_pixel_selector`, `gpu_pixel_selector_routed`. Ils seront tous déclenchés
par le qualificateur inchangé grâce aux mêmes marqueurs de sources. Le
résultat historique de `gpu_reset_tree` est FAIL : reset4 utilise encore une
ressource globale. Son résultat R10 doit être recalculé, jamais recopié.

R9 ne contient aucun `wide_gpu_controls.json` et aucun sélecteur
`incremental`, `wide_gpu_controls_local`, `requested_primary_gpu_control_nets`
ou `requested_local_gpu_control_nets`. Aucun de ces audits optionnels n'a été
retiré : ils n'étaient pas activés sur ce parent. Le vérificateur refuse si
l'un de ces éléments apparaît afin qu'une nouvelle revue traite explicitement
son héritage.

Le [plan de raccordement](expected_probe_bindings.json) conserve les pilotes
physiques des vingt sondes et du sample clock dans le R9 terminé, avec
primitives, paramètres et empreintes de leurs charges. Il prépare le contrôle
du futur VO R10 sans ouvrir les artefacts en cours. Les 263 primitives de
démarrage déjà inventoriées fourniront le second témoin de comparaison.
Le vecteur applicatif contient vingt bits ; la mémoire GAO en contient21
avec le trigger capturé. La disposition finale ne sera pas devinée.
