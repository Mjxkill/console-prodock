# Proposition GAO startup R9 — lecture seule, configuration par root

Liste vérifiée dans `tang/impl/console_neo_n56r9_route9_dma_c150/console_neo.vg`,
SHA `0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157`.
Les chemins sont relatifs à l'instance top `console_neo` ; la syntaxe
d'affichage/qualification complète est à conserver selon l'importeur GAO.
Aucune insertion, configuration ou construction n'est effectuée ici.

Horloge de capture indépendante : **`clk_d`**, sortie de l'IBUF de la
référence carte50MHz. Ne pas choisir `vid_hclk`, `gpu_clk` ou `core_clk`
comme horloge unique pour diagnostiquer précisément leur absence.

| Bits proposés | Net exact post-synthèse | Ce qu'il observe |
|---|---|---|
| 0 | `pll_lock` | LOCK brut PLL AE350 |
| 1 | `pll_ae350_lock` | LOCK AE350 filtré par PLL_INIT |
| 4:2 | `state_178[2:0]` | État PLL_INIT AE350 ; sortie filtrée autorisée à7 |
| 6:5 | `ae350_rst_sync[1:0]` | Deux étapes du reset AE350, INIT11, sortie attendue00 |
| 7 | `u_soc/init_sync[0]` | Premier FF de synchronisation DDRinit vers AHB |
| 8 | `soc_dbg[0]` | Second FF init_sync, net des POR/HW AE350 |
| 9 | `ddr_init` | Fin de calibration DDR, également LED V13 inversée |
| 10 | `u_soc/exts_hrstn` | HRESETN issu du bloc AE350 dur |
| 11 | `vid_hrstn` | HRESETN réenregistré sur AHB, reset scanout |
| 12 | `soc_dbg_177[1]` | LOCK DDR filtré |
| 13 | `soc_dbg_2_3` | STOP IP DDR relié à ENCLK2 PLL DDR |
| 14 | `vid_hclk` | Net d'horloge AHB80MHz |
| 15 | `gpu_clk` | Net d'horloge UI DDR75MHz |

Extensions courtes si20bits acceptables : `u_soc/pll_lock` (LOCK brut DDR)
et `u_soc/state_0[2:0]` (PLL_INIT DDR). Les deux machines PLL_INIT ont des
noms d'état différents ; `state[2:0]` au top n'est pas l'alias à choisir
pour l'état PLL AE350, qui est raccordé à `state_178`.

Preuves dans le VG : wires top1153079–1153100,1153129,1153215–1153224 ;
instance PLL AE3501163182–1163192 ; instance SoC1163193–1163264 ;
`u_soc/init_sync_0_s0`1145166–1145173 ;
`u_soc/init_sync_1_s0`1145270–1145277 ;
`u_soc/vid_hrstn_r_s0`1145263–1145269.

Alias importants : le nom RTL `bus80_clk` est devenu `vid_hclk` ;
`init_sync[1]` n'existe plus comme net vectoriel dans ce module, sa sortie
est `soc_dbg[0]`. Le FF existe bien. Les clocks sont présentes dans les
ports des modules synthétisés : PLL AE350 sortie0→vid_hclk, sortie1→core_clk,
sortie4→rtc_clk ; gpu_clk sort du sous-système DDR.

## Captures et limites

À50MHz,16kpoints couvrent327,68µs et64kpoints1,31072ms. Or le source
`pll_init.v:19` impose WAIT_TIME=2ms pendant plusieurs passages du balayage
ROM, avant STATE7. Une capture initiale brute limitée à ces profondeurs
peut donc se terminer avant la libération normale, même sur une carte saine.

Prévoir une vue longue au moyen des fonctions réelles de capture qualifiée
ou décimation GAO si elles sont disponibles, puis une vue courte autour
de la fin de calibration/libération reset. Vérifier que le mode initial
arme réellement l'instrument dès configuration et ne dépend pas d'une
action JTAG effectuée après le démarrage déjà terminé. Une capture qui
attend seulement le front DDRinit ne peut pas conclure quand ce front
n'arrive jamais ; conserver aussi une observation finale indépendante.

Les niveaux PLL/reset échantillonnés sont asynchrones à50MHz : cette
capture peut distinguer des séquences stables, pas garantir l'ordre de
transitions espacées de moins20ns. Les clocks80/75MHz sont sous-échantillonnées
et peuvent s'aliaser ; leurs transitions sont un indice d'activité, pas
une mesure de fréquence ni une preuve d'absence quand les échantillons
sont constants. Une mesure de période fiable demanderait une observation
adaptée ou des témoins divisés réellement disponibles. La clock800MHz
brute n'apporte pas de mesure exploitable à50MHz.

Enfin, l'insertion GAO et son nouveau placement/routage produiront un
**nouveau candidat**, même depuis la netlist R9 identique. Sa capture ne
doit pas être présentée comme un enregistrement du bitstream R9 original
`1593a2…e2fde`. Conserver ce dernier et ses échecs intacts ; si le candidat
instrumenté démarre différemment, cela devient un résultat distinct.
