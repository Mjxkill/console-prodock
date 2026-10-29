# N56r4 : qualification refusée

Le constructeur relu a terminé normalement. Aucun accès matériel, chargement
ni promotion n'a été effectué par cet agent. Le parent reste N56r3, avec sa
netlist, son SDC, ses fréquences, sa DDR et ses sources inchangés ; seules
les sept contraintes régionales décrites dans `constraints.diff` sont ajoutées.

Bitstream :
`f3b068882450a47c197c67c00ebd68f4add5f5f8df42e51ee4cec83c4683e3f6`.

| Contrôle temporel | Marge minimale |
| --- | ---: |
| Setup | −0,489 ns |
| Hold | +0,124 ns |
| Recovery | −1,946 ns |
| Removal | +0,354 ns |

La table détaillée contient 59 chemins setup négatifs : 57 intradomaine
(9 bus80, 48 UI DDR) et deux CDC d'observation. Elle contient également deux
chemins recovery négatifs. Le champ historique `violated_endpoints.setup=61`
du qualificateur agrège ici les 59 setup et les deux recovery ; il ne représente
pas 61 violations setup distinctes. La qualification complète reste **FAIL**.

Les recovery négatifs sont `u_soc/vid_hrstn_r_s0/Q` vers
`u_accel/engine_resetn_4_s0/CLEAR` (−1,946 ns) et `engine_resetn_2_s0/CLEAR`
(−1,378 ns), sous la borne CDC inchangée de 8 ns. Le pire setup est
`u_soc/u_bridge/st_0_s1/Q` vers `m_hrdata_31_s0/CE` (−0,489 ns).

Les anciens endpoints d'observation 49 et 57 ne figurent plus dans les
chemins négatifs. Deux autres observations deviennent négatives : bit25
(−0,087 ns) et bit34 (−0,070 ns). D'autres chemins DMA/cache/commandes et
ITCM deviennent également négatifs. Cette expérience ne ferme donc pas
le timing et ne justifie aucune exception de chargement.

Les dix audits structurels du qualificateur, le profil DDR et l'audit local
`observer_placement_audit.json` passent. Le driver, tous les pins, l'INIT et
l'ensemble des charges des quatre contrôles locaux restent exacts ; reset4
est lui aussi inchangé logiquement. Les quatre contrôles et reset4 sont
absents du tableau complet des ressources globales.

La distribution globale change néanmoins ailleurs :

- Reset4 et CAMERA/viewport (`n57378_3`) sortent du tableau LW.
- `v1_pending` y entre, avec huit charges combinatoires directes.
- `u_gpu_debug/n4022_5` y entre, avec 315 entrées CE.
- Le contrôle de face `u_accel/u_v1/n59467_5` reste LW.

Ces changements sont constatés, sans conclure que tout signal LW est
défectueux. Le placement de reset4 est publié à R18C45[0][A], dans sa région.
Les six autres instances placées ne sont pas publiées dans les chemins du
rapport : leurs contraintes et leur logique sont vérifiées, mais leurs
positions physiques restent inconnues avec ces seuls rapports.

Ressources : 85 043 / 138 240 logiques, 54 885 / 139 095 registres,
58 408 / 69 120 CLS, 263 / 340 BSRAM, 176,5 / 298 DSP.

Preuves complètes :
`tang/impl/console_neo_n56r4/qualification.json`,
`observer_placement_audit.json`, `impl/pnr/console_neo.tr`,
`impl/pnr/console_neo.rpt.txt` et les deux journaux de qualification.
