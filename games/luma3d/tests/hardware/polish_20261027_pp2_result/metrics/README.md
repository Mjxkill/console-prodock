# Mesures PP2 / R6 par activité

Whole activity as played, including transitions and normal logs; no fixed-scene controlled A/B.

| Activité | Images | FPS pendant activité | p95 ≤ ms | p99 ≤ ms | Maximum ms | CPU simulation ms/image | Préparation ms/image | SUBMIT ms/image | PRESENT ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Exploration 3D | 4708 | 10.89 | 164 | 220 | 303.9 | 8.18 | 13.21 | 56.58 | 13.38 |
| Circuit | 323 | 20.10 | 368 | 424 | 490.5 | 1.33 | 32.40 | 0.00 | 15.65 |
| Blocs | 244 | 32.14 | 112 | 368 | 434.2 | 1.20 | 14.01 | 0.00 | 15.52 |
| Formes | 413 | 20.67 | 364 | 420 | 591.6 | 1.26 | 31.05 | 0.00 | 15.66 |
| Fusion 1024 | 2827 | 9.63 | 408 | 440 | 454.5 | 2.08 | 86.64 | 0.00 | 14.65 |
| Maison des lueurs | 157 | 5.91 | 320 | 348 | 363.9 | 2.66 | 112.89 | 40.04 | 13.20 |
| Quatre échos | 773 | 13.51 | 256 | 296 | 350.5 | 1.50 | 27.67 | 31.42 | 13.05 |
| Vaisseau | 760 | 35.09 | 112 | 220 | 309.0 | 1.40 | 11.22 | 0.00 | 15.53 |
| Tour 3D | 327 | 16.37 | 188 | 260 | 382.9 | 1.27 | 25.93 | 20.08 | 13.43 |

Les percentiles restent des bornes de tranches. Le maximum est mesuré directement.
Le conseiller est inclus dans la simulation ; les copies UI excluent le HUD du monde et le chargement initial.
Une moyenne élevée ne prouve pas une cadence régulière : conserver les p95/p99, maximums et dépassements.
