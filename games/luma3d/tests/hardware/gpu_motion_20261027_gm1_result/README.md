# GM1 — résultat matériel

Résultat global : PASS. Aucun résultat partiel ne requalifie MO1.
Manifeste : `ed04a3f1b41e07f75d9f0c97770f473fb15748cab28d24fa58f98259e407d64a`.
Jeu candidat : `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.

Les fenêtres fixes comparent un pas logique par image. Le tour en temps réel est séparé. Les percentiles sont des bornes supérieures de bacs de 4 ms ; le maximum est exact. Les coûts SUBMIT incluent le pilote et son attente, sans attribution automatique au seul GPU.

| Mode | Variante | Phase | Images | FPS | Préparation ms/image | SUBMIT ms/image | PRESENT ms/image | p99 ≤ ms | Max ms / index |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Blocs | baseline | entry | 2 | 2.39 | 397.779 | 0.000 | 20.576 | 580 | 579.293 / 0 |
| Blocs | baseline | rest | 12 | 56.81 | 1.728 | 0.000 | 15.701 | 28 | 25.660 / 3 |
| Blocs | baseline | moving | 360 | 39.72 | 7.865 | 0.000 | 16.111 | 316 | 361.943 / 93 |
| Blocs | candidate | entry | 2 | 1.53 | 608.296 | 30.833 | 12.245 | 1016 | 1014.735 / 0 |
| Blocs | candidate | rest | 12 | 56.54 | 2.750 | 0.000 | 14.661 | 24 | 21.684 / 13 |
| Blocs | candidate | moving | 360 | 41.32 | 4.116 | 3.878 | 14.728 | 92 | 145.095 / 94 |
| Fusion 1024 | candidate | entry | 2 | 1.31 | 739.501 | 15.192 | 8.662 | hors histogramme | 1254.674 / 0 |
| Fusion 1024 | candidate | rest | 12 | 55.70 | 3.233 | 0.000 | 14.507 | 24 | 21.758 / 9 |
| Fusion 1024 | candidate | moving | 360 | 31.12 | 5.842 | 10.470 | 14.236 | 96 | 109.500 / 275 |
| Fusion 1024 | baseline | entry | 2 | 2.35 | 416.417 | 0.000 | 9.182 | 620 | 616.153 / 0 |
| Fusion 1024 | baseline | rest | 12 | 55.63 | 1.806 | 0.000 | 15.901 | 20 | 19.997 / 8 |
| Fusion 1024 | baseline | moving | 360 | 27.77 | 18.727 | 0.000 | 15.997 | 432 | 437.457 / 223 |
| Simon | baseline | entry | 2 | 2.41 | 358.161 | 41.681 | 15.060 | 540 | 539.923 / 0 |
| Simon | baseline | rest | 12 | 16.66 | 10.227 | 34.201 | 15.413 | 112 | 108.667 / 13 |
| Simon | baseline | moving | 360 | 16.01 | 15.035 | 31.273 | 14.298 | 256 | 288.019 / 241 |
| Simon | candidate | entry | 2 | 1.09 | 852.722 | 52.070 | 16.146 | hors histogramme | 1236.174 / 0 |
| Simon | candidate | rest | 12 | 53.73 | 1.479 | 0.000 | 16.861 | 28 | 25.009 / 2 |
| Simon | candidate | moving | 360 | 29.22 | 3.441 | 13.531 | 14.141 | 112 | 127.932 / 224 |
| Maison | candidate | entry | 2 | 1.91 | 458.258 | 50.064 | 16.125 | 708 | 705.492 / 0 |
| Maison | candidate | rest | 12 | 12.07 | 26.787 | 44.071 | 11.425 | 124 | 123.586 / 3 |
| Maison | candidate | moving | 360 | 12.22 | 22.877 | 40.280 | 14.223 | 136 | 145.608 / 28 |
| Maison | baseline | entry | 2 | 2.30 | 384.149 | 39.301 | 11.129 | 548 | 544.051 / 0 |
| Maison | baseline | rest | 12 | 12.53 | 24.067 | 42.156 | 13.379 | 112 | 108.953 / 9 |
| Maison | baseline | moving | 360 | 8.43 | 59.855 | 41.565 | 14.797 | 308 | 309.168 / 134 |
| Shooter | baseline | entry | 2 | 2.76 | 347.170 | 0.000 | 14.754 | 400 | 396.981 / 0 |
| Shooter | baseline | rest | 12 | 54.35 | 2.475 | 0.000 | 15.750 | 24 | 21.425 / 2 |
| Shooter | baseline | moving | 360 | 43.95 | 5.255 | 0.000 | 15.581 | 200 | 238.592 / 215 |
| Shooter | candidate | entry | 2 | 2.30 | 422.640 | 0.000 | 12.419 | 544 | 543.618 / 0 |
| Shooter | candidate | rest | 12 | 57.01 | 1.918 | 0.000 | 15.135 | 28 | 24.632 / 12 |
| Shooter | candidate | moving | 360 | 49.96 | 2.244 | 0.000 | 15.134 | 64 | 90.594 / 151 |

Les deux images d’entrée sont publiées séparément du régime établi. Les huit images les plus longues, leurs indices et leurs composantes sont conservées dans `result.json`. Les cycles géométrie sont des deltas modulo 32 bits, pas un total garanti sans enroulement.

| Mode | Ratio temps moyen candidat/témoin | Garde |
|---|---:|---|
| Blocs | 0.9613 | acceptée |
| Fusion 1024 | 0.8924 | acceptée |
| Maison | 0.6896 | acceptée |
| Simon | 0.5479 | acceptée |
| Shooter | 0.8799 | acceptée |

Seuils prédéfinis : moyenne +10 %, p99 +25 % +4 ms, maximum +50 % +20 ms. Ce sont des gardes de non-régression, pas une qualification 30/60 FPS.

Tour réel : 772.622 s simulées, 783.232 s murales, 1079 commandes légales, masque visité/gagné ff/ff. Ces temps ne sont pas une durée de campagne humaine.

État final : /tmp/luma3d-gm1 --showcase; autonomous background loop, stdin /dev/null.
Ancre vérifiée : PID 2925, startticks 26240721.
save_initial SHA : `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.
save_final SHA : `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.

Oracles : pixels RGB réellement publiés et octets UI. Palette/descripteurs sont validés localement ; ce n’est pas une lecture composite complète du LCD. Les compteurs contacts/files appartiennent au diagnostic, pas au bilan du vrai main après BACK.

SHA du résultat brut : `8cb582b9cbbe3e3ac1c8d2516eac67b8c219f43001bded456bf070c2442f3b32`.

## Vrai tour complet, entrées et transitions incluses

Ces valeurs ne sont pas les courtes fenêtres A/B ci-dessus.

| Mode | FPS | p99 ≤ ms | Maximum ms |
|---|---:|---:|---:|
| Exploration | 10.65 | 236 | 293.78 |
| Circuit | 19.95 | 420 | 454.50 |
| Blocs | 38.37 | 148 | 797.38 |
| Formes | 20.65 | 420 | 581.17 |
| Fusion1024 | 21.61 | 148 | 1071.14 |
| Maison | 11.83 | 384 | 581.38 |
| Simon | 25.70 | 148 | 1072.07 |
| Shooter | 43.40 | 92 | 382.86 |
| Tour | 19.72 | 216 | 435.15 |

Les modes circuit/formes et l’exploration n’ont pas reçu de refonte GPU dans ce lot. La maison reste lente ; les p99 élevés empêchent de qualifier tous les jeux de fluides. Aucun nouveau test matériel n’a été lancé après GM1.
