# Périmètre exact du contrôle post-PnR R3

Les 80 commandes du banc terminent avec les compteurs attendus. Le test
conserve les 87 111 primitives et leurs paramètres dans les cônes complets
`u_accel` et `u_gpu_debug`, et emploie les modèles officiels Gowin.

La suite couvre TARGET (dimensions, bases, strides, erreurs), matrices,
lumière, matériau, texture, plan et INVALIDATE. Elle ne contient **pas** de
commande CAMERA ni de rendu DRAW avec mémoire. Un contrôle CAMERA distinct
est préparé dans `../n56r3_camera_routed`.

Le terme « full GPU » dans le journal désigne la netlist GPU complète
retenue dans la simulation, pas une couverture de toutes ses fonctions.
Les transactions AHB, la FIFO, les décodeurs, les compteurs et la capture de
diagnostic restent inclus. CPU, `video_bus_stage`, DDR et délais physiques
restent hors du banc. La simulation n'utilise pas de SDF ; son succès ne
constitue ni une fermeture temporelle ni une preuve de fonctionnement matériel.

La netlist routée R3 utilisée a pour SHA-256
`63aaba4ad13b3855fc107c259bc10ca25aa78a14c6095cc2cf19d236adf8ce9b`.
Les commandes, modèles et autres hashes sont conservés dans `result.json`.
