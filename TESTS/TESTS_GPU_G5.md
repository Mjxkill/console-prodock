# G5 — triangles et démonstration 3D

Date : 28 septembre 2026. Tang Mega 138K Pro Dock, AE350 800 MHz.
Interface : [GPU_G5_TRIANGLES_3D.md](../ARCHI/GPU_G5_TRIANGLES_3D.md).

**Validé en simulation et sur carte**, build `gpu_g5_r3`.
Michael confirme le 28 septembre 2026 que les deux cubes tournent
correctement, avec le texte stable et sans déchirure.

## Rasteriseur isolé

[Journal](gpu_g5_triangle_simulation.txt) : 101 triangles, chaque pixel
comparé à une référence indépendante sur 800×480 ; 28 076 segments et
8 330 pauses d'acceptation. Sommets dans les deux sens, arêtes communes,
triangles plats/dégénérés, clipping, sommets signés extrêmes et triangles
très fins. Les segments restent stables pendant les pauses, ne se chevauchent
pas et ne sortent jamais de la surface. Une limite de cycles détecte tout
balayage excessif hors écran.

```sh
verilator --binary --timing -Wno-fatal --top-module gpu_triangle_tb \
  --Mdir /tmp/console_gpu_triangle TESTS/rtl/gpu_triangle_tb.sv \
  tang/rtl/video/gpu_triangle.v
/tmp/console_gpu_triangle/Vgpu_triangle_tb
```

## Chemin AHB → dessin → DDR

`python3 TESTS/test_gpu_accel.py` conserve les primitives G2 et ajoute
70 triangles, avec masques d'octets, alignements, ordres des sommets,
clipping et page 15. Le contrôleur simulé impose des pauses et mélange
les accès CPU, affichage et dessin.

[Journal](gpu_g5_blitter_simulation.txt) : **170 commandes**, trois pages
entières et leurs gardes exactes ; 91 556 écritures dont 66 834 rafales
complètes ; 878 868 lectures, dont 561 989 CPU et 315 889 affichage.
La commande inconnue termine et incrémente BAD ; aucun mot perdu.

Après simplification du contrôle d'adresse DDR, le banc complet G3/G4
800×480 repasse : [journal](gpu_g5_layers_simulation.txt), 1 124 984 lectures
CPU concurrentes, 2 341 cycles par ligne et 5 889 cycles de chargement du
cache. La surcharge volontaire et la récupération après panne DDR conservent
leur comportement ; aucun cycle supplémentaire n'est ajouté au lecteur.

## Préparation CPU et références visuelles

`tools/render_gpu_3d.py --pose N` compile la préparation C avec détection
des comportements indéfinis. Il parcourt 512 angles dans les modes normal
et proche, contrôle la capacité des listes, puis teste explicitement le
clipping d'un polygone traversant le plan proche ou entièrement rejeté.
Les primitives sont rasterisées séparément en Python ; le texte vient de
la référence logicielle G2. Le compositeur ajoute la couche transparente.

| Pose | Description | Empreinte attendue |
|---|---|---|
| [0](images/gpu_g5_pose0_expected.png) | Deux cubes, fil de fer et faces pleines | `55a13c71` |
| [1](images/gpu_g5_pose1_expected.png) | Rotation | `e4d10d27` |
| [2](images/gpu_g5_pose2_expected.png) | Autre rotation | `5ac3f7a1` |
| [3](images/gpu_g5_pose3_expected.png) | Cube proche, deux faces découpées par le plan proche | `9a9da882` |

Les poses comportent respectivement 6, 4, 4 et 3 triangles pleins.
La couleur uniforme est choisie par face ; le découpage peut changer le
nombre de triangles. `--hardware-log` compare les empreintes avec la carte.

Le test USB conserve G0..G4, puis teste les quatre poses G5, leurs pixels
et gardes, quatre permutations, les accès CPU à 1 Mio de DDR, 120 images
animées, les mesures de temps et la pause. Il relance ensuite l'animation
pour la vérification visuelle.

## Validation matérielle finale

Le [journal USB complet](gpu_g5_uart.txt) conserve tous les essais G0..G5 :

- USB : identité G5, cœur 800 MHz, écho exact de 5 441 octets.
- G0 : masques, adresses et trois passes de 1 Mio, zéro erreur DDR.
- G1 : pages et permutations, sommes exactes, accès CPU concurrents.
- G2 : trois dessins de 56 commandes, pixels et gardes exacts, somme `da3c6a80`.
- G3/G4 : toutes les scènes précédentes, six permutations par jalon et accès
  DDR CPU concurrents ; empreintes exactes, aucun descripteur invalide,
  aucune ligne manquante.
