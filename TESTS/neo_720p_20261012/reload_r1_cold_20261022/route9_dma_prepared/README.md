# Préparation R9 DMA — aucun routage lancé

Le [constructeur](../route9_dma_cone.py) reprend exactement les **entrées R8 C150**, même si R8 est encore en cours. Seul le [CST](candidate.cst) change : [huit ajouts INS_LOC](constraints.diff), sans nouvelle synthèse, nouveau clock routing, déplacement HDMI, changement SDC/DDR/RTL/options ou intervention carte. Le futur dossier est `tang/impl/console_neo_n56r9_route9_dma_c150` ; il n’existe pas au terme de la préparation.

Les [40 empreintes d’entrées](review.json), les primitives avant/après synthèse, leurs paramètres INIT, les 18 nets de frontière et toutes leurs charges sont conservés dans le manifeste. Les quatre tests locaux, onze mutations CST refusées, le contrôle `before_build('neo', candidate=True)` et la relecture exacte `--verify-prepared` passent : [résultats](local_checks.json). Le premier brouillon, dont la comparaison tuples/JSON refusait à tort un lancement inchangé, est conservé sous `../route9_dma_prepared_draft1` et n’est pas la préparation active.

Les huit cellules sont :

| Cellule sous `u_accel/u_dma/` | Type | Fanout direct R7 de la sortie | Position R7 observée |
|---|---|---:|---|
| n66_s4 | LUT4 | 2, internes au groupe | R65C38 |
| c_ack_s2 | LUT2 | 3, internes au groupe | R65C39 |
| n84_s1 | LUT2 | 1, interne | R62C40 |
| n76_s2 | LUT3 | 1, interne | R62C40 |
| c_ack_s0 | DFFRE | 16 vers le blitter | R16C88 |
| f_done_s0 | DFFRE | 15 vers le blitter | R27C75 |
| w_done_s0 | DFFRE | 16 vers le blitter | R35C76 |
| write_accepted_s0 | DFFRE | 21 dans le DMA | R65C38 |

Le chemin R7 reset→n66→c_ack→c_ack_s0 échoue de **−3,447 ns**, dont 15,435 ns de route : 10,810 ns jusqu’à n66 et 4,467 ns jusqu’au registre final. Les deux branches f_done et w_done donnent −3,334 et −2,695 ns. La branche write_accepted passe à +1,298 ns ; elle reste dans le groupe pour ne pas séparer les deux charges de n66. Ce sont des mesures R7, pas une prédiction R8/R9.

La région proposée, **R[40:65]C[65:90]**, rapproche les quatre LUT et les quatre FF, entre le reset R7 R60C90 et les destinations C75..88. Le reset source conserve son ancrage existant. Les registres d’état restent libres : ils se trouvaient R63C38..39 et alimentent des nets de 145, 40 et 142 charges. Le déplacement peut donc allonger leurs branches. Les autres entrées externes sont b_grant (9 charges), fill_write (5), pixel_write (2) et les resets synchrones des FF. Les 68 charges externes des quatre sorties imposent aussi une revue des nouveaux chemins sortants. Ce choix n’est ni un modèle de congestion ni une garantie de timing.

Le STA R7 annonce un fanout de 663 sur le reset source ; le net alias `gpu_debug_state[47]` du `.vo` expose 20 pins directes à l’indexeur. Le manifeste garde ces deux vues distinctes. Aucun choix ne repose sur l’hypothèse que le reset n’aurait que 20 charges physiques.

Depuis la racine du dépôt, vérification sans écriture de build :

```sh
PYTHONDONTWRITEBYTECODE=1 python3 TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_dma_cone.py --verify-prepared
```

Après validation de root seulement, commande de routage isolé :

```sh
PYTHONDONTWRITEBYTECODE=1 python3 TESTS/neo_720p_20261012/reload_r1_cold_20261022/route9_dma_cone.py --route-reviewed
```

Le constructeur refuse un dossier de sortie existant et toute dérive du manifeste, du CST, des helpers ou de la campagne locale. Après routage, il contrôle setup/hold/recovery/removal, l’observateur, les contrôles globaux et les huit primitives. Il conserve les échecs et ne charge jamais une carte. La comparaison complète avec R8 restera une étape distincte, incluant ses trois canaux HDMI et tous les domaines de timing ; aucune qualification n’est acquise par cette préparation.
