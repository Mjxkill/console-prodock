# Validation : perspective et composition RGB565 / 2D

3 octobre 2026. **Simulation, timing et tests sur Pro Dock validés :
`gpu_perspective_r10`.**
[Contrat](../ARCHI/GPU_PERSPECTIVE_COMPOSITION.md).

## Références et non-régression

- `TESTS/test_gpu_accel.py --affine --equiv-blitter-root
  tang/impl/gpu_l1315_r3/source --equiv-dma-delay 0` : 604 commandes,
  pixels et gardes exacts ; blitter identique sur 2 081 517 cycles,
  DMA identique sur 2 081 518 cycles.
- `TESTS/test_gpu_raster_equivalence.py` : moteur RGB565 actuel et snapshot
  `gpu_l1315_r3` côte à côte, mêmes commandes et retours DDR. **2 490 564
  cycles identiques** sur les 359 commandes historiques : requêtes, adresses,
  données, masques, compteurs, busy/done. Pages et gardes exactes. Les vecteurs
  sont conservés dans `gpu_perspective_20261003/legacy_rgb_vectors.tar.gz`.
- `TESTS/test_gpu_raster.py` : 785 commandes, 18 refus attendus,
  toutes les pages couleur/Z/source et leurs gardes exactes. Référence
  Python indépendante par pixels, division entière rationnelle signée,
  alpha, Z, trois modes de texture, Q positif/nul/négatif, extrêmes et
  concurrence CPU/affichage avec attentes DDR.
- `TESTS/test_gpu_perspective.py` : 2 196 couples rationnels U/V,
  comparaison à la division Python ; reset pendant une division, aucun
  résultat ancien rejoué ; latence maximale observée 28 cycles après séparation de la capture.
- `TESTS/test_gpu_raster_scene.py --perspective` : quatre scènes firmware
  contre RTL : 141, 141, 141 et 151 commandes avec chargement de texture.
- `TESTS/test_gpu_raster_geometry.py --perspective` : 512 phases et fermeture
  de boucle, 22 905 121 pixels intérieurs aux silhouettes vérifiés, aucune
  face manquante ; UBSan, commandes périodiques et rotation continue.
- `gpu_scanout_tb`, RGB direct : dimensions, chaque pixel, palette,
  permutation au vblank, empreinte, concurrence CPU et reprise après manque
  de données validés.
- `gpu_layers_tb`, 800 × 480, sprites et RGB565 superposé : chaque pixel,
  16 couches, alignements, fenêtres, défilement, priorités, sprites, index zéro
  opaque/transparence par clé, permutations atomiques, surcharge volontaire
  signalée, blocage DDR et reprise puis retour au framebuffer indexé.
- `TESTS/test_gpu_layers_equivalence.py` : **77 670 746 cycles identiques**
  entre le lecteur de r7 et celui de r10, dans le banc 800 × 480 complet :
  commandes DDR, adresses de descripteurs et de sprites, blocs valides avec
  couverture, compteurs et fins de lignes. La référence ouverte est conservée
  dans `gpu_perspective_20261003/reader_reference.tar.gz`.

La simulation complète avec `-GW=800 -GH=480 -GVT=533 -GSPRITES=1
-GTILES=5 -GOVERLAY=1` passe aussi cinq couches de tuiles avec surfaces
et sprites, puis quatre couches de tuiles avec cinq surfaces. La scène
16 surfaces + fond RGB565 mesure **2 522 / 2 556 cycles** par ligne dans
ce modèle DDR : la marge de cette charge extrême est donc de 34 cycles.
La surcharge volontaire 16 surfaces + 64 sprites est correctement signalée.
Ces nombres ne sont pas des mesures de la DDR physique.