- G5 : quatre poses et quatre changements supplémentaires, pixels et gardes
  comparés par le CPU. Les quatre empreintes correspondent également au rendu
  Python. La pose proche découpe deux faces et produit trois triangles pleins.
- Animation : 120 images chronométrées, contrôle USB accessible, pause
  conservant l'empreinte pendant que le compteur LCD continue d'avancer,
  puis reprise. Aucune ligne manquante sur l'ensemble des essais.

Mesures de la boucle d'animation, MCYCLE à 800 MHz :

| Mesure | Moyenne | Maximum |
|---|---:|---:|
| Préparation CPU (rotations, clipping, projection, tri, commandes) | 11 524 cycles = 14,41 µs | 12 521 cycles = 15,65 µs |
| Soumission et attente du dessin GPU | 7 470 743 cycles = 9,34 ms | 7 666 583 cycles = 9,58 ms |
| Image complète, attente du retour vertical comprise | 14 569 128 cycles = 18,21 ms | 17 684 186 cycles = 22,11 ms |

Cadence mesurée : **54,91 images/s**, proche des 55,04 images/s calculées
pour le timing LCD conservé (35 MHz / 1 193 / 533). Le temps GPU comprend
les envois AHB et l'attente de fin ; ce n'est pas un compteur interne du
rasteriseur. Les comparaisons CPU des pixels et les commandes USB entre
images sont exclues des temps de la boucle. Ce résultat qualifie les deux
cubes de cette démonstration, pas une scène arbitraire.

Le compteur de composition atteint 2 472 cycles pendant la régression
G3/G4, pour 2 556 disponibles ; le cache de sprites atteint 6 525 cycles.
Ces compteurs sont cumulatifs et ne constituent pas une mesure propre à G5.
La 3D utilise deux couches, avec les sprites désactivés, et ne présente
aucune sous-alimentation pendant le dessin de la page arrière.

## Bitstream conservé

- [console_gpu_g5_800.fs](../bitstreams/console_gpu_g5_800.fs), chargé en SRAM
  sur la Pro Dock FTDI `2023112818`, USB `3:12`. Flash inchangée.
- SHA-256 : `871afc00334b9098c65ce63edf9ed53a5f1cab226acf695ef081285cc9ba2577`.
- Build isolé : `tang/impl/gpu_g5_r3`, 74 fichiers figés et empreintes dans
  `sources.json`, sans différence avec les sources courantes de compilation.
- Reproduction : `python3 tools/build_gpu.py --name NOM_NOUVEAU`.
- Timing : 110 chemins détaillés positifs, minimum **+0,140 ns** ; 24 lignes
  TNS setup/hold à zéro. Cœur 800 MHz, AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
- Ressources : 23 833 cellules logiques, 17 991 registres, 202/340 BSRAM,
  15/298 DSP, 8/8 horloges PRIMARY.
- Firmware : code et données initialisées dans une image de 36 272 octets,
  sous la limite ITCM de 64 Kio ; données modifiables en ILM, pile en DLM.

## Ajustements de timing

`gpu_g5_r1` valide le nouveau rasteriseur mais expose deux chemins existants :
adresse DDR → activation du lecteur (−0,563 ns) et retour HREADY AHB
(−0,328 ns). Le contrôle de dépassement DDR tire maintenant parti du fait
qu'une ligne découpée fait au plus 1 024 octets : seule l'addition dans le
dernier Kio doit être vérifiée, sans addition/comparaison sur 33 bits.
Le port de commandes AHB est décodé pendant la phase d'adresse, avant HREADY.
Les fréquences et contraintes temporelles restent identiques.

La seconde compilation inclut aussi une période d'animation de 512 pas :
la rotation lente peut ainsi terminer son tour avant le rebouclage.

`gpu_g5_r2` ferme les chemins du lecteur mais conserve un chemin reset de
FIFO → HREADY (−1,355 ns). Le FIFO expose désormais son bit `full` enregistré
en plus de son signal `ready` habituel. Seul le port AHB de commandes utilise
ce bit pour l'attente et l'écriture ; le maître et la FIFO partagent le reset.
Le bloc conserve la priorité du reset et les autres clients gardent leur
signal `ready` bloqué pendant le reset. Le compteur de pertes reste contrôlé
par la régression de saturation de la FIFO.

`gpu_g5_r3` passe le timing et tous les essais sur carte ci-dessus. C'est
le premier bitstream G5 chargé ; aucun routage en défaut n'a été chargé.
