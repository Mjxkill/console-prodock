# G3 — seize couches en DDR3

Interface : [GPU_G3_REGISTRES.md](../ARCHI/GPU_G3_REGISTRES.md).
Date : 28 septembre 2026. Cible : Tang Mega 138K Pro Dock, cœur AE350 800 MHz.
**Validé en simulation et sur carte**, build `gpu_g3_r9`. Michael confirme
également le rendu du LCD le 28 septembre 2026 (« parfait »).

## Simulation

Le banc `rtl/gpu_layers_tb.sv` teste le compositeur, le lecteur LCD et
l'arbitre DDR avec un CPU concurrent. La mémoire simulée applique une latence
variable et des pauses d'acceptation. Les adresses de départ et les pas de
ligne sont volontairement non alignés.

Chaque pixel RGB est comparé à une référence indépendante, ainsi que
l'empreinte ordonnée de l'image. Les cas couvrent les 16 couches actives,
positions négatives, clipping aux limites source/écran, défilement,
transparence zéro, opacité, priorité inversée, toutes les couches désactivées
et retour au mode framebuffer G1. Une panne DDR de plusieurs trames retarde
un commit : la banque en cours reste protégée jusqu'à la reprise.

Résultat 800×480 dans [gpu_g3_simulation.txt](gpu_g3_simulation.txt) :

- PASS ; 594 688 lectures CPU concurrentes, latence mémoire de 32 à 42 cycles.
- Maximum de 2 328 cycles par ligne pour 16 surfaces complètes, sur 2 556
  cycles DDR disponibles entre lignes. Cette marge dépend du modèle de
  latence simulé ; les mesures sur carte sont rapportées séparément.
- Le compteur de sous-alimentation ne monte que pendant la panne imposée.
- Le banc G1 réduit repasse également : pixels, somme, permutation au retour
  vertical et récupération après panne ; 5 926 lectures CPU.
- Après séparation du calcul des coordonnées source et de l'adresse de
  copie du blitter, `python3 TESTS/test_gpu_accel.py` repasse : 100 commandes,
  trois pages et leurs gardes intégralement exactes, 20 381 écritures DDR
  dont 14 327 blocs complets, 187 388 lectures concurrentes.

```sh
verilator --binary --timing -Wno-fatal --top-module gpu_layers_tb \
  -GW=800 -GH=480 -GVT=533 --Mdir /tmp/console_gpu_layers_full \
  TESTS/rtl/gpu_layers_tb.sv tang/rtl/video/gpu_scanout.v \
  tang/rtl/video/gpu_line_reader.v tang/rtl/board/ddr_gpu_arb.v \
  tang/rtl/board/cdc_word.v
/tmp/console_gpu_layers_full/Vgpu_layers_tb
```

## Démonstration et référence visuelle

La commande `L` prépare 16 surfaces de 800×480, soit 6 144 000 octets utiles.
Chaque surface fournit une bande numérotée 00 à 15 ; le reste est transparent.
Le lecteur lit donc réellement les 16 surfaces complètes pour la première
configuration. Le texte est dessiné par le blitter G2. La palette comporte
trois rampes de 64 couleurs, commune avec la démonstration G2 corrigée.

Trois configurations testent ensuite le déplacement, le défilement et la
permutation de priorité. Le CPU recalcule l'image composée et son empreinte
à partir des surfaces DDR, puis la compare à celle du matériel après commit.
`P` passe à la configuration suivante. Le test hôte conserve G0/G1/G2, effectue
six changements supplémentaires et teste 1 Mio de DDR côté CPU après chacun.

| Configuration | Référence attendue | Empreinte logicielle |
|---|---|---|
| 0 : surfaces à l'origine | [Image](images/gpu_g3_pose0_expected.png) | `d2a52383` |
| 1 : positions et défilement | [Image](images/gpu_g3_pose1_expected.png) | `efdb7ff7` |
| 2 : priorités et déplacements | [Image](images/gpu_g3_pose2_expected.png) | `a43aeec8` |

`tools/render_gpu_layers.py --pose N` génère ces images en exécutant la
préparation C des surfaces et le rasteriseur de texte de référence, puis en
composant les couches en Python. L'option `--hardware-log` compare également
l'empreinte au journal de la carte. Les images représentent les composantes
RGB envoyées au LCD, sans modéliser sa réponse physique.

## Validation matérielle finale

Le [journal complet](gpu_g3_uart.txt) conserve les résultats de
`python3 tools/check_gpu_console.py --wait 20` sur le CDC de la Pro Dock :

- USB : identification G3, écho exact de 5 441 octets.
- G0 : masques, adresses et trois passes de 1 Mio en DDR, zéro erreur.
- G1 : deux pages, quatre permutations et accès CPU concurrents, sommes exactes,
  zéro sous-alimentation LCD.
