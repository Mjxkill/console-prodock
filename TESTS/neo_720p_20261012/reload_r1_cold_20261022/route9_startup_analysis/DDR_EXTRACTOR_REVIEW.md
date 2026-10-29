# Revue indépendante de l’extraction DDR

Extracteur relu : [analyze.py](../route9_ddr_io_compare/analyze.py), SHA-256 `abe56a1137084d17fd5b849be7a186beaf1db7ab574136e3c7bfe7eb9416b19a`. Aucun fichier de son dossier n’a été modifié par cette revue ; aucune carte n’a été ouverte.

Deux limites détectées pendant la revue sont corrigées dans cette version : correspondance rise/fall en amont des sorties différentielles inversées `OB/IOB`, et couverture des trajets OEN vers les PAD DQ/DQS. L’extracteur conserve également toutes les branches après IODELAY.DO, au lieu de supposer une charge unique.

Le [contrôle indépendant](check_ddr_samples.py) n’importe pas l’extracteur. Il relit les SDF, suit DQ0, DQS0 positif/négatif, CK positif/négatif et A0, puis recalcule 15 trajets par build. Les **45 comparaisons sont PASS** avec les résultats produits ; [preuves et lignes SDF](independent_ddr_samples.json). Cela vérifie ces trajets témoins, pas l’exhaustivité de tous les chemins du FPGA.

| Calcul témoin, ns | MIN | TYP | MAX |
|---|---:|---:|---:|
| DQ0 PAD→buffer→IODELAY→IDES.D | 0,608+0+0,266+0 = 0,874 | 0,613+0+0,333+0 = 0,946 | 0,619+0+0,399+0 = 1,018 |
| DQS0 PAD→buffer→DQSIN | 0,608 | 0,613 | 0,619 |
| Clock OSER→Q→PAD positif, rise | 1,160+0+2,716 = 3,876 | 3,887 | 3,897 |
| Clock OSER→Q→CK_n, rise PAD | 1,146+0+2,716 = 3,862 | 3,873 | 3,883 |

Ces valeurs sont identiques pour N56r8, R2 et R9. Pour CK_n, la transition en amont du buffer est descendante : le délai OSER 1,146 ns remplace 1,160 ns. Les arcs OEN ont une sémantique de commande trois états, pas de transition de donnée DQ ; l’extracteur le signale.

L’entrée DQ0 comporte une dérivation réelle en plus d’IDES.D. Sur R9, IODELAY.DO atteint `u_ddr_phy_wds/n468_s1/I0` en 0,343 ns maximum ; le total PAD→cette entrée LUT est donc 1,361 ns. La netlist précise sa fonction :

- `n468_s1`, LUT4 INIT `0001`, reçoit DQ[0..3] après IODELAY et produit leur NOR.
- Son résultat rejoint `n468_s0`, LUT2 INIT `7`, puis `in_dq0_reg_0_s0`, DFFCE sur `gpu_clk`, CLEAR=`ddr_rst`.
- Le registre suivant `in_dq0_0_s0` alimente `u_ddr_init/n1872_s2/I0` et `n1883_s1/I1`. Les deux arcs sont aux lignes 2635762/2635761 du SDF R9.

Cette dérivation rejoint donc la logique d’initialisation après deux registres. Son délai jusqu’à la première LUT n’est ni le délai de réception IDES, ni un délai complet de calibration.

Le [complément pour les 32 DQ](complete_calibration_taps.py) prolonge maintenant chaque tap jusqu’à **D du premier FF** : [données complètes et segments](calibration_taps.json), [table des 32 broches et trois builds](calibration_taps.csv). Les 96 trajets passent exactement par une NOR4 `INIT=0001`, puis une NAND2 `INIT=7`. Le sens négatif de chaque entrée LUT est calculé à partir de sa table INIT ; les fronts des segments amont sont inversés en conséquence. La chaîne entière est positive. Les quatre destinations sont `u_ddr_phy_wds/in_dq0_reg_[0..3]_s0`, toutes DFFCE sur `gpu_clk`, à raison de huit DQ par FF. Types, connexions et INIT des LUT/FF sont identiques dans les trois builds.

| Somme PAD → premier FF.D | N56r8 | R2 | R9 |
|---|---:|---:|---:|
| Maximum parmi les 32 chemins, ns | 3,058 (DQ25) | 3,063 (DQ19) | 3,084 (DQ6) |
| DQ0 MIN / TYP / MAX, ns | 1,519 / 1,950 / 2,380 | 1,505 / 1,957 / 2,408 | 1,488 / 1,893 / 2,297 |

Les sommes rise/fall sont ici égales avec ces arcs SDF, bien que le calcul conserve leurs polarités. Parmi les chemins individuels, R9 ajoute au maximum 0,683 ns par rapport à N56r8 (DQ5, 2,295→2,978 ns) et 0,444 ns par rapport à R2 (DQ8, 1,949→2,393 ns). D’autres chemins raccourcissent. Ce sont des chemins sensitizés lorsque les autres bits du groupe sont stables à zéro ; ni les aléas combinatoires, ni la phase d’arrivée DQ, ni la clock de capture ne sont calculés. Il serait incorrect de soustraire simplement ces sommes à la période de `gpu_clk` pour annoncer une marge.

Le IODELAY de DQ0 est statique : `C_STATIC_DLY=5`, `DYN_DLY_EN=FALSE`, `ADAPT_EN=FALSE`, DLYSTEP/SDTAP/VALUE à zéro. En revanche DQS reçoit RMOVE/RDIR/RCLKSEL/DLLSTEP/WSTEP de la logique de calibration, et DLL_FORCE vaut FALSE. L’identité des paramètres et des arcs fixes ne révèle pas les valeurs effectivement atteintes par ces contrôles sur carte.

Limites conservées : les chemins `launch` commencent à la broche d’horloge du sérialiseur et n’incluent pas la route d’arrivée de cette horloge ; les groupes clocks l’exposent séparément. Les sommes ne combinent pas les phases DDR ni les checks setup/hold, ne sont pas une marge d’œil et n’incluent pas le circuit imprimé ou la DRAM. La première arrivée à une entrée LUT n’inclut pas le reste du cône combinatoire ni les cycles de sa machine d’état. Aucune de ces égalités ne qualifie R9 ou ne prouve la cause de son échec DMI.
