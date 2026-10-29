# Simulation fonctionnelle post-routage du scanout R1 et de son arbitre

Résultat : **PASS** dans `simulation.log` et `result.json`.

Le banc extrait les cônes complets `u_gpu`, `u_scan_queue` et
`u_soc/g_ddr.u_ddr/u_gpu_arb` du fichier post-PnR de N56r1. Les 20 714
primitives et leurs `defparam` sont repris sans modification ; les 24 cellules
externes requises sont des décodeurs de registre et inverseurs de reset.
Les modèles de primitives sont ceux de Gowin. Le test ne remplace aucun moteur
GPU, état d'arbitrage ou compteur de requêtes par un modèle comportemental.

Le framebuffer RGB565 est configuré par le bus avec une largeur de 1280 pixels,
un stride de 2560 octets et une base de 0x01700000. Les compteurs raster sont
placés juste avant le blanking pour éviter de simuler toute une trame avant la
première requête. Les horloges du banc sont distinctes : bus 80 MHz, mémoire
75 MHz et pixels environ 74,375 MHz, avec des phases différentes.

Le modèle du point d'entrée DDR accepte les commandes uniquement quand il est
prêt. Il impose 3 cycles de blocage sur 11, puis renvoie chaque réponse après
16 cycles. Le banc vérifie 80 commandes de lecture natives, les 80 adresses
ordonnées attendues, les 80 retours, la fin de la requête et le basculement ACK.
Les valeurs inconnues sur les moniteurs de commande provoquent un échec.

## Limites

- Simulation logique sans SDF : aucune validation des délais physiques,
  du routage global/local, du skew ou de la métastabilité.
- Le contrôleur DDR physique et les mémoires externes sont remplacés à leur
  interface native ; ce n'est pas un essai de DDR sur carte.
- Les requesters CPU et dessin sont maintenus inactifs à leur frontière. Le
  test ne couvre pas la contention CPU/GPU, les accès CPU ni le rendu de jeu.
- Le scénario s'arrête après la première ligne RGB565. Il ne qualifie pas le
  compositeur, les tuiles, les sprites, la durée d'une trame ou HDMI.
- Les réponses mémoire sont constantes, `0xffff` pour chaque pixel. La mention
  historique « patterned bursts » dans le docstring du générateur signifie
  ici ce motif constant ; le résultat vérifie le protocole, pas les couleurs
  affichées.

Le blocage de fetch observé sur la carte N56r1 n'est donc pas reproduit dans
ce scénario fonctionnel précis. Il n'est pas pour autant expliqué ni résolu.

## Historique des bancs

`routed_scanout_arb` est invalide : trois sorties de contrôle n'étaient pas
exportées et leur vérification aurait accepté des X. La compilation a expiré
avant simulation ; aucun PASS n'en est retenu.

`routed_scanout_arb_r2` a expiré à la compilation, sans résultat fonctionnel.
Son alias externe de sélecteur du blitter ne correspondait pas au nom du
fichier routé : la fermeture des dépendances embarquait inutilement presque
tout l'accélérateur (87 741 primitives). L'alias exact
`gpu_debug_state_145[99]` est prouvé par le port correspondant de `ae350_soc`
dans la netlist de synthèse et par `ext_active_s2` dans le fichier routé.
Le banc r3 corrige cette frontière et refuse désormais d'embarquer un moteur
de dessin en dépendance. Les anciennes preuves n'ont pas été réécrites.
