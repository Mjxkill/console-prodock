# G2 — blitter DDR3 et texte

Travail commencé après le commit G1 `63275ff`, sur Tang Mega 138K Pro Dock.
Cœur AE350 800 MHz, bus 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
Interface : [registres et API](../ARCHI/GPU_G2_REGISTRES.md).

## Simulation

`python3 TESTS/test_gpu_accel.py` produit les commandes et l'image attendue
en Python, puis exécute `gpu_accel_tb.sv` sous Verilator. La chaîne testée
comprend le bus AHB, la FIFO entre horloges, le rasteriseur, la police,
le DMA 256 bits et l'arbitre DDR3 avec lecteurs CPU et affichage concurrents.

- 100 commandes, comparaison de **tous les octets de trois emplacements
  de 1 Mio**, y compris les zones non dessinées et les gardes.
- Rectangles et copies aux 32 décalages possibles d'une rafale DDR3 ; masques
  des premiers/derniers octets ; pauses aléatoires déterministes du contrôleur.
- Dégradés H/V/diagonal ; rectangles découpés et coordonnées extrêmes.
- Lignes sur l'intervalle signé 16 bits, cercles, disques, rayon nul,
  centres hors écran sans retour des coordonnées sur la surface visible.
- Copies découpées à la source et à la destination, superpositions
  horizontales, verticales et diagonales ; page 15.
- Texte transparent/opaque, échelles 1/2, 16 caractères en échelle 2,
  bords de l'écran, caractères étendus, réécriture du glyphe `0x80`.
- FIFO AHB pleine avec attente du CPU, compteurs d'erreurs et commande inconnue.

Résultat : 20381 rafales écrites, dont 14327 complètes ; 187388 lectures,
dont 119365 retours CPU et 67034 retours affichage pendant le test ;
660340 cycles AHB d'attente. Aucun octet différent de la référence.

`ddr_gpu_arb_tb.sv` vérifie séparément les trois clients, les lectures et
écritures CPU/blitter, les masques distincts, la file de 16 étiquettes pleine,
les blocages indépendants commande/données, les retours simultanés aux demandes.
Résultat : 176 lectures, 37 écritures ; blitter 47/22, CPU 78 accès acceptés.

`gpu_scanout_tb.sv` conserve le test G1 à la résolution complète 800×480 :
palette, ordre des pixels, limites actives, somme, échange au retour vertical,
interruption mémoire et récupération. Résultat : **2437647 lectures CPU**,
toutes les vérifications réussies.

## Intégration

Le premier routage `gpu_g2_r1` a révélé une marge négative de −2,778 ns sur
la chaîne combinatoire affichage → arbitrage → adaptateur CPU. Il n'a pas été
chargé. Un tampon d'une requête CPU coupe désormais cette chaîne avant
l'arbitrage natif ; ses commandes et données restent associées sous blocage.

Le pilote publie explicitement les surfaces CPU : vidage/invalidation,
barrière puis relecture DDR du dernier octet pour vider les écritures
différées avant l'accès d'un autre maître. Après une écriture GPU, le CPU
attend `DONE` puis invalide son cache avant de comparer les pixels.

## Validation sur carte

**28 septembre 2026 : tests automatiques réussis.** Programmateur FTDI
`2023112818`, USB `3:12`, chargement en SRAM uniquement. Console USB CDC
`359f:2011`, `/dev/ttyACM1`. L'autre carte n'a pas été programmée.

La commande `B` produit l'image de démonstration en page cachée,
la compare à une référence CPU sur une autre page, vérifie 64 octets de garde,
puis permute l'affichage au retour vertical. Des accès DDR du CPU sont ajoutés
pendant la fin du dessin. Le script `tools/check_gpu_console.py` conserve
les tests G0/G1 et répète le test G2 trois fois, avec contrôle de la somme
lue par l'affichage, des compteurs de trames et des débordements.

Résultats conservés dans [`gpu_g2_uart.txt`](gpu_g2_uart.txt) :

- 5441 octets d'écho exact, masques DDR octet/demi-mot, adressage jusqu'à
  1 Gio, trois passes de 1 Mio : aucune erreur.
- G1 : deux pages, palette, quatre permutations, cinq tests CPU DDR concurrents
  de 1 Mio, sommes `c5c4fc70` / `a3a2ec50`, aucun débordement LCD.
- G2 : 56 commandes par dessin, trois répétitions ; chaque fois,
  **384000 pixels + 64 octets de garde comparés exactement** à une page de
  référence CPU. Accès CPU de 16 Kio pendant la fin du dessin.
- Somme de la page dessinée, vérifiée aussi par le lecteur LCD : `c4002a6c`.
  Trois tests CPU de 1 Mio supplémentaires, compteurs de trames croissants,
  `underflows=0` à chaque contrôle.
- Temps d'envoi/exécution et d'accès CPU simultanés : 12497846, 12637958 et
  12496278 cycles, soit environ **15,62 / 15,80 / 15,62 ms** à 800 MHz.
  Cela exclut la préparation des surfaces, le calcul de référence sur CPU
  et l'attente du retour vertical. Ce n'est pas une mesure générale de FPS.
- Michael confirme le 28 septembre 2026 que l'écran correspond exactement
  au rendu de référence généré : « bon c'est exactement ça ». Le programme
  laisse la démonstration G2 affichée. Cette confirmation porte sur la
  concordance de l'image ; la limite des dégradés décrite ci-dessous subsiste.

## Image finale

- Build isolé : `tang/impl/gpu_g2_r3`, sources figées et empreintes dans `sources.json`.
- Commande : `python3 tools/build_gpu.py --name gpu_g2_r3` (prendre un nouveau nom
  pour reconstruire ; le script refuse d'écraser un build existant).
- Timing : 110 chemins détaillés positifs ; marge minimale **+0,002 ns**,
  chemin calcul des coordonnées source → adresse DDR du blitter. Les 24 lignes
  de synthèse TNS sont à zéro. Cette marge est étroite ; tout changement RTL
  nécessite une nouvelle vérification de timing.
- Ressources : 15245 cellules logiques, 12603 registres, 117/340 BSRAM,
  6/298 DSP, 8/8 horloges PRIMARY. Aucune nouvelle horloge globale.
- Firmware : code en ITCM, données ILM, pile DLM ; même implantation que G1.
- Image conservée : [`console_gpu_g2_800.fs`](../bitstreams/console_gpu_g2_800.fs).
- SHA-256 : `9f66a91983795a1937fe4eab097dc5f29257c8aae2518b2ed980cc6b6aef74b0`.

Les bitstreams G1 et E2 restent disponibles comme références précédentes.
G2 ne comporte pas encore le compositeur 16 couches, les sprites ni les triangles.

## Référence visuelle et limite des dégradés de la démonstration

Michael signale des bandes à la place de dégradés doux. La démonstration
fait varier les **indices** d'une palette RGB332 (8 niveaux rouges,
8 verts, 4 bleus), ce qui produit effectivement des bandes colorées.
Les tests précédents vérifient les indices écrits et lus ; ils ne prouvent
pas une interpolation douce des couleurs. Il faudra utiliser des rampes
de palette adaptées ou ajouter une interpolation des composantes couleur.

Le [rendu attendu en 800×480](images/gpu_g2_expected.png) est généré par
`python3 tools/render_gpu_demo.py`, qui exécute sur l'hôte le rasteriseur
de référence C, les commandes et l'initialisation de palette du firmware.
Sa somme framebuffer `c4002a6c` correspond aux trois essais matériels.
L'image représente les valeurs RGB envoyées au LCD, sans simuler sa
luminosité ou sa réponse colorimétrique physique.
