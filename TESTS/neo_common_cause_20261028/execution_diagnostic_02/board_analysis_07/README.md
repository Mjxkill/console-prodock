# COPY vide sur R19 : rejet terminé confirmé

Le résultat root `root_empty_copy_run_01` est lié aux fichiers dans facts.json.
Le firmware exact 0e9b249f… ne change que l’étendue demandée de COPY à 0×0.
Le GPU atteint done2, busy0, rejected1 ; le programme finit phase8/résultat−5.
Ce code désigne ici un rejet après completion et ne prouve pas un timeout.
Le contrôleur n’a pas signalé d’erreur et a restauré R19.

Les images CPU comparées comptent32/32/0 : seed et contrôle TARGET terminés,
aucune relecture après COPY dans cet essai. Ne pas extrapoler la mémoire finale.
Le contrat RTL prévoit zéro transfert natif pour ce paquet valide vide, mais
les signaux natifs ne sont pas observés sur R19 : aucune absence physique de
trafic n’est mesurée. La commande vide subit encore les validations du
header, de la cible et du descripteur avant le clipping.

Le prochain contrôle préparé est TARGET→CLEAR(flags0)→COPY(0×0), sans
réécrire TARGET entre CLEAR et COPY. CLEAR0 terminé sans rejet témoigne que
la cible était valide pendant sa validation. COPY peut néanmoins ensuite
rejeter si cette cible change ou si son propre chemin de validation échoue.
Une réussite de la séquence ne distingue pas à elle seule une latence de
stabilisation d’un effet d’état apporté par CLEAR ; ne pas conclure une cause.
Le firmware aura un journal MD13 distinct, un code−8 pour l’échec CLEAR0
et−5 pour COPY, trois completions attendues, le même scratch128B et des
boucles bornées. Root seul décide et exécute l’essai sur la carte.
