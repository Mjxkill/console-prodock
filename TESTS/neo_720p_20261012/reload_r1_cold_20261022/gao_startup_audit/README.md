# Audit indépendant GAO N56r10 avant fin du routage

**PASS limité à l'insertion générée et à son rapport de synthèse.**
Le [résultat détaillé](result.json), SHA
`cf6e96fc9ee0d261f71f67e4d2de06b36dbc0e85e79e78c6e2b49c0ef70fa755`,
conserve les SHA de tous les fichiers stables `impl/gao`, du XML, des
entrées applicatives et des sources IP installées effectivement référencées.
Les identités ont été revérifiées après lecture. Aucun processus de
construction ni matériel n'a été ouvert, modifié ou interrompu.

Vérification réalisée par [audit_generated.py](audit_generated.py) :

- Le wrapper `gw_gao_top.v` contient exactement les vingt sondes attendues,
  toutes présentes aussi dans les entrées et raccordements de `gao.v`
  synthétisé vers `u_la0_top`.
- `clk_i=clk_d`, net issu de l'IBUF du port `clk`, contraint à20ns/50MHz.
  Cette fréquence est une contrainte du design, pas une mesure matérielle.
- `trig0_i=ddr_init`, un seul match activé, expression M0, valeurs initiales
  M0/M1=1, contrôle=0 ; XML demandé `ddr_init==1` conservé.
- `CORE0_DEF_CAPTURE_INIT_DATA` est défini dans les sources générées.
  `STORAGE_DEPTH=4096`, une fenêtre, position de déclenchement demandée128,
  soit2,56µs avant déclenchement dans une fenêtre totale81,92µs.
- `SIG_PORT_WIDTH=20`, `NUM_TRIG_PORTS=1`, `TRIG_PORT_WIDTH_0=1`,
  `CAPTURE_TRIG_0=1`, `MEM_DATA_WIDTH=DATA_OUT_SHIFT_WIDTH=21`.
- Paramètres internes conservés : `MAX_DATA_DEPTH_INIT=4095`,
  `DATA_DEPTH_INIT=3965`. L'écart de pipeline interne n'est pas démontré
  indépendamment, car les corps IP fournisseur sont protégés.

Le vecteur `data_i` contient `pll_lock` en bit19 et `u_soc/state_0[0]`
en bit0, dans l'ordre exact du XML. Le JSON donne les vingt correspondances.
Ce vecteur ne définit **pas à lui seul** l'ordre du flux mémoire de21bits,
qui comprend aussi le déclencheur capturé. Ne pas supprimer ce bit ni
deviner sa position à partir du nombre de sondes ; utiliser les métadonnées
et fonctions de lecture GAO.

| Ressource | GAO seul, synthèse |
|---|---:|
| Registres | 354 |
| LUT | 556 |
| ALU | 15 |
| BSRAM | 6 |

Ces nombres viennent de `gao_syn_rsc.xml` et concordent avec le rapport
HTML de hiérarchie. Ce ne sont ni les ressources finales du design entier,
ni une mesure de son impact sur les routes d'horloge/reset.

Le netlist applicatif, le CST et le SDC sont identiques à R9. Le candidat
instrumenté doit toutefois être routé à nouveau : il ne constitue pas
une observation du bitstream R9 original.

Après routage, restent obligatoires la vérification des vingt connexions
réelles dans le VO final, des seules charges ajoutées au design, de la
distribution des clocks/resets, des ressources et du timing finaux, des
artifacts/SHA et des métadonnées de lecture. La capture matérielle et la
qualification fonctionnelle restent non établies par cet audit.
