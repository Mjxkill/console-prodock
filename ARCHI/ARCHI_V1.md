# ARCHI V1 — Console de jeux Tang Mega 138K Pro Dock (proposition, 2026-09-25, À VALIDER)

> **Document historique, remplacé le 27 septembre 2026 par
> [ARCHI_V2_CONSOLE_JEUX.md](ARCHI_V2_CONSOLE_JEUX.md).** Michael précise :
> console de jeux, LCD 800×480, DDR3 uniquement, **16 couches graphiques
> superposables**, sprites, texte, accélérations et première 3D. Les entrées
> servent aux boutons/ADS1115/manettes éventuelles, les sorties aux LED et
> périphériques simples. Les fonctions d'acquisition rapide ci-dessous
> ne font plus partie du projet.

Demande de Michael (25/09) : une console de jeux originale sur la Tang Mega 138K **Pro** Dock
(FPGA GW5AST-LV138FPG676AC1/I0, boîtier 676 billes), écran LCD **480×272 RGB**, langage de
programmation **simple**, carte vidéo performante, DDR3 + cœur RISC-V **AE350**, génération /
acquisition de signaux sur le connecteur externe, 2 × ADS1115 en I2C, avec « pages vidéo »,
« merge » et police de caractères. Socle repris du projet `../logic_wifi_analyser`.

Réponses de Michael ce jour (arbitrages) :
- Carte = **Pro Dock 676** (dépôt d'exemples local `~/gowin/ref/TangMega-138KPro-example`, device
  confirmé dans `ae350_customized_demo.gprj` : `GW5AST-LV138FPG676AC1/I0`).
- Écran = **480×272** (exemple Sipeed `rgb_screen/480_272_screen`, RGB 6-6-6 ou 5-6-5 à lire du cst).
- Langage = **langage maison**, grammaire à définir dans ce document.
- Analogique = **numérique 10 MHz sur le connecteur + ADS1115 pour les mesures lentes** ;
  l'ADS1115 est borné à 860 éch/s (datasheet ADS1115 § Electrical Characteristics), le 10 MHz
  analogique direct n'existe pas avec ces composants. Tout ADC rapide externe est hors périmètre V1.

Règles héritées de `logic_wifi_analyser/ARCHI/ARCHI_V4_PLATEFORME.md` : une modification à la fois,
tout mesuré et consigné dans `TESTS/`, aucun fallback silencieux, modules < 1000 lignes à API
propre, fichiers `.cst`/`.sdc`/`.tcl` par variante, bitstream accepté seulement après essais carte.

## 1. Faits posés en base (vérifiés ce jour)

- **Socle existant réutilisable** (`logic_wifi_analyser/tang/rtl/`) :
  - `board/ae350_soc.v` + `riscv_ae350_soc_ext/` : SoC AE350 complet avec contrôleur DDR3
    (`gwmc_param.v`, `DEFAULT_DDR3_SETTINGS`), AHB/APB, ITCM.
  - `board/ddr_subsys.v`, `ddr_writer.v`, `ddr_reader.v`, `ddr_arb.v`, `ddr_dcfifo.v`,
    `ddr_ui_adapt.v`, PLL DDR (`gowin_pll_ddr3*`) : anneau DDR3 éprouvé (E1/E2 validés en V3/V4).
  - `board/ext_regs.v` : banc de registres du cœur (interface preg).
  - `periph/i2c_master.v` + `i2c_seq.v` : maître I2C et séquenceur ADS1115/MCP4728 (V4 § 9.2/9.4).
  - `periph/gen_out8.v` : 8 sorties PWM/motifs, pas jusqu'à 10 ns (100 MHz), motifs 1 Kio par voie.
  - `rtl/sampler.v`, `change_detect.v`, `raw_fifo.v` : acquisition numérique 16 voies à 100 MHz.
  - `rtl/uart_tx.v`/`uart_rx.v` : cadencement 115200 (utile derrière le CDC-ACM) ; `usb3/*`
    **non repris en V1** (pas de SerDis USB 3 sur le Pro Dock).
