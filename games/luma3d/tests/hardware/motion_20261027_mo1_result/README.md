# MO1 — mesure HUD, 27 octobre 2026

**Essai global FAIL, R6 restaurée.** Les deux oracles et les quatre fenêtres
A/B passent. La dernière séquence à temps réel finit normalement, mais la
garde du diagnostic échoue : la sortie de la maison efface les compteurs
locaux de mouvement avant leur impression. Aucune relance ni promotion.

État laissé : `/tmp/luma3d-pp1 --showcase`, PID **2680**, startticks **25042521**,
identité complète et progression vérifiées après reprise et lecture finale
de la sauvegarde. La boucle autonome utilise stdin `/dev/null`. Le contrôleur
est sorti avec code 1 ; CDC et verrou sont libérés. G22r0 et noyau
`6.12.112-prodock-luma3d-g3d1-r1` conservés, aucune écriture FPGA/noyau/SD/flash.
La V4 `/tmp/op2-live.save` reste identique, SHA
`2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.

## Mesures acquises

Les deux diagnostics reprennent exactement le même snapshot motion R5.
Seul `mini_ui.c` change : rendu UI R6 pour le témoin, cache du chrome et
publication de rectangles pour le candidat. Même caméra, même glissement,
mêmes règles et ressources. Un pas simulé de 1/60 s par image rend les états
comparables ; ces fenêtres ne sont pas un jeu cadencé sur le temps mural.
Elles incluent la première publication du HUD, sans chauffe exclue.

| Activité / variante | Images | FPS | Préparation CPU / image | p95 ≤ | p99 ≤ | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Maison, témoin | 360 | 8,37 | 60,84 ms | 276 ms | 312 ms | 557,75 ms |
| Maison, candidat | 360 | 12,39 | 22,60 ms | 116 ms | 148 ms | 713,74 ms |
| Shooter, candidat | 600 | 45,91 | 4,04 ms | 40 ms | 76 ms | 543,01 ms |
| Shooter, témoin | 600 | 37,85 | 8,61 ms | 48 ms | 220 ms | 398,84 ms |

Les bornes percentiles viennent d'un histogramme de 4 ms. Les maxima de ces
fenêtres, qui incluent l'entrée, restent plus hauts avec le candidat. Le journal
ne donne pas l'indice des images correspondantes : leur attribution à l'entrée
n'est pas démontrée. La cadence n'est donc pas qualifiée comme régulière. Une seule paire prédéfinie par activité a été mesurée.

Les états finaux, les commandes, les batches et les octets UI sont identiques
entre chaque paire : maison `c5384401`, 8 322 commandes, 782 424 octets UI ;
shooter `e84b1a71`, zéro commande de raster/3D et 785 320 octets UI. Le shooter
utilise les couches/sprites de scanout. Aucune erreur GPU, aucun underflow ou
sliver dans les fenêtres. Les deux images de diagnostic passent exactement
(pixels 3D de la maison et banques UI) ; palette/descripteurs sont validés
localement, pas relus comme une capture composite du LCD.

## Échec final conservé

La maison à temps mural produit 161 images, 12,733 s simulées et 13,414 s
murales. Le journal donne `activity_exit=1`, `active=0`, `showcase_status=1`,
code de sortie du programme 0 et compteurs GPU sans erreur. Le callback BACK
appelle `l3_maze_motion_reset`, puis le diagnostic imprime `moves=0` ; la
garde `moves>0` rejette donc le résultat. Les zéros finaux ne permettent pas
non plus de prouver l'absence d'un débordement de file visuelle antérieur.

Le binaire hôte exact reproduit cette remise à zéro après les mêmes 12,733 s
simulées et le même CRC final `6d7eacac` :
`../../../candidates/arcade_motion_r1/tests/measurement_lifetime_r1/result.json`.
La correction prévue conserve les compteurs sur toute la durée du diagnostic,
sans modifier le reset de présentation ni les règles. Le FAIL matériel
d'origine n'est pas reclassé. Aucun essai supplémentaire n'a été lancé.

Les pastilles disparaissent encore au pas logique, environ 100 ms avant
l'arrivée du personnage interpolé : limite visuelle connue de ce lot. La
présentation des contacts et ramassages sera corrigée séparément.

## Identités et preuves

- Paquet : `../motion_20261027_mo1_prepared_r2/`, manifeste
  `2fe601fdf3f3d7469bd0b3bb06d32abe42e3243ab1d2ee47e59f7490a51cd464`.
- Témoin diagnostic : `72d138d8052262229eba17254d86bdc8c48e4623e94162c8dad660b555858e23`.
- Candidat diagnostic : `d776da6e802ebc5ce6c691683264be35abd1aae801794172d3cdfed4dd6b4aad`.
- R6 restaurée : `d8f65131f8ad4834501850d39354be98a666e484822085004dea13c8fd1c0a48`.
- `result.json` contient le FAIL original et la récupération ;
  `measurement_summary.json` résume les fenêtres sans changer le verdict.
- 437 055 octets transférés en RAM en 113,32 s cumulées. Les lectures CRC,
  le prélude et le chargement des ressources s'ajoutent à cette durée.
- Chaque fils est supervisé par son PID distinct et son vrai EXIT ; aucune
  commande UART n'est émise pendant ses mesures.
