# R8 C150 terminé — timing global FAIL

Les [rapports comparés et leurs SHA](comparison.json) sont complets ; les builds restent inchangés et aucune carte n’a été utilisée. R8 a généré son bitstream, mais **n’est pas qualifié**. R9 DMA8 est une expérience distincte encore en routage au moment de cette analyse.

| Contrôle, ns | R7 C140 | R8 C150 |
|---|---:|---:|
| Setup | −3,447 | −3,494 |
| Hold | +0,124 | +0,124 |
| Recovery | −0,759 | −1,337 |
| Removal | +0,277 | +0,347 |

| HDMI | R8 recovery, ns | R8 removal, ns |
|---|---:|---:|
| Canal 0 | +0,477 | +0,505 |
| Canal 1 | +0,368 | +0,505 |
| Canal 2 | +0,063 | +0,626 |

Les trois canaux HDMI passent les contrôles statiques, avec une marge recovery minimale de 0,063 ns. Cela ne qualifie ni le reste du circuit ni une libération de reset sur matériel. Les routes globales sont identiques à la référence de comparaison R3, sans nouvelle promotion signalée ; les limites historiques de cette référence restent présentes.

R8 : bitstream SHA `2772efc295b17758c6e09757ba7085ebbf1b224f3b8d17334934733f3a0c9e03`, rapport timing SHA `b883e99e937cf9bf8cd81fcd6176fe0e81423ad7f9afa5d62f984668c70345ad`.

Le résumé Gowin affiche 149 endpoints « setup ». Les groupes donnent 91 bus et 51 DDR. La section setup imprime 144 chemins négatifs vers 133 destinations, parmi 1 000 chemins. Ces agrégations ne sont pas interchangeables : **leur soustraction ne permet pas de compter les violations recovery**. L’extraction des sections recovery/removal complètes figure dans [details.json](details.json).

| Recovery négatif | Slack, ns | Position destination R8 | Route depuis vid_hrstn_r, ns |
|---|---:|---|---:|
| u_gpu/mrst_0_s0 | −1,337 | R87C177 | 8,425 |
| u_gpu/mrst_1_s0 | −1,337 | R87C177 | 8,425 |
| u_scan_observe/up_0_s0 | −0,969 | R86C166 | 8,044 |
| u_scan_observe/up_1_s0 | −0,969 | R86C166 | 8,044 |
| u_accel/engine_resetn_2_s0 | −0,455 | R84C57 | 7,632 |

La source est `u_soc/vid_hrstn_r_s0`, R50C120. Aucun chemin removal imprimé n’est négatif. Les points de synchronisation et les règles recovery/removal ne doivent pas être supprimés pour obtenir PASS.

Le pire setup R8 est désormais `w_len_3_s0 → position_3_s1` à −3,494 ns : 14,346 ns de route et 1,968 ns de cellules. La logique initiale n58 est compacte autour de R54C58, puis le chemin fait un détour vers `n2949_s17` R22C135, `n2949_s12` R54C118 et le registre final R71C34. Ces trois routes coûtent 4,489, 1,989 et 7,328 ns. Une expérience future limitée aux **deux LUT n2949_s17/n2949_s12**, proches du registre position, serait un candidat plus petit que déplacer tout le DMA. Elle devra aussi vérifier leurs entrées w_addr/s_addr/w_req, le retour position et les termes de retenue : aucun gain n’est prédit et aucune contrainte de cette expérience n’a été écrite.

Le second groupe critique concerne le contrôle CEA des BSRAM de police : `vid_hrstn_r → n9128_s1 → n78_s2 → n78_s0 → mem_mem_*`, jusqu’à −3,108 ns. Les grands trajets sont 7,133 ns jusqu’à la première LUT et 5,965 ns jusqu’au BSRAM. Il constitue un autre cône, à examiner séparément du DMA et des synchroniseurs de reset.

Le cône R7 choisi pour R9 n’est plus le pire de R8. Le chemin imprimé vers c_ack est positif à +1,722 ns avec une autre source DDR-init ; les trois autres sorties ne figurent pas dans les 1 000 chemins setup. Leur absence ne prouve pas leur marge. R9 garde sa motivation R7 et sera comparé au **même baseline R8**, sans modifier le candidat pendant son routage.

L’audit strict de l’observateur reste FAIL : il détecte 374 changements de nom du net RESET/CLEAR. Le [complément de preuve](details.json) établit que :

- exactement ces 374 raccordements changent, sans différence de type de registre, D, CLK, CE ou INIT ;
- `n6_6` est produit par une LUT1 `INIT=2'h1` dont l’entrée est `vid_hrstn` ;
- le nouveau net est produit par une INV ayant la même entrée, donc la même table de vérité ;
- le nouveau net dessert 1 458 pins (1 430 RESET, 22 CLEAR, 6 SET), sans pin d’horloge ni route globale ;
- les mêmes 374 différences étaient déjà signalées dans R3 et R7.

Cette preuve locale explique un dédoublement d’inverseur introduit au routage. Elle n’est pas une équivalence complète du circuit et ne garantit aucun délai analogique. **Aucun audit existant ni résultat FAIL n’a été réécrit.**
