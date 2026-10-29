# Alias des resets GPU N57

`result.json` prouve le raccordement des douze bascules
`u_accel/engine_resetn_0_s0` à `engine_resetn_11_s0`. Leurs sorties Q sont les
ports scalaires `gpu_debug_state_44` à `gpu_debug_state_55` du module
`gpu_accel`, reliés dans le module supérieur aux bits `gpu_debug_state[44]`
à `gpu_debug_state[55]`.

Les noms internes hiérarchiques sont donc `u_accel/gpu_debug_state_44` à
`u_accel/gpu_debug_state_55`. Les pilotes DFFCE, leur INIT=0 et toutes leurs
broches sont vérifiés. Les connexions hiérarchiques vers les charges sont
résolues ; aucun de ces douze nets n'alimente une broche d'horloge.

Le CST d'origine contient déjà douze contraintes LOCAL_CLOCK portant sur les
bits au niveau supérieur. R5 utilise néanmoins des LW pour les resets 0, 4
et 7. `proposed_additions.cst` contient donc les douze contraintes utilisant
les noms internes scalaires, à ajouter sans retirer celles d'origine. Cette
proposition a été revue par root avant intégration dans la nouvelle préparation
N57 ; le présent dossier ne modifie aucun snapshot ni fichier commun.

La documentation locale SUG1018-1.7E §2.7, pages 14–15, définit CLOCK_LOC sur
un nom de net et LOCAL_CLOCK comme un routage local. Elle ne précise pas quel
alias est reconnu avant l'aplatissement hiérarchique. La preuve de connexion
ne garantit donc pas que Gowin appliquera les contraintes internes. Le test
reste discriminant : conserver un éventuel rejet du parseur, puis contrôler
les ressources réelles et tous les audits reset après routage. Aucune exception
SDC, fréquence ou logique n'est modifiée pour obtenir un PASS.