- **Exemples Sipeed Pro Dock** (`~/gowin/ref/TangMega-138KPro-example/`) : `pro_ddr_test` (DDR3 +
  UART, test 16 Mo, réponse `57 52 FF FF FF`), `rgb_screen/480_272_screen` (timing + PLL + `.cst`
  du panneau), `ae350_customized_demo` (AE350 + DDR3 sur ce brochage), `audio` (DAC embarqué),
  `dvp_rgb` (caméra OV5640 → LCD), `pcie_dma_demo`, lecteur SD.
- **Différence de boîtier** : le Pro Dock est en FPG676 ≠ PG484 du Console — **tout brochage du
  projet analyseur est invalide ici** ; les `.cst` partent des exemples Sipeed Pro.
- **ADS1115 × 2** : 16 bits, mux 4 canaux chacun, ≤ 860 éch/s, I2C (0x48/0x49) — mesures lentes
  uniquement. Sur le connecteur externe : génération ET acquisition numérique 10 MHz tenue
  (clk100 / prescaler 10, mêmes mécanismes que `gen_out8` mode motif et le `sampler`).

## 2. Ce que la console fait / ne fait pas (périmètre V1)

**Fait :**
- Écran LCD 480×272, carte vidéo : pages vidéo en DDR3, sprites « blob », blending (merge),
  texte avec police bitmap, palette.
- Cœur AE350 qui exécute le **langage maison** (interpréteur C compilé pour le AE350, ou
  interpréteur matériel — voir § 5, décision à trancher).
