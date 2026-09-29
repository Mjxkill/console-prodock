# G6 — validation du prototype de course

Ce compte rendu décrit la version r2 conservée, avant accélération matérielle.
Les mesures courantes sont dans [TESTS_GPU_FAST.md](TESTS_GPU_FAST.md).

Bitstream chargé sur la Tang Mega 138K Pro Dock le 28 septembre 2026.
Validation visuelle par Michael encore à effectuer pour cette nouvelle scène.

## Résultats sur carte

Le [journal complet](racer_uart.txt) valide G0 à G6 sur le bitstream final :
écho USB 5 441 octets, DDR CPU, double tampon, blitter, 16 couches, 64 sprites,
cubes G5, puis course. Aucun échec, descripteur invalide ou sous-alimentation
LCD pendant cette régression.

Les quatre scènes du jeu sont comparées **pixel par pixel** avec une
référence CPU, plus 64 octets de garde. L'empreinte calculée par le lecteur
LCD correspond à la référence. Le rendu Python indépendant retrouve aussi
les quatre empreintes :

| Scène | Empreinte | Commandes | Image |
|---|---|---:|---|
| Départ | `608ca111` | 316 | [PNG](images/racer_pose0.png) |
| Course, voie droite | `8843a930` | 303 | [PNG](images/racer_pose1.png) |
| Voie opposée | `6ed69a3d` | 311 | [PNG](images/racer_pose2.png) |
| Collision | `77add22e` | 306 | [PNG](images/racer_pose3.png) |

Le contrôle USB vérifie départ, accélération, directions simultanées avec
l'accélérateur, freinage, retour des touches à zéro après expiration du délai,
redémarrage, ainsi qu'un accès CPU DDR concurrent de 1 Mio.

Deux séries de 120 images donnent **54,40 puis 53,60 images/s**, avec zéro
ligne manquante. Ce sont les temps de la boucle de rendu, hors traitement
des commandes USB entre deux images ; ce résultat qualifie ces séquences,
pas tous les placements d'objets ni tous les futurs jeux.

| Mesure | Série 1 | Série 2 |
|---|---:|---:|
| Préparation CPU | 55 738 cycles / 69,67 µs | 55 011 cycles / 68,76 µs |
| Soumission + attente GPU | 12 837 998 cycles / 16,05 ms | 13 017 812 cycles / 16,27 ms |
| Image avec attente vblank | 14 703 792 cycles / 18,38 ms | 14 925 186 cycles / 18,66 ms |

La version initiale r1 donnait environ 27,7 images/s. r2 met le panorama en
cache DDR et dessine les deux bordures comme des bandes étroites, ce qui
élimine les principaux dessins superposés inutiles. Les fréquences et le RTL
sont identiques entre ces deux compilations.

Un premier test r2 a été lancé trois secondes avant la fin du chargement
FPGA : l'écho a été interrompu par la reconfiguration. Après rechargement et
attente explicite de la fin du loader, la régression entière ci-dessus passe.
Il faut attendre la sortie `DONE` du loader avant de démarrer le diagnostic.

## Simulation et logiciel hôte

- `python3 TESTS/test_gpu_accel.py` : 187 commandes à travers AHB, blitter,
  DMA et arbitre DDR avec accès concurrents et attentes. Pages et gardes
  exactes ; 94 656 écritures DDR, dont 68 961 complètes, 918 577 lectures,
  4 463 123 cycles d'attente AHB. Voir [journal](racer_blitter_simulation.txt).
- ZOOM : sources de 1 à 128 pixels, zoom et réduction non entiers, décalages
  impairs, découpage aux quatre bords, coordonnées signées extrêmes, pas
  nuls ou forgés et descripteurs invalides. La référence utilise des calculs
  entiers indépendants du cache et des machines d'états RTL.
- `python3 tools/render_racer.py --cached --pose N --hardware-log TESTS/racer_uart.txt`
  : tests du modèle sous UBSan, parcours complet de 6 km avec correction de
  direction, accélération, freinage, sortie de route, collision, arrivée et
  reprise. Génération de scènes sur tout le parcours et aux limites de
  direction ; aucun dépassement du tampon de 512 commandes.
- `python3 TESTS/test_racer_controller.py` : véritable Chrome sans interface,
  serveur local simulant la console, départ, touches simultanées,
  relâchement d'une touche sans perdre l'autre, perte de focus et contrôle
  de l'origine HTTP. Pas d'installation npm ; Node 22 et Chrome locaux.

## Compilation conservée

- [console_gpu_racer_800.fs](../bitstreams/console_gpu_racer_800.fs)
- SHA-256 : `114cda69ee14bb6a3a20bdbab4bbbaf9cd0fe2de304e43c6bd998b81b0f94b32`.
- Build `tang/impl/gpu_racer_r2`, 76 fichiers figés dans `sources.json`,
  empreintes vérifiées contre les sources de compilation courantes.
- 110 chemins détaillés valides, slack minimal **+0,139 ns**, TNS nuls.
- Cœur 800 MHz, AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
- SRAM de la carte FTDI `2023112818`, USB `3:12`. Flash non modifiée.
- Firmware : 46 768 octets d'image ITCM ; 27 336 octets de BSS en ILM.

Occupation **de toute la console** après placement/routage :

| Ressource | Total G6 | Capacité | Ajout par rapport à G5 |
|---|---:|---:|---:|
| Logique | 24 263 | 138 240 | +430 |
| Registres | 18 127 | 139 140 | +136 |
| BSRAM | 203 | 340 | +1 |
| DSP physiques | 17 | 298 | +2 |
| Horloges PRIMARY | 8 | 8 | 0 |

Ces totaux comprennent CPU/bridge, USB, DDR et vidéo. Les différences
quantifient le coût de cette intégration ; elles ne sont pas une mesure
isolée de l'ensemble de l'IP vidéo.

Pour reproduire : `python3 tools/build_gpu.py --name NOM_NOUVEAU`, attendre
le résultat positif du timing, charger le bitstream puis attendre la fin
du loader, et lancer `python3 tools/check_gpu_console.py --wait 20`.

[Architecture, protocole et utilisation](../ARCHI/JEU_COURSE.md).