Reproduire la comparaison historique (l'archive contient aussi le moteur
de référence ouvert, dont l'empreinte est consignée dans le résultat) :

```sh
mkdir -p /tmp/console_rgb_vectors
tar -xzf TESTS/gpu_perspective_20261003/legacy_rgb_vectors.tar.gz -C /tmp/console_rgb_vectors
python3 TESTS/test_gpu_raster_equivalence.py \
  --reference-root /tmp/console_rgb_vectors/reference \
  --vectors /tmp/console_rgb_vectors --out /tmp/console_rgb_equivalence \
  --commands 359 --raster-bad 13
```

## Empreintes attendues de la démonstration commune

| Angle | Ordre inversé | Somme fond RGB565 | Somme sortie LCD RGB666 |
|---:|---:|---|---|
| 0 | 0 | `6121d64d` | `58ab9465` |
| 37 | 1 | `ff0e3a83` | `5d78b787` |
| 74 | 0 | `c54c5c04` | `4c1385a9` |
| 111 | 1 | `fa3fafee` | `5cc829f0` |

Production : `tools/render_gpu_raster.py --overlay`, avec `--angle` et
`--reverse`. La référence LCD peint séparément les zones des couches,
le sprite et le ruban de tuiles. La simulation de composition utilise
également ses propres scènes et son propre peintre par pixels.

## Corrections pendant l'intégration

1. Le lecteur RGB565 initial attendait chaque réponse avant la requête
   suivante. Son coût ajouté à 16 surfaces dépassait le budget d'une ligne.
   Le mode composé emploie maintenant des requêtes en vol, bornées par
   l'arbitre DDR. Le mode direct historique conserve son séquencement.
2. La première invocation de Gowin dans le sandbox n'a pas passé la licence
   matérielle. Aucun bitstream n'en est issu.
3. La synthèse du build `gpu_perspective_r2` ne produit plus huit cellules
   `gowin_add_SDPB_composed_composed_*` visées par d'anciennes contraintes
   de placement. Ces huit placements ont été retirés, les autres restent
   conservés. Aucun assouplissement du SDC ni modification d'IP fermée.
4. Le premier appel du banc d'équivalence avait conservé le délai DMA
   historique d'un cycle. Le snapshot r3 l'inclut déjà : l'exécution avec
   `--equiv-dma-delay 0` valide l'identité cycle par cycle.

5. `gpu_perspective_r3` a échoué au timing : pire marge **−5,610 ns**,
   chemin interne du diviseur, 441 terminaisons en violation setup. Ce
   bitstream n'a pas été chargé. Les comparaisons `>=` et soustractions
   distinctes créaient quatre chaînes de retenue successives. La soustraction
   fournit désormais directement son emprunt et son reste, sans comparaison
   redondante. Les 2 196 couples rationnels et les 785 commandes repassent,
   avec exactement les mêmes cycles et transactions que la version simulée
   précédente. Le SDC reste inchangé.

6. `gpu_perspective_r4` réduit le pire retard à **−1,205 ns**, sans atteindre
   la fermeture : deux soustractions en série, capture puis valeur absolue
   des coordonnées, et activation de tampons depuis un décodage partagé.
   R5 effectue Q/2Q/3Q en parallèle, capture les coordonnées avant leur valeur
   absolue et prépare les activations des tampons un cycle en avance.
   Les résultats couleur/Z restent exacts sur les 785 commandes ; la division
   prend un cycle supplémentaire, masqué en grande partie par l'anticipation.

7. `gpu_perspective_r5` échoue à **−2,102 ns** sur le retour de lecture DDR :
   décodage combinatoire des tags de l'arbitre puis activation des tampons
   couleur/Z. Les autres domaines passent. R6 capture données et destination
   du retour avant l'activation des tampons ; le cycle de préparation déjà
   présent laisse les données se stabiliser sans retarder les commandes.
   Les 785 commandes étendues, les quatre scènes et les 359 commandes
   historiques repassent. Transactions, compteurs et cycles historiques
   restent identiques. Aucun de ces builds en échec timing n'est chargé.

8. `gpu_perspective_r6` supprime ce chemin critique couleur/Z mais révèle
   la capture de texture commandée par le même retour combinatoire :
   **−3,043 ns**, 118 terminaisons GPU en violation. Le domaine sclk USB
   présente aussi une violation de −0,056 ns dans ce placement. R7 fait
   suivre au tampon de texture le bus de retour jusqu'à son acceptation,
   puis le fige pendant la copie. Seules les données acceptées sont utilisées ;
   aucun cycle de copie n'est ajouté. Les IP et le SDC restent inchangés.
   Les 785 commandes, les quatre scènes et la comparaison cycle par cycle
   avec l'ancien moteur passent après cette modification.

9. `gpu_perspective_r7` réduit les violations à 13 terminaisons GPU, pire
   marge **−0,753 ns** ; tous les autres domaines passent. R8 supprime le
   dernier pas impair du diviseur en ajoutant un zéro de tête : 25 pas
   de deux bits, même latence. Une sélection exclusive des restes remplace
   la chaîne de multiplexeurs prioritaires. La profondeur précédente est
   lue pendant PIX_SAMPLE avant la comparaison ; l'alignement des couches
   est réparti en 2 puis 3 bits sur les registres existants. Les 2 196 couples,
   785 commandes, quatre scènes et 2 490 564 cycles historiques repassent.
   La composition complète 800 × 480 conserve 2 508 cycles au dernier cas
   et 1 729 862 lectures CPU, avec tous les pixels et gardes attendus.

10. `gpu_perspective_r8` laisse neuf terminaisons en violation : cinq dans
    le domaine GPU, deux AHB et deux dans le PHY USB fermé. Pire marge
    **−1,084 ns**, sur le retour `ready` de l'arbitre vers l'état du raster.
    Les chemins arithmétiques et d'alignement corrigés en r8 passent.
    R9 encode explicitement le raster avec un bit par état, pré-décode les
    adresses de lecture AHB du GPU et prépare la condition de blocage des
    écritures du compositeur pendant la phase d'adresse existante.
    La synthèse conserve cet encodage du raster. Les 604 commandes indexées,
    785 commandes étendues, quatre scènes et les équivalences de
    **2 490 564 cycles** du raster et **77 670 746 cycles** du lecteur
    repassent. Les sources USB fermées et le SDC restent inchangés.

11. `gpu_perspective_r9` ferme le timing AHB mais échoue encore à
    **−2,326 ns** sur la sélection de la profondeur précédente : dix
    terminaisons GPU et une USB (−0,297 ns). R10 répartit le multiplexage
    des 16 pixels sur SAMPLE/TEST ; l'alpha reçoit le fond avant BLEND,
    sans cycle ajouté. Les activations du registre d'écriture DDR sont
    isolées du décodage des commandes sans rapport. Les trois lecteurs
    d'affichage ne demandent jamais simultanément la DDR : leur OU remplace
    le multiplexage d'activation ; cette exclusivité et l'identité avec
    l'ancien multiplexeur sont vérifiées à chaque cycle du banc.
    L'arbitre compare les pointeurs avant l'acceptation tardive, puis met
    à jour son état plein selon push/pop. **77 670 748 cycles de l'arbitre**
    sont identiques à r7, et **2 490 566** à r3 dans le banc raster, avec
    pointeurs, plein et toutes les sorties comparés. Pixels, transactions
    et budgets de ligne restent inchangés.
    Enfin, une contrainte CST rapproche la bascule PHY `bit_align_wr_act_s1`
    de son dernier étage de commande (fil de 0,759 ns dans r9), sans
    modifier la logique USB fermée ni ses contraintes de timing. Son effet
    doit être vérifié dans le rapport du nouveau routage.

## Validation physique

Build `gpu_perspective_r10`, Gowin 1.9.12, Pro Dock FPG676 via ax15.
SHA-256 du bitstream :
`3e528e6baf0208ed3efe5c23629d7aae65a6cc75485064af075741029072de4b`.
Les 108 sources figées sont vérifiées avant programmation. Archive SRAM :
`bitstreams/console_gpu_perspective_800.fs`, avec manifeste et somme.

### Timing et ressources

Aucune violation setup/hold, TNS nul dans tous les domaines. Marge minimale
**+0,140 ns** (USB), GPU **+0,789 ns**, AHB **+0,977 ns**. La bascule USB
replacée présente maintenant +0,466 ns. Le SDC reste identique :
`c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.
Contrôle de synthèse du compositeur : aucun registre absorbé dans un DSP
avec des horloges incompatibles. Mesure SDF des pointeurs Gray : 12 chemins
du pont DDR, maximum 1,567 ns ; 18 chemins de l'observateur USB, maximum
1,305 ns. Ce contrôle de délais n'est pas une preuve analogique de MTBF.

Ressources de **l'ensemble FPGA**, comprenant CPU, DDR et USB :

| Ressource | Utilisée / disponible | Occupation |
|---|---:|---:|
| Logique LUT/ALU | 46 206 / 138 240 | 33,42 % |
| Registres | 34 231 / 139 140 | 24,60 % |
| CLS | 36 895 / 69 120 | 53,38 % |
| BSRAM | 239 / 340 | 70,29 % |
| DSP | 53 / 298 | 17,79 % |
| Horloges PRIMARY | 8 / 8 | 100 % |

Firmware : 53 192 octets texte + 1 360 données = **54 552 octets ITCM**,
BSS 29 128 octets. `-Os` conserve toutes les démonstrations dans l'ITCM ;
leurs performances ont été revérifiées sur carte.

### Rechargements, USB et vidéo

Deux chargements **SRAM**, FTDI 2023112818, câble USB maintenu branché.
Console 359f:2011 / 11252024 : nouvelles adresses 3:26 puis 3:27,
configuration complète et vitesse **480 Mbit/s** à chaque fois. Deux séries
de 20 essais, **217 640 octets binaires exacts**. Aucun changement de flash.

Suite complète passée : DDR partagée, framebuffer, palette, primitives,
texte, 16 couches, 64 sprites, triangles, tuiles, course, variantes FAST,
transformations affines, RGB565/alpha/Z historique puis perspective et
composition. Les quatre sommes RGB565 et les quatre sommes LCD du tableau
ci-dessus correspondent exactement. Les références firmware vérifient
les surfaces couleur/profondeur et leurs gardes.

La scène avancée conserve **zéro ligne manquante**, y compris pendant les
accès CPU à la DDR. Cinq fenêtres de 120 images couvrent la rotation et
son rebouclage : **54,84–55,18 images/s**, dessin maximal **10 305 033 cycles
CPU = 12,881 ms**. Les quatre poses mesurent **2 019 / 2 556 cycles** par ligne
pour composition et fond réunis, hors ligne zéro. Le maximum d'intervalle
complet observé est de 25,926 ms : la moyenne à la cadence LCD ne signifie
pas que chaque intervalle logiciel est identique.

Pause par USB, empreinte stable pendant que l'écran continue à balayer,
puis retour au mode indexé et aux anciennes empreintes : passé. L'animation
avancée `e` est relancée à la fin. Confirmation visuelle utilisateur de
cette nouvelle scène encore non reçue ; les résultats ci-dessus sont les
vérifications automatiques sur matériel.

Preuves : `gpu_perspective_20261003/board_r10/result.json` et `gpu.log`,
`r10.tr`, `r10.rpt.txt`, `r10_resources.json`, `scanout_synthesis_r10.json`,
`ddr_gray.json`, `usb_gray.json`, `r10_firmware.log`. Sources exactes dans
`r10_sources.tar.gz` ; outils de validation figés avec les résultats carte.