- Connecteur externe : génération de signaux numériques (jusqu'à 10 MHz) et acquisition
  numérique 16 voies à 100 MHz (héritée du sampler), ADS1115 × 2 en I2C pour le lent.
- Sorties audio via le DAC embarqué de la carte (option V1.x, non bloquant).

**Ne fait pas (V1) :**
- Pas de lien USB 3 (le Pro Dock n'en a pas nativement ; le CH569 HSPI du Dock non-Pro est une
  autre architecture). Le programme se charge par **USB CDC sur le port SOFT-USB** (voir § 3)
  ou depuis la flash.
- Pas de PCIe, pas de SFP+, pas de caméra DVP (prévu V2 si demandé).
- Pas d'ADC analogique rapide (voir arbitrages).

Décision Michael (25/09) : **pas de BL616** — le lien debug/chargement est le **soft USB** du
Pro Dock (`usb2_soft` de Sipeed : PHY USB2 soft sur 9 broches + réseau RC, sans puce, CDC-ACM
115200 plug and play, jusqu'à 16 endpoints, ~40 Mo/s HS). Modules repris de
`TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src` (brochage `usb_ref.cst` exact pour
ce port).

## 3. Architecture : découpage en modules

Un top `console_top`. Chaque module = un fichier Verilog < 1000 lignes, API propre, entrées et
sorties registrées (règle V4 § 5). Sources des modules existants : réutiliser, pas réécrire.

| Module | Rôle | Origine | Horloge |
|---|---|---|---|
| `board/ae350_soc` (+ `ext_regs`) | cœur RISC-V : exécute l'interpréteur, pilote tout via preg | logic_wifi_analyser (adapté FPG676) | ahb 80 MHz |
| `board/ddr_subsys` | anneau DDR3 : écriture des pages, lecture vidéo, accès CPU | idem | 75 MHz wr + ui |
| `video/video_pll` | pixel clock 480×272 (~9-12 MHz selon le panneau, à lire du timing Sipeed) | exemple rgb_screen | pixel |
| `video/lcd_timing` | générateur de balayage RGB 480×272 (DE, H/V sync) | exemple Sipeed 480×272 | pixel |
| **`video/vga_pages`** | **NOUVEAU** : N pages vidéo en DDR3 (8 bpp indexé), bascule de page visible, copie de page, remplissage | à faire | pixel + wr |
| **`video/gpu_sprites`** | **NOUVEAU** : **64 sprites hardware**, tailles 8/16/32 px, bitmap en BSRAM (24 Kio), priorité par index, transparence 0, flip H/V, clipping | à faire | pixel |
| **`video/gpu_raster`** | **NOUVEAU** : moteur de dessin à commandes sur page DDR3 : ligne (Bresenham), cercle (point médian), rectangle, triangle **+ remplissage hardware** et **remplissage dégradé 0°/45°/90°** (interpolation 2 couleurs) | à faire | clk100 + wr |
| **`video/gpu_3d`** | **NOUVEAU** : 3D wireframe/flat : matrice 4×4 Q16.16, transform+projection de sommets (division itérative), arêtes tracées par `gpu_raster`, triangles remplis par `gpu_raster` | à faire | clk100 |
| **`video/font_rom`** | **NOUVEAU** : police bitmap (8×8 et 8×16) en BSRAM, rendu texte sur page | à faire | pixel |
| `video/palette` | LUT couleur 256 → RGB888 (BSRAM) | à faire | pixel |
| `periph/i2c_seq` | ADS1115 × 2 (adresses 0x48, 0x49), voies virtuelles mesures | logic_wifi_analyser (adapté 2 adresses) | clk100 |
| `periph/gen_out8` | génération sur connecteur (PWM/motifs ≤ 10-100 MHz) | logic_wifi_analyser | clk100 |
| `sampler` + `raw_fifo` | acquisition numérique 16 voies 100 MHz → DDR3 ou FIFO hôte | logic_wifi_analyser | clk100 |
| `console_regs` | registres vidéo/IO exposés au CPU : pages, sprites, palette, E/S, ADC | à faire (mimique ext_regs) | ahb/clk100 |
| `lang/interp.c` | interpréteur du langage maison, C bare-metal sur AE350 | à faire | CPU |
| `usb2_soft` (PHY + CDC-ACM) | lien debug/chargement : console série virtuelle sur le port SOFT-USB, **pas de BL616** (décision 25/09) | exemple Sipeed `usb2_soft` (adapté) | softphy 60 MHz + clk100 |

Découpage GPU (le point technique) :
- **Pages** : mémoire DDR3 vue en pages fixes (ex. 480×272 × 8 bits = 130 560 octets ≈ 128 Kio par
  page ; 1 Go DDR3 = jusqu'à 8000 pages, on borne le nombre à un registre). La page *visible* est
  lue par la vidéo en continu (débit : 272 lignes × 480 px × 60 Hz ≈ 7,8 Mo/s — très en dessous du
  débit DDR3 32 bits ~600 Mo/s). Les pages *hors écran* sont le champ des opérations de dessin.
- **Merge** : deux pages (base + overlay) fusionnées au vol pendant le balayage : priorité par
  valeur (0 = transparent) et/ou alpha 4 bits par pixel d'overlay. L'arbitre DDR lit la base, un
  petit FIFO absorbe le jitter, l'overlay arrive par le lecteur 2.
- **Sprites (64, hardware)** : 64 descripteurs en registres (x, y, tu, taille, flip, visible),
  bitmaps 8/16/32 px en BSRAM — budget 24 Kio (64 × 32×32 octets = 64 Ko max, borné : par défaut
  24 sprites de 32×32 ou 96 de 16×16, config par registre). Composition pendant le balayage :
  par ligne active, liste des sprites intersectés (tri par le CPU à l'écriture de y), priorité
  = index le plus bas gagne, couleur 0 = transparent. 64 sprites × 32 px = 2048 pixels par ligne
  à tester : 480 pixels affichés → sur-remplissage possible ; règle : au-delà, les sprites de
  priorité haute sont sautés (débordement signalé dans un registre de statut, jamais silencieux).
- **Raster 2D à commandes** (l'acceleration demandée) : le CPU pousse des commandes
  {opcode, page, params} dans une FIFO ; le moteur écrit dans la page via le writer DDR :
  - ligne (Bresenham hardware), cercle (point médian), rectangle plein/crénelé, triangle
    (rastérisation par demi-bords) ;
  - remplissage de toutes ces formes, en couleur pleine ou **dégradé** : interpolation entre
    c1 et c2 sur le grand axe de la forme — direction 0° (horizontal), 45° (diagonale :
    t ∝ (x−x_min)+(y−y_min), axe dominant), 90° (vertical) ; en 8 bpp le dégradé interpole
    l'**index** dans une rampe palette 16 entrées (pas de true-color : limité 8 bpp, assumé) ;
  - débit : 1 pixel par cycle à clk100 hors conflits DDR = 100 Mpx/s → écran plein en 1,3 ms.
- **3D (léger, wireframe + flat)** : 32 sommets × matrice 4×4 en virgule fixe Q16.16 (multipliers
  DSP 18×18 du GW5AST, 298 dispo), projection perspective avec division itérative (non
  restaurée, ~32 cycles), arêtes envoyées au moteur ligne, faces → triangles remplis. Pas de
  Z-buffer en V1 (painter's algorithm par le CPU) — assumé, documenté.
- **Police** : 8×8 (ASCII) en BSRAM (1 Kio), extension 8×8 accentués FR au choix (registre).

## 4. Plan d'horloges (budget : 8 arbres principaux, 12 PLL, GW5AST)

| Horloge | Usage | Arbre |
|---|---|---|
| 50 MHz pin | entrée PLL DDR3 + init | 1 |
| clk100 | sampler, I2C, gen_out8, FIFO, regs | 1 |
| ahb 80 MHz | AE350 | 1 |
| wr_clk 75 MHz | DDR UI | 1 |
| pixel ~9-12 MHz | LCD 480×272 | 1 |
| softphy 60 MHz | PHY USB2 soft (ut = 4×15 MHz, horloge dérivée du cristal) | 1 |
| (réservé) | extension (audio, HDMI) | 2 restants |

Aucun SerDes en V1 (pas d'USB 3, pas de PCIe) : le budget est confortable, contrairement au
C-USB de la V4 (9/8). Ce point est un gain majeur de partir sur le Pro Dock sans USB 3.

## 5. Langage maison — proposition de grammaire (à trancher)

Interpréteur en C bare-metal (toolchain Andes déjà en place : `~/ae350/sdk`, `riscv_ae350_soc`
compile en V3/V4), programmes stockés en DDR3, chargés par UART ou depuis la flash.

```
' rem — commentaires
DIM var[, var...]                     ' entiers 32 bits, tableau DIM a[64]
LET var = expr                        ' opérateurs + - * / % & | ^ << >> ()
IF cond THEN ... ELSE ... FI
WHILE cond ... WEND  /  FOR i=a TO b [STEP s] ... NEXT
GOSUB label / RETURN / GOTO label
' --- vidéo
PAGE n                                ' page de dessin courante (0..63)
SHOW n                                ' page affichée (double buffering : DRAW puis SHOW)
CLS [c]      PLOT x,y,c      LINE x1,y1,x2,y2,c      RECT x,y,w,h,c[,fill]
CIRCLE x,y,r,c[,fill]     TRIANGLE x1,y1,x2,y2,x3,y3,c[,fill]
GRAD mode,x1,y1,x2,y2,c1,c2           ' mode 0=horizontal 1=vertical 2=diagonal 45°
SPRITE n,x,y[,flip]    SPRITEBMP n,ad, taille    ' 64 sprites, bitmap en BSRAM
MESH n,ad        TRANS n,m00..m33     ' 3D : maillage 32 sommets, matrice 4×4 Q16.16
DRAW3D n[,wire|,fill]                 ' transforme + projette + trace via le raster
TEXT x,y,"chaîne",c
PALETTE i,rgb    FLIP                 ' bascule page dessin/page visible
WAIT vblank   SYNC n                  ' cadence jeu
' --- E/S
IN ch                                 ' lit la voie numérique du connecteur
OUT ch,val    OUTMODE ch,mode         ' PWM / motif / fréquence (héritage gen_out8)
ADQ(adc,ch)                           ' dernière mesure ADS1115 (0/1 = les deux ADC)
```

Alternatives écartées : Forth (arbitré contre — lisibilité), micro-Python (pas de portage
raisonnable sur AE350 + footprint RAM), interpréteur matériel (métadonnée : plus tard si besoin
de vitesse, le jeu des pages/sprites suffit à 60 Hz).

## 6. Étapes (chacune mesurée, consignée dans `TESTS/TESTS_V1.md`)

| Étape | Contenu | Critère de sortie |
|---|---|---|
| E0 | portage des constraints : `.cst` Pro Dock (brochage depuis exemples Sipeed + schéma 4071f), PLL DDR3 pour FPG676 | build passe ; **CDC-ACM énuméré sur le port SOFT-USB** (`/dev/ttyACM*`), pas de BL616 |
| E1 | AE350 + DDR3 sur le Pro : rejouer le test `pro_ddr_test` (pattern `57 52 FF FF FF`) | DDR3 32 bits validée sur carte |
| E2 | LCD 480×272 seul : mire interne (pas de DDR) | écran affiche les barres |
| E3 | page vidéo en DDR3 + bascule SHOW/FLIP | mire dessinée par CPU visible, flip sans tearing (mesuré vblank) |
| E4 | police + TEXT + CLS/PLOT/LINE | texte affiché, vitesse de remplissage mesurée |
| E5 | merge 2 pages + palette | overlay visible, alpha vérifié à l'œil + mesures de trames GAO |
| E6 | sprites 64 hardware | jeu de test : 64 sprites animés 60 fps, compteur d'overflow à 0 |
| E6b | raster : ligne/cercle/rect/triangle + fill + dégradés 0/45/90 | formes tracées en 1 image, dégradé vérifié pixel à pixel sur mire |
| E6c | 3D : cube wireframe puis cube flat (6 faces) | rotation fluide 60 fps, faces dans le bon ordre (painter) |
| E7 | E/S connecteur : gen_out8 + sampler + ADS1115 × 2 | signaux 10 MHz mesurés au scope, lectures ADC affichées |
| E8 | interpréteur : grammaire du § 5, premiers jeux | 2 jeux de démonstration tournant à 60 fps |

## 7. Points de risque et repli

1. **Portage PG484 → FPG676** : le brochage DDR3, AE350, PLL diffèrent. Repli : s'appuyer sur
   `ae350_customized_demo` (c'est déjà AE350 + DDR3 sur ce boîtier) plutôt que sur notre V3/V4.
2. **Bande passante DDR3 partagée CPU/vidéo** : la page visible est un flux continu ; si le CPU
   ralentit le balayage (tearing), séparer base/overlay sur deux lecteurs (déjà prévu § 3) et
   mesurer avec GAO avant d'ajouter des contraintes.
3. **Le merge au vol** : la composition base+overlay+sprites doit tenir dans le budget pixel
   (~12 MHz → ~37 cycles par pixel sur ahb). Seule la palette + merge est critique ; les sprites
   sont fetchés une ligne d'avance (pipeline 1 ligne).
4. **64 sprites sur une même ligne** : 64 × 32 px = 2048 px potentiels pour 480 affichés — le
   moteur ne peut pas tout dessiner. Limite matérielle : 64 slots par ligne, débordement
   **signalé** dans un registre de statut (aucun repli silencieux). En pratique les jeux
   n'empilent pas 64 sprites sur la même ligne ; à mesurer en E6.
5. **Dégradés en 8 bpp** : interpolation d'index sur une rampe palette de 16 entrées — pas du
   true-color. Si Michael veut du vrai dégradé continu, il faudra du 16 bpp : décision à
   trancher à E6b (voir § 2, format pixel).
6. **3D sans Z-buffer** : painter's algorithm géré par le CPU (tri des faces). Limites assumées
   pour des objets convexes ; concave = artefacts de tri possibles. V2 si besoin.
7. **Pas de fallback silencieux** : si le DDR3 ne passe pas (E1), on ne « dégrade » pas en BSRAM ;
   on arrête et on diagnostique (héritage diag-embarque).

## 8. Hors périmètre explicitement (à rappeler si redemandé)

- USB 3 : absent du Pro Dock (fait wiki Sipeed + ARCHI V4 § 1). Le lien de chargement = UART.
- 10 MHz *analogique* : impossible avec ADS1115 (860 éch/s, datasheet). Numérique seulement.
- PCIe, SFP+, caméra : V2+.
