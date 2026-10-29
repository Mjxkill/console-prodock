# Options de routage : vérification dans la documentation locale

Documentation officielle installée avec Gowin V1.9.12.03. Aucun accès web,
option cachée extraite d'un binaire ni modification de fréquence/SDC.

| Source | Page imprimée | Conclusion étayée |
| --- | ---: | --- |
| SUG1018-1.7E, §2.7 | 14–15 | `CLOCK_LOC "net" LOCAL_CLOCK;` demande une distribution locale. Aucun `signal_type` ne peut accompagner LOCAL_CLOCK. |
| SUG1018-1.7E, §2.7 | 15 | Pour BUFG, les catégories sont CLK, CE, SR, LOGIC. Le document distingue donc explicitement les contrôles des horloges. |
| UG306-1.0.7E, Overview | 3 | Le réseau GCLK inclut les ressources PCLK et LW. |
| SUG100-4.4.6E, Route configuration | 39 | Route Maxfan ne contrôle pas le routage long wire ni clock. Il ne fournit donc pas un moyen documenté d'empêcher la promotion CE vers LW. |
| SUG100-4.4.6E / SUG1220-2.0E | 39 / 42 | Clock Route Order choisit l'ordre par fanout ou fréquence. Aucune promesse de désactivation des promotions CE. |
| SUG1018-1.7E, NET_NO_REP | 24–25 | NET_NO_REP empêche la réplication d'une ressource. Il ne documente pas une interdiction LW. |
| SUG1220-2.0E, replicate_resources | 40 | L'option concerne la réplication du fanout, déjà désactivée dans cette expérience. |

Les options exposées dans `data/config/rtlrouteoptions.xml`,
`rtlplaceoptions.xml`, `rtlplacerouteoptions.xml` et
`rtlplacerouteoptions5at.xml` ont également été relues. Aucun interrupteur
documenté distinguant « promotion automatique des contrôles CE vers LW »
de la distribution des vraies horloges n'a été identifié dans ces sources.
Cela ne prouve pas qu'une option interne n'existe pas.

Les contraintes explicites par net constituent donc la méthode documentée
disponible ici. Leur présence dans le CST ne prouve pas leur respect physique :
le cas reset4 de R3 impose de relire l'intégralité du tableau final des
ressources globales, en plus du timing et des connexions.

Les extractions texte locales sont conservées dans `docs/`. Elles proviennent
des PDF officiels de `/home/michael/gowin/IDE/doc/EN/`.

# Inventaire et proposition avant gel de R5

L'inventaire corrigé contient **2 015 nets CE non constants**. Il déroule les
bits des connexions vectorielles et concaténées des DSP et mémoires. Les ports
rencontrés sont CE, CEA, CEB, OCE, OCEA et OCEB ; aucun de ces ports n'est ignoré.
Les fichiers `inventory_scalar_only_superseded.*` sont conservés pour tracer
la correction, mais leurs comptages ne sont pas la preuve finale.

Les deux contrôles demandés pour R5 sont :

| Contrôle | Driver | INIT | Charges exactes | Horloges |
| --- | --- | --- | --- | ---: |
| CAMERA `u_accel/u_v1/n57378_3` | LUT3 `n57378_s0` | 8'h80 | 198 DFF + 6 CE DSP = 204 | 0 |
| FACE `u_accel/u_v1/n59467_5` | LUT4 `n59467_s1` | 16'h8000 | 240 DFF + 6 CE DSP = 246 | 0 |

Proposition minimale : R3 exact avec uniquement ces deux LOCAL_CLOCK, sans
les sept placements de R4. Elle conserve une expérience lisible mais ne peut
garantir l'absence d'autres promotions.

Pour prévenir les promotions déjà observées dans R4, une extension à revoir
séparément protégerait aussi `u_gpu_debug/n4022_5` (315 CE, LUT3 INIT 8'h90),
`v1_pending` (8 charges combinatoires, DFFRE INIT 1'b0) et son inverse
`u_accel/v1_tx_addr_27_12` (317 CE). Ces trois nets n'alimentent aucun pin CLK.
Une contrainte sur `v1_pending` ne contraint pas automatiquement son inverse.

L'inventaire compte 321 contrôles non protégés ayant au moins 32 CE. Ce seuil
sert seulement à présenter la liste : il n'est pas un seuil de promotion Gowin
documenté. Appliquer des contraintes à tous ces nets sans examen modifierait
largement la recherche de routage et pourrait dégrader le timing. Aucune telle
extension n'a été appliquée.
