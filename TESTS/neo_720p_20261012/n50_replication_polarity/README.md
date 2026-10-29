# Divergence des registres répliqués après PNR

Gowin V1.9.12.03, GW5AST-LV138PG484AC1/I0, projet console Neo.
Date : 19 octobre 2026. Aucun envoi à un tiers n'a été effectué.

## Observation vérifiée

Le modèle synthétisé accepte les commandes de configuration GPU. Sur la
carte avec N50r2, 22 TARGET valides sont systématiquement rejetés ; les
commandes de matrice sont également rejetées par le moteur de pixels.
Les compteurs de transport et les mots observés à l'entrée du blitter
sont corrects. La DDR6 à 400 MHz passe les tests mémoire échantillonnés.

Le modèle post-PNR a cinq copies `gowin_replicate_reg_v1_select_*` du DFFRE
`u_accel/v1_select_s0`. Les entrées D et CLK, ainsi que INIT, sont identiques.
L'original a CE = !ext_active et RESET = !mrst[1]. Les copies ont
CE = ext_active et RESET = mrst[1]. La copie n°1 pilote notamment la
validation de capture des 312 bits de commande géométrique et bornes.

## Reproduction sans carte

`tb.sv` contient les cellules et les inverseurs extraits du fichier .vo,
avec uniquement les connexions externes renommées. Le modèle officiel
`/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v` sert de référence.
La commande exacte du compilateur, les cellules sélectionnées et les
SHA-256 sont enregistrés dans `result.json`.

Avec les primitives officielles :

| État | Original | Copie |
|---|---:|---:|
| Reset relâché, propriétaire 3D au repos | 1 | 0 |
| Reset relâché, propriétaire 3D en cours | 1 | 0 |
| Reset asserté, CE de la copie actif | 0 | 1 |

Le test réussit lorsqu'il reproduit cette divergence connue ; son champ
`reproduced=true` ne signifie pas que le circuit est correct.

## Portée et limites

La divergence du modèle post-PNR est établie. Le défaut du bitstream n'est
pas encore établi séparément : l'export Verilog pourrait ne pas représenter
certaines inversions physiques. L'essai A/B sur carte reste nécessaire.
Il ne s'agit pas d'une preuve d'erratum FIFO, DDR6 ou silicium.
L'inspection exploratoire a retrouvé des polarités différentes dans
1 067 des 1 230 copies associées à leur sortie originale ; 124 associations
restent non résolues. Ces chiffres ne constituent pas une preuve globale
d'équivalence ou de non-équivalence du bitstream.

## A/B contrôlé

N50r4 réutilise exactement la netlist, le SDC, le CST et le manifeste de
N50r2. Seul `replicate_resources` passe de 1 à 0, hors chemins de build.
Voir `n50r2_vs_n50r4_inputs.json`. Le candidat reste à qualifier et à tester.
Le nouvel audit `tools/neo/gpu_replication.py` bloque les cinq copies du
sélecteur non équivalentes. Il ne remplace pas un contrôle de toute la netlist.

Fichiers associés : `audit.json`, `cross_build_audit.json`, `simulation.log`,
`all_raw_comparisons.json`, `all_resolved_comparisons.json`.
