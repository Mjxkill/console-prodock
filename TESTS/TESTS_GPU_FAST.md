# GPU accéléré — validation

Cette évolution remplace le balayage pixel par pixel des triangles par des
intersections de lignes exactes et ajoute une voie d'aplats DDR3 de 256 bits.
Le rendu original du jeu est rétabli par défaut ; le panorama en cache reste
sélectionnable pour comparaison.

## Régression RTL

Le test de triangles compare chaque pixel 800×480 avec trois tests de
demi-plans indépendants : **255 triangles, 52 036 segments**, avec
contre-pression, orientations inversées, arêtes partagées, coordonnées
signées extrêmes, pentes élevées, découpage et dégénérescences. Le calcul le
plus long prend **2 720 cycles**, attentes du consommateur comprises ; le
coût par ligne ne dépend plus de sa largeur.
[Journal](gpu_fast_triangle_simulation.txt).

Le test complet AHB → blitter → DMA → arbitre DDR compare toutes les pages
et leurs gardes : **541 commandes**. Il couvre également chacun des 32
alignements de départ, onze longueurs de remplissage, les masques partiels,
les attentes DDR et les clients CPU/affichage concurrents.

La même liste de commandes est exécutée contre le RTL figé précédent :

| Mesure de simulation | Ancien RTL, racer r2 | Nouveau RTL |
|---|---:|---:|
| Écritures DDR | 95 449 | 95 449 |
| Écritures DDR complètes | 69 159 | 69 159 |
| Attentes AHB cumulées | 6 099 663 | 1 316 837 |
| Pixels et gardes | Exacts | Exacts |

Les attentes AHB diminuent d'un facteur **4,63**. Ce compteur mesure les
attentes de la file de commandes sous cette charge simulée ; ce n'est pas
un facteur universel de débit GPU ou de bande passante DDR. Les écritures
identiques confirment que les opérations n'ont pas été supprimées.
[Ancien RTL](gpu_fast_baseline_simulation.txt), [nouveau RTL](gpu_fast_blitter_simulation.txt).

```sh
python3 TESTS/test_gpu_accel.py
python3 TESTS/test_gpu_accel.py --rtl-root tang/impl/gpu_racer_r2/source --out /tmp/gpu_baseline_comparison
```

La régression d'affichage vérifie les 16 couches, 64 sprites, priorités,
transparence, positions, défilements, commits atomiques, descripteurs invalides
et reprise après surcharge. Les scènes prévues tiennent en **2 341/2 556 cycles**
par ligne dans ce banc ; la surcharge volontaire à 2 898 cycles est signalée
et récupérée. Le client CPU effectue 1 124 984 lectures.
[Journal](gpu_fast_layers_simulation.txt).

## Identité du rendu original

Le générateur hôte sous UBSan retrouve les quatre empreintes du premier jeu,
avant mise en cache du panorama et réduction des aplats de bordure :

| Scène | Empreinte | Commandes |
|---|---|---:|
| Départ | `05b527ab` | 267 |
| Course | `249a5c44` | 254 |
| Voie opposée | `9f770a5b` | 262 |
| Collision | `b3078f98` | 257 |

```sh
python3 tools/render_racer.py --pose 1 --hardware-log tang/impl/gpu_racer_r1/uart_test.log
```

Les tests du modèle couvrent aussi un parcours complet de 6 km, la conduite,
les collisions et le redémarrage. Le navigateur teste les touches simultanées
et la perte de focus. Une réponse USB numérique malformée ferme désormais
proprement la liaison et remet l'état de connexion en erreur.

## Fermeture du timing

La première compilation `gpu_fast_r1` présente un dépassement de **0,209 ns**
sur le lecteur d'affichage, entre le défilement vertical et l'activation des
masques de pixels. Elle n'est pas chargée sur la carte.

La hauteur source restante est maintenant calculée dans l'état SIZE déjà
présent. Dans COORD, les coordonnées et masques sont chargés sans dépendre
du prédicat de visibilité ; ils sont simplement inutilisés si la couche est
rejetée. Le chemin de contrôle est raccourci sans cycle supplémentaire.
Les fréquences et contraintes sont conservées.

La compilation suivante `gpu_fast_r2` passe les 110 chemins détaillés, avec
une marge minimale de **+0,139 ns** et tous les TNS nuls. Les 76 fichiers
figés dans `sources.json` correspondent aux sources de compilation courantes.

