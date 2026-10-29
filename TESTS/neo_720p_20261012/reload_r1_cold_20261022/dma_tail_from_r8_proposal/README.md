# Proposition CST : deux LUT du DMA, base R8 exacte

**Préparée seulement, aucun routage lancé.** Le [générateur](../prepare_dma_tail_from_r8.py) n’a aucun mode de lancement de Gowin. Il produit le [CST](candidate.cst), le [diff](constraints.diff) et les [preuves/empreintes](review.json). La garde de construction Neo candidate passe ; neuf mutations CST interdites sont refusées. Aucun fichier de R8 ou du R9 en cours n’est modifié.

L’expérience ajouterait uniquement :

```text
INS_LOC "u_accel/u_dma/n2949_s12" R[55:75]C[45:65];
INS_LOC "u_accel/u_dma/n2949_s17" R[55:75]C[45:65];
```

Elle repart du **CST R8 C150**, sans les huit cellules regroupées dans R9. Netlist, RTL, SDC, reset HDMI, ancrages existants et options restent ceux de R8. Le netlist, le rapport STA, le netlist routé, le SDF et le bitstream sont vérifiés contre leurs SHA connus avant analyse.

Le chemin critique R8 `w_len3 → n58 → n2949_s17 → n2949_s12 → position3` donne −3,494 ns. Le groupe n58 est déjà compact autour de R54C58 ; le chemin part ensuite à R22C135 puis R54C118 avant de revenir au registre position3 R71C34. La région proposée place les deux LUT près de n58 et du registre final, sans déplacer ces pilotes ni les registres du DMA. Les deux LUT existent dans le netlist synthétisé, avec INIT `CACC` et `AA3C`, et chacune a **une seule charge en sortie**.

Les neuf arcs SDF donnent les coûts suivants. Les valeurs sont celles de **R8 aux coins min/typ/max Gowin**, pas des estimations pour la proposition ; les maxima du chemin critique concordent avec le rapport STA.

| Branche | Fanout du net source | Min / typ / max, ns |
|---|---:|---:|
| w_addr3 → n2949_s17.I0 | 1 | 0,265 / 0,410 / 0,553 |
| s_addr3 → n2949_s17.I1 | 6 | 0,683 / 1,234 / 1,785 |
| n58_s6 → n2949_s17.I2 | 37 | 2,004 / 3,247 / 4,489 |
| w_req → n2949_s17.I3 | 48 | 0,411 / 0,893 / 1,375 |
| n2949_s17 → n2949_s12.I0 | 1 | 0,751 / 1,370 / 1,989 |
| position3 → n2949_s12.I1 | 17 | 3,065 / 4,796 / 6,528 |
| n2949_s16, retenue position[2:0] → n2949_s12.I2 | 1 | 2,230 / 4,166 / 6,102 |
| n2949_s15, état DMA → n2949_s12.I3 | 12 | 2,053 / 4,021 / 5,989 |
| n2949_s12 → position3.D | 1 | 3,184 / 5,256 / 7,328 |

Le déplacement vise surtout les trois branches actuellement à 5,989–6,528 ns et la sortie à 7,328 ns. En contrepartie, les entrées w_addr/s_addr/w_req peuvent devenir plus longues : elles sont aujourd’hui proches de la première LUT. Par exemple, s_addr3 se trouve R3C149, loin de la région proposée. Les positions absentes du rapport limité sont conservées comme inconnues ; les bases de placement chiffrées n’ont pas été décodées. La somme des maxima d’arcs ne remplace pas une nouvelle analyse STA complète et ne permet pas de prédire le gain.

La recherche des contraintes existantes montre :

- **Aucun INS_LOC direct** sur les deux LUT, leurs sept pilotes directs ou le registre final position3. Leur placement en détour n’est donc pas imposé explicitement par le CST.
- Le CST ancre déjà un groupe FIFO/blitter dans R[1:25]C[140:175] : pointeurs de FIFO, compteurs et contrôle de mémoire. s_addr3 est physiquement dans cette région, mais n’est pas lui-même ancré.
- Une [chaîne de huit connexions vérifiées](anchor_context.json) relie indirectement s_addr3 aux coordonnées lues dans la mémoire de commandes, puis aux pointeurs/contrôles de cette mémoire. Elle traverse des registres et la mémoire : ce n’est pas un chemin combinatoire STA. Cette proximité peut expliquer une préférence de placement, **sans démontrer que les contraintes anciennes causent le détour**. Il faudrait un essai séparé supprimant ces contraintes pour tester cette hypothèse ; cette proposition les conserve toutes.

Les essais futurs devront comparer à R8 les délais des **neuf branches**, tous les chemins entrants vers position3, les sorties des autres charges des nets à fanout 37/48/17/12 et le timing global. Les cinq violations recovery déjà présentes dans R8 restent des problèmes distincts ; les marges HDMI doivent être revérifiées. Aucun bitstream ni résultat de qualification n’est produit par cette préparation.

Reproduction dans un **nouveau dossier** depuis la racine du dépôt :

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/prepare_dma_tail_from_r8.py --out TESTS/neo_720p_20261012/reload_r1_cold_20261022/dma_tail_from_r8_recheck
```