- G2 : trois dessins de 56 commandes, tous les pixels et gardes exacts ; somme
  `da3c6a80`, zéro erreur de cache/mémoire et zéro sous-alimentation LCD.
- G3 : 16 surfaces complètes, trois configurations, puis six permutations
  atomiques. Empreintes `d2a52383`, `efdb7ff7`, `a43aeec8`, vérifiées par la
  référence CPU et par le rendu Python. Six tests CPU supplémentaires de 1 Mio
  pendant l'affichage : zéro erreur, zéro descripteur invalide, zéro ligne manquante.

Le compteur maximal atteint **2 477 cycles DDR par ligne** avec le trafic CPU,
soit environ 33,03 µs sur 34,09 µs disponibles (2 556 cycles). Il est cumulatif
depuis le reset ; les valeurs affichées pour les scènes suivantes conservent
donc ce maximum. Cette marge ne garantit pas tout autre mélange de trafic DDR.
Le diagnostic termine avec la configuration 0 affichée, numéros 00 à 15.

Les images de référence sont vérifiées contre ce journal :
`python3 tools/render_gpu_layers.py --pose N --hardware-log TESTS/gpu_g3_uart.txt`.
La commande `P` change de configuration ; `L` reconstruit et vérifie la scène.

## Bitstream conservé

- [console_gpu_g3_800.fs](../bitstreams/console_gpu_g3_800.fs), chargé en SRAM
  sur la Pro Dock FTDI `2023112818`, USB `3:12`. La flash n'est pas modifiée.
- SHA-256 : `c772327216538427a8d6fdfd25a8d6a06ff2036512410e8b306ca79fb5903c85`.
- Build isolé : `tang/impl/gpu_g3_r9`, sources figées et empreintes dans
  `sources.json` ; aucune différence avec les sources de compilation courantes.
- Reproduction : `python3 tools/build_gpu.py --name NOM_NOUVEAU`.
- Timing : 110 chemins détaillés positifs, minimum **+0,139 ns** ; les 24 lignes
  TNS setup/hold sont à zéro. Cœur 800 MHz, AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
- Ressources : 19 534 cellules logiques, 14 671 registres, 167/340 BSRAM,
  7/298 DSP, 8/8 horloges PRIMARY.

## Corrections nécessaires à la validation

Le premier routage `gpu_g3_r1` échoue au timing et n'a pas été chargé.
Le calcul de l'empreinte est désormais réparti sur plusieurs cycles ; le
compteur des lectures DDR en cours est enregistré, et le réalignement des
pixels évite un multiplexage inutile. Le second routage ne laisse que le
retour DDR vers les tampons d'affichage en défaut (−0,865 ns). Un étage de
registre sépare désormais le décodage des réponses DDR des validations RAM.
Le troisième routage révèle ensuite un chemin demande vidéo → autorisation
du blitter à −0,658 ns. La validation complète des requêtes est maintenant
enregistrée, séparant le décodage d'état de l'arbitrage. Les simulations
complètes restent positives, au même coût de 2 119 cycles par ligne.
Le quatrième routage ferme les chemins du compositeur, mais révèle la marge
insuffisante du calcul d'adresse des copies G2 (−0,627 ns). Les coordonnées
source sont désormais enregistrées avant leur conversion en adresse, dans
deux étapes déjà existantes, sans cycle supplémentaire par ligne copiée.
Le cinquième routage passe : 110 chemins détaillés, minimum +0,140 ns et
24 lignes TNS à zéro. Il est chargé en SRAM. G0/G1/G2 passent sur carte,
mais les 16 surfaces complètes provoquent 958 lignes manquantes pendant
la première vérification : [journal de l'échec](gpu_g3_r5_underflow.txt).
Le modèle de latence initial était insuffisant pour qualifier ce débit.

Le lecteur est porté de 8 à 16 lectures simultanées pour mieux masquer
la latence DDR, avec un modèle de simulation de 32 à 42 cycles au lieu de
12 à 22. Les compteurs USB incluent maintenant le temps maximal par ligne,
y compris dans les messages d'échec. Les routages r6/r7 ne sont pas chargés :
après correction des chemins GPU, le placement automatique de l'ITCM reste
en défaut (jusqu'à −1,621 ns sur r7). `constr/gpu.cst` reprend le brochage E2
et 135 placements ITCM du projet de référence `la16_usbV5_p24`, avec le même
composant et `ITCM_SIZE=14`. R8 corrige les défauts ITCM, mais expose un chemin
reset → données de la RAM de composition à −1,373 ns. Le port d'écriture est
désormais enregistré ; les registres de données intermédiaires n'utilisent
plus le reset global. R9 passe ensuite le timing et tous les essais matériels
rapportés ci-dessus. Aucun routage en défaut de timing n'a été chargé.
