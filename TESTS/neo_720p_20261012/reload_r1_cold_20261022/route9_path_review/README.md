# R9 : timing amélioré, qualification toujours FAIL

Bitstream `1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde`. La [comparaison indépendante](comparison.json) vérifie les empreintes des rapports et bitstreams R8/R9. Aucun accès matériel ni modification des résultats de construction n’a été effectué par cette analyse.

| Minimum, ns | R8 | R9 |
|---|---:|---:|
| Setup | −3,494 | −0,849 |
| Hold | +0,124 | +0,124 |
| Recovery | −1,337 | −0,360 |
| Removal | +0,347 | +0,196 |

| Canal HDMI | Recovery R9, ns | Removal R9, ns |
|---|---:|---:|
| 0 | +0,816 | +0,196 |
| 1 | +0,706 | +0,263 |
| 2 | +0,658 | +0,298 |

La section setup imprime 1 000 chemins, dont 62 négatifs vers 56 destinations distinctes. La section recovery 3.1 imprime 10 000 chemins, dont **exactement deux négatifs** : `vid_hrstn → u_gpu/prst_0_s0` et `prst_1_s0`, chacun −0,360 ns. Leur route prend 7,425 ns, de R50C120 vers R103C173. Les agrégats du résumé STA ne doivent pas être soustraits pour déduire le nombre de violations recovery.

Les anciens échecs recovery R8 sont positifs dans R9 : `mrst_0/1` +0,093 ns, `u_scan_observe/up_0/1` +1,875 ns, `engine_resetn_2` +2,756 ns. Les douze étages `engine_resetn` ont une recovery positive ; reset4 vaut +2,141 ns. Une marge positive sur ces chemins ne qualifie pas les deux chemins `prst` encore négatifs.

Le nouveau pire setup est `u_accel/u_blitter/rp_0_s4 → u_accel/busy_sync_0_s0`, −0,849 ns et 6,198 ns de route. Les suivants concernent le pont SoC, puis le moteur géométrique, la police et plusieurs chemins de reset/contrôle. Les compteurs de l’observateur ont eux-mêmes des chemins setup négatifs : leurs mesures devront être corroborées par les registres du scanout.

Les huit primitives contraintes par R9 ont exactement les mêmes types, broches et INIT après routage. Les destinations `position3`, `c_ack`, `f_done`, `w_done`, `write_accepted` sont absentes des 1 000 chemins setup imprimés R9 ; cette absence n’est pas une preuve exhaustive de réussite. Le [SDF des neuf arcs des deux LUT de position](dma_tail_sdf_comparison.json) montre néanmoins un fort changement physique :

| Arc, maximum SDF en ns | R8 | R9 |
|---|---:|---:|
| n2949_s12 → position3 | 7,328 | 1,476 |
| position3 → n2949_s12 | 6,528 | 1,542 |
| n2949_s16 → n2949_s12 | 6,102 | 0,941 |
| n2949_s15 → n2949_s12 | 5,989 | 1,160 |

En contrepartie, les entrées w_addr/s_addr/w_req de n2949_s17 prennent 1,7–2,35 ns de plus. La proposition R10 fondée sur R8 reste non lancée ; ses coûts initiaux ne décrivent plus R9.

Quatre allocations globales changent par rapport à R8 et R3 :

| Net | Avant → après | Nature et charges directes |
|---|---|---|
| gpu_debug_state[48] | local → LW | Q de engine_resetn_4, 9 charges D/LUT/INV |
| u_accel/u_v1/n59467_5 | LW → local | LUT4 INIT8000, 246 charges CE |
| u_accel/u_v1/n60439_3 | LW → local | LUT2 INIT8, 390 charges CE |
| u_accel/u_v1/n61613_3 | local → LW | LUT2 INIT8, 165 charges CE |

Les fonctions et listes de charges directes restent identiques à R8, sans broche CLK. Toutefois, derrière l’inverseur de reset4 se trouvent **2 612 RESET et 38 SET** du moteur de pixels. Le FAIL `gpu_reset_tree` est conservé : ce net n’est pas un simple témoin de debug. Les changements CE ne sont pas qualifiés pour des commandes GPU par cette analyse.

La [preuve standard d’alias reset](../../../../tang/impl/console_neo_n56r9_route9_dma_c150/scan_observer_reset_alias_proof.json) démontre uniquement l’équivalence logique de l’inverseur `!vid_hrstn` pour 374 registres (372 RESET et 2 CLEAR). Tous leurs autres champs restent identiques. L’audit strict original reste FAIL.

La [revue structurelle exacte](../../../../tang/impl/console_neo_n56r9_route9_dma_c150/scan_reset_route9_trial_review.json), produite par [ce script](../review_route9_scan_trial.py), compare aussi 21 étages de reset et documente les quatre changements globaux. Son `passed:true` s’applique exclusivement à ses vérifications structurelles/identités, avec `qualification_status:FAIL` et le périmètre « CPU arrêté, diagnostic reset/RGB du scanout ». Elle ne prouve ni la fiabilité physique des resets, ni le fonctionnement Linux, ni celui du moteur géométrique. Le chargement et le repli éventuels relèvent du seul opérateur Neo.

Le protocole isolé du coordinateur, SHA `445c5a8c6f9bd26a1c2c08142915b7bcde7c19d7e1c95cfeebf4c6b4deefa7dc`, a été relu : aucune reprise CPU ni commande accélérateur ; repli armé avant programmation ; retour vérifié par progression des frames, deux configurations et deux checksums. Onze mutations du préflight ont été refusées en mémoire (SHA, statut, timing, pulse, audit, scope, étages, alias), puis le préflight réel a passé, sans subprocess ni carte. C’est une vérification de procédure, pas une qualification matérielle.