Occupation de **toute la console** après placement/routage :

| Ressource | Avant, racer r2 | GPU accéléré | Variation |
|---|---:|---:|---:|
| Logique | 24 263 | 26 332 / 138 240 | +2 069 |
| Registres | 18 127 | 19 080 / 139 140 | +953 |
| BSRAM | 203 | 203 / 340 | 0 |
| DSP physiques | 17 | 17 / 298 | 0 |
| Horloges PRIMARY | 8 | 8 / 8 | 0 |

Cela représente environ 19,05 % de la logique disponible, soit 1,50 point
de plus. Ces chiffres comprennent aussi USB, CPU/bridge, contrôleur DDR et
affichage ; ils ne sont pas l'occupation isolée de l'IP vidéo.

Le firmware occupe 48 112 octets d'image ITCM, avec 27 344 octets de BSS
en ILM. L'interface du blitter, le zoom et les autres commandes sont conservés.

## Résultats sur la carte

Le [journal complet](gpu_fast_uart.txt) passe G0 à G6 puis le benchmark FAST :
échos USB, DDR CPU, palette, pages, blitter, couches, sprites, 3D, zoom,
conduite USB et reprise. Aucune ligne manquante ni erreur de descripteur.
Les quatre images du rendu original sont comparées pixel par pixel sur le
CPU, avec gardes, puis vérifiées par l'empreinte de lecture LCD.

`K` utilise la même séquence déterministe de 240 images dans chaque mode :

| Mesure | Rendu original, recalcul complet | Panorama en cache |
|---|---:|---:|
| Préparation CPU moyenne | 50 692 cycles / 63,37 µs | 55 601 cycles / 69,50 µs |
| Soumission + dessin GPU moyen | 6 478 503 cycles / **8,10 ms** | 6 958 262 cycles / 8,70 ms |
| Soumission + dessin GPU maximum | 7 832 625 cycles / **9,79 ms** | 8 307 730 cycles / 10,38 ms |
| Image avec attente vblank | 14 514 487 cycles / 18,14 ms | 14 514 497 cycles / 18,14 ms |
| Cadence mesurée sur 240 images | 55,11 images/s | 55,11 images/s |
| Lignes manquantes | 0 | 0 |

La fréquence nominale du panneau reste 55,04 Hz. Les 55,11 images/s calculées
sur cet intervalle fini incluent une première attente de vblank partielle ;
ce n'est pas une augmentation de la fréquence du LCD. Le temps maximal de
dessin original laisse environ **8,38 ms** avant une période LCD complète,
hors préparation CPU. La première version du même rendu donnait environ
27,7 images/s avec l'ancien GPU ; son temps GPU seul n'avait pas été mesuré.

Le mode original est légèrement moins coûteux ici que le panorama en cache :
les aplats et triangles profitent de la voie directe, tandis que COPY conserve
son chemin de transfert précédent. Les résultats décrivent cette séquence
d'objets et de virages, pas une garantie pour toute scène future.

Le benchmark G5 des deux cubes donne aussi 855 746 cycles GPU moyens, soit
1,07 ms, contre environ 7,47 millions de cycles (9,34 ms) dans le bitstream
G5 conservé. La cadence d'affichage reste limitée par le panneau.

## Bitstream conservé

- [console_gpu_fast_800.fs](../bitstreams/console_gpu_fast_800.fs).
- SHA-256 : `6aba70d8cac106e9cfed8ecd517d4c5e60cfdbd89f539bd271e1de5ef041d7ea`.
- Build isolé : `tang/impl/gpu_fast_r2`, sources figées et timing validé.
- Chargé en SRAM sur la Pro Dock FTDI `2023112818`, USB `3:12`.
- Flash non modifiée ; retour possible au [bitstream racer r2](../bitstreams/console_gpu_racer_800.fs).
- Le jeu revient au rendu original après le benchmark ; la manette locale
  utilise le même protocole USB.

Reproduction : construire avec `python3 tools/build_gpu.py --name NOM_NOUVEAU`,
attendre le timing positif, charger puis attendre la fin du loader, et lancer
`python3 tools/check_gpu_console.py --wait 20`. Pour la manette :
`python3 tools/racer_web.py`, puis <http://localhost:8765>.

[Architecture de l'accélération](../ARCHI/GPU_SPANS_DDR256.md).
