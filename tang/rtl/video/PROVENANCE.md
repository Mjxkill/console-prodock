# Sources G2

3 octobre 2026, retour GPU avec pont CPU/DDR à deux horloges : `blitter.v`
prépare l'adresse et le nombre de mots DMA au début de chaque ligne de
rectangle/copie, zoom, affine et texte. Ce déplacement supprime les tests
de fin de pixel/caractère de leurs enables, sans modifier les cycles des
interfaces. Équivalence 604 commandes / 2 081 517 cycles :
`TESTS/gpu_hs_cdc_r3_equivalence_20261003.txt`.

`blitter.v`, `font_ram.v` et `font8x16.hex` proviennent du projet local
`../logic_analyser_wifi/tang/rtl/video`, révision
`be1229c1eadf6d5dde77abe2e49ee6151a38c323`.

Le rasteriseur est adapté au 800×480, à la DDR3, au découpage de la source
des copies et aux copies superposées. Les calculs de lignes, cercles et
dégradés acceptent les coordonnées signées 16 bits. La police a maintenant
des ports d'écriture et de lecture sur des horloges distinctes.

`font8x16.hex` est la conversion 256 glyphes × 16 octets de la police
`/usr/share/consolefonts/Lat15-Terminus16.psf.gz`, reprise sans modification
du projet source. Bit 7 à gauche. Nom de cette conversion : Console Bitmap 8x16.
La police d'origine est [Terminus Font](https://terminus-font.sourceforge.net/),
de Dimitar Toshkov Zhekov, sous SIL Open Font License 1.1.
La notice et la licence sont conservées intégralement dans `FONT_LICENSE.txt`,
extraites de `/usr/share/doc/keyboard-configuration/copyright.fonts.gz`
(section des fichiers `ter-u*.bdf`). Elles s'appliquent aussi à la police
embarquée dans le bitstream et à sa représentation C générée pour le diagnostic.

`gpu_accel.v` et `gpu_blit_dma.v` sont propres à ce projet : file de commandes
AHB à deux horloges et adaptation des ports de pixels aux rafales DDR3 de 256 bits.

L'opcode ZOOM (11), son cache de ligne DDR et l'échantillonnage 8.16 sont
des extensions propres à ce projet, ajoutées pour le prototype de course G6.
Les graphismes procéduraux du jeu sont définis dans `fw_console/racer_scene.h`.

`gpu_tile_row.v` (L11, décors en tuiles) est propre à ce projet : lecture
des cases et des lignes de tuiles en DDR3, retournements et assemblage en
mots de 32 pixels. `gpu_line_reader.v` lui confie les couches en tuiles et
garde son traitement des couches d'image.

Le rasteriseur par intersections entières d'arêtes dans `gpu_triangle.v` et
la voie d'aplats natifs 256 bits dans `gpu_blit_dma.v` sont propres à ce projet.
Ils conservent les règles de pixels et le protocole de commandes précédents.

Revue USB/L11 : la remise à zéro du pointeur de lecture des banques de
`blitter.v` passe par `row_rewind` pour raccourcir le chemin vers la BSRAM.
Le protocole, les pixels et les cycles consommés sont conservés, vérifiés
contre le module antérieur par `TESTS/rtl/blitter_equiv.sv`.

La préparation d'une lecture de surface dans `gpu_line_reader.v` charge
les registres d'adresse/alignement même pour une ligne refusée. Seuls
l'état et `request_valid` autorisent la requête : le contrôle de limite DDR
ne pilote plus les activations de registres larges. Le banc lié
`TESTS/rtl/gpu_reader_equiv.sv` compare les interfaces au cycle près avec
la version antérieure, y compris les surfaces hors de la DDR.

Revue timing suivante : `blitter.v` et `gpu_triangle.v` utilisent un bit
par état, avec les mêmes transitions et cycles. Les bornes source d'une
copie sont préparées dans les cycles existants avant `M_COPY_CLIP`.
La comparaison du blitter comprend le rasteriseur et ses diviseurs
antérieurs inchangés ; les interfaces et pixels restent équivalents.

`gpu_blit_dma.v` enregistre les trois acquittements d'écriture pour couper
le chemin de retour DDR vers le blitter. Ils arrivent un cycle après
l'acceptation native (jamais avant). `TESTS/rtl/gpu_dma_equiv.sv` vérifie
ce décalage exact et l'identité des interfaces natives ; la régression
AHB/DDR vérifie les pixels et quantifie le coût en cycles.

`gpu_scanout.v` présélectionne les registres de lecture durant la phase
adresse AHB. Le multiplexage des valeurs conserve le cycle et la valeur
courante ; `TESTS/rtl/gpu_registers_equiv.sv` compare avec le décodage
antérieur, notamment durant les attentes de validation de scène.

La correction du quotient signé de `gpu_triangle_floor_div` prépare en
parallèle le complément du quotient et la nullité du reste. Elle conserve
les 36 itérations et le résultat ; 12 000 divisions sont comparées à la
version antérieure. Le blitter prépare aussi la fin de caractère pendant
la lecture de police, sans changer les cycles ni les pixels du texte.

## L12 — transformations affines (30 septembre 2026)

Extension originale de `blitter.v` : opcodes 12/13, six coefficients signés
Q16.16, cache source de 16 Kio, échantillonnage inverse et lignes masquées.
`gpu_accel.v` expose la capacité dans le bit 0 du registre `0x20`.
Aucun changement de protocole DDR ni du lecteur de composition. Les opcodes
1 à 11 sont comparés au cycle près à l'instantané `gpu_l11_usb_r13/source`.
Le banc AHB compare aussi les transformations à des produits entiers Python
indépendants, avec images entières, gardes, chevauchement et descripteurs invalides.
La table sinus de la démonstration réemploie celle du jalon G5 local ; les
images asymétriques sont calculées par `fw_console/gpu_affine_scene.h`.

Validation L12 : ajout dans `usb/sync_fifo/usb_fifo.v` (chemin relatif au
dossier `rtl`) d'une qualification du POP des FIFO IN par la présence d'un
payload annoncé (`!CORK && longueur != 0`). Un octet déjà arrivé en RAM
mais pas encore propagé dans la longueur enregistrée ne doit pas être
consommé par le POP d'un sondage à vide. Le banc `usb_in_packet_tb.sv`
reproduit la perte avant correction et la conservation après correction ;
le banc concurrent conserve ses 30 000 octets et 3 685 reprises.

L12 r4 : les comparaisons de masque de COPY déplacent la parité source
dans deux limites préparées en `M_COPY_COUNT`. Les soustractions signées
ne traversent plus le chemin d'activation des banques lors de `s_valid`.
La régression conserve les 541 commandes, 1 269 390 cycles du blitter,
94 260 mots et les transactions DMA de L11 à l'identique.

L12 r5 : `gpu_blit_dma.v` prépare `read_active` et `read_last` sur les
mêmes fronts que les transitions d'état et de compteur. Les signaux S
conservent leurs cycles, mais leur décodage ne traverse plus le chemin
de fin de ligne du blitter. Les deux registres utilisent l'attribut
Gowin documenté `syn_preserve=1` pour conserver cette préparation.

L12 r6 : le DMA prépare `write_follow_addr` pendant l'assemblage d'une
rafale ou la préparation de son masque. Le signal READY ne traverse plus
les choix fin de remplissage/fin de ligne avant de valider cette adresse.
Même les valeurs d'adresse entre transactions restent identiques dans le
banc d'équivalence DMA (1 269 391 cycles contre L11).


Réintégration HS 3.3/PHY 3.5 (2 octobre 2026) : la validation du crop zoom/affine
et son dernier indice de ligne sont préparés dans les cycles existants. Les
compteurs de rafale avancent au cycle d’échantillonnage de la demande DMA,
à partir de sa longueur enregistrée. L’équivalence avec le snapshot complet
`gpu_l12_usb_hs33_ep0_r3/source` compare 604 commandes et 2081517 cycles,
y compris les échanges DDR, sans différence de pixels ni de latence.
`gpu_sprite_cache.v` calcule la fin de texture pendant la lecture du dernier
mot du descripteur avant de la comparer dans CHECK ; la régression complète
800×480 couches/sprites/tuiles conserve les résultats et budgets précédents.
Aucun changement de fréquence ni d’interface logicielle.
# L13–L15 (3 octobre 2026, validé sur carte : gpu_l1315_r3)

- `gpu_raster.v` et `gpu_rgb_reader.v` : création originale pour cette console.
  Alpha RGB565, texture affine en cache et profondeur Z16 ; lecteur RGB565.
- `blitter.v` : relais ordonné des opcodes 14–20 vers le moteur natif.
- `gpu_accel.v` : arbitrage exclusif entre ancien DMA et nouveau moteur,
  capacités et compteurs transférés par `cdc_word`.
- `gpu_scanout.v` : format RGB565 appliqué au retour vertical, buffers de ligne
  étendus ; composition indexée historique conservée.
- Aucune modification des netlists fournisseur ni des fréquences/SDC.
- Le pas ×1/×2 de `gpu_scanout.v` est sélectionné par multiplexage/décalage.
  Cette écriture évite l'absorption incorrecte des registres AHB/pixel dans
  un DSP observée avec une multiplication variable en r1. Le contrôle de
  synthèse et les essais avant/après sont dans `TESTS/TESTS_GPU_L13_L15.md`.
- R3 : origines de plans signées sur 48 bits et accumulateurs sur 49 bits
  pour conserver les triangles dont les profondeurs sont valides à l'écran,
  même si le plan extrapolé à l'origine sort de l'ancien format 32 bits.
  La démonstration boucle sur 512 phases ; le test géométrique indépendant
  vérifie l'intérieur des cubes et la continuité de cette boucle.

# Perspective et composition RGB565 / indexée (3 octobre 2026)

- `gpu_perspective.v` : création originale, division entière signée exacte
  en base quatre pour les coordonnées UQ/Q et VQ/Q. Soustractions Q/2Q/3Q
  parallèles, capture séparée de la valeur absolue, deux instances anticipées.
  Sélection exclusive des restes, 50 bits avec zéro de tête pour les 25 pas
  généraux ; entrées toujours signées sur 49 bits, mêmes résultats et latence.
- `gpu_raster.v` : ajout du plan Q et du drapeau perspective ; traitement
  couleur/alpha/Z commun à l'ancien mode. Activation des tampons préparée
  à l'avance ; retour DDR capturé avant son écriture dans les tampons de
  pixels. L'ancien raster conserve ses cycles dans le banc de régression.
  Le tampon de texture suit le bus avant l'acceptation, puis reste figé
  pendant sa copie : le tag DDR ne pilote plus son activation sur 256 bits.
  La profondeur précédente est capturée en PIX_SAMPLE avant sa comparaison.
  R9 encode explicitement la machine avec un bit par état pour raccourcir
  le retour d'acceptation DDR ; l'équivalence conserve tous les cycles de
  l'ancien moteur sur les 359 commandes RGB565 de référence.
  R10 répartit la sélection des 16 pixels couleur/Z en deux étapes 4:1
  dans SAMPLE/TEST, avant BLEND, et isole l'activation de `wr_data`.
  Transactions et compteurs restent identiques au cycle près.
- `blitter.v` et `gpu_accel.v` : relais de l'opcode 21 et bit de capacité.
  R9 pré-décode les adresses de lecture AHB pendant la phase d'adresse,
  sans changer les registres ni la latence du protocole.
- `gpu_line_reader.v` : couverture par pixel pour distinguer un index zéro
  opaque d'un emplacement non couvert. `gpu_scanout.v` conserve les lignes
  indexées et RGB565 séparées, puis sélectionne le pixel effectivement couvert.
  Fond, format et tables sont appliqués ensemble au retour vertical.
  R9 prépare la condition de blocage AHB pendant la phase d'adresse afin
  de raccourcir le retour HREADY, sans modifier les écritures protégées.
  R10 remplace le multiplexage de validité DDR par le OU des trois lecteurs
  exclusifs. Le banc vérifie cette exclusivité et l'ancien multiplexage
  à chaque cycle, y compris les surcharges et interruptions DDR.
  L'alignement des octets est réparti sur les deux étapes déjà présentes
  (2 bits puis 3 bits), sans cycle de composition supplémentaire.
- `gpu_rgb_reader.v` : requêtes DDR en vol dans le seul mode composé ;
  séquencement historique conservé en RGB565 direct.
- Huit anciennes contraintes de placement `gowin_add_SDPB_composed_*`
  retirées du CST, leurs cellules ayant disparu à la synthèse ; les placements
  des BSRAM `composed_*` existantes restent conservés. Aucun changement du SDC,
  des fréquences ou des IP fermées USB/DDR/AE350.
  R10 ajoute un placement de la bascule USB `bit_align_wr_act_s1`, d'après
  son chemin critique routé r9 ; aucune modification de la logique du PHY.
- Contrat : `ARCHI/GPU_PERSPECTIVE_COMPOSITION.md`. Preuves, rapports des
  builds et statut sur carte : `TESTS/TESTS_GPU_PERSPECTIVE.md`.

### GPU V1 — 4 octobre 2026, R31 validé

Sources originales du projet : `gpu_v1.v` (cibles, scissor, plans, matériau,
RGB565/ARGB4444, alpha/additif, Gouraud, brouillard), `gpu_texture_cache.v`
(cache lecture DDR de 2 Kio), `gpu_copy565.v` (copie rectangulaire avec recouvrement).
Le générateur de spans et les diviseurs perspective existants sont réutilisés.
`gpu_accel.v` et `blitter.v` routent les nouveaux opcodes 22–30 ; les opcodes
1–21 conservent leurs moteurs. `gpu_scanout.v`/`gpu_rgb_reader.v` ajoutent
l'agrandissement ×2 et le pas RGB565, engagés au vblank. Aucune netlist
fournisseur ni contrainte d'horloge n'est modifiée.
Le contrôle DDR de `gpu_accel.v` forme VALID/WRITE à partir des demandes
enregistrées exclusives des moteurs ; les transactions, réponses AHB et
cycles sont comparés à la version figée r8 dans trois simulations complètes.
Les chemins de validation, d'adressage de texture et de test Z sont découpés
dans `gpu_v1.v` ; `gpu_copy565.v` enregistre son décaleur de sortie sans
activation issue de l'état. Le CST r10 ajoute seulement un placement du
multiplexeur RXACTIVE USB, à qualifier après routage. Les IP fermées restent
identiques.
R13 retire les prédicats de validation des activations des bornes privées de
copie/effacement, et prédécode les mots de `gpu_raster.v` dans le cycle déjà
disponible avant START. La comparaison au cycle près porte alors sur le parent
et les neuf moteurs vidéo figés de r11 ; une assertion vérifie la stabilité
préalable de la commande. Aucun cycle de dessin n'est ajouté.
R14 isole les activations U/V/Z/Q du rasteriseur et indique les états
one-hot exclusifs à la synthèse. `gpu_triangle.v` teste l'intersection des
bords par comparaisons parallèles, sans changer les spans ni leurs cycles.
Le banc compare le parent et les moteurs figés r13 sur les trois chemins
indexé, perspective et V1, et vérifie l'invariant one-hot. La contrainte de
placement de l'activation AHB `m_hready` est déplacée d'après son fil critique
routé ; les périodes restent identiques.
R15 décode séparément les coordonnées affines et les deux coordonnées
perspective de l'ancien rasteriseur, puis sélectionne leurs adresses courtes
de texture. La comparaison complète au r14 conserve tous les pixels et
cycles sur les 785 commandes perspective et 746 commandes mixtes V1.
R17 prédécode les six classes de commandes du blitter pendant la lecture
des mots de commande, avant SETUP. Les trois comparaisons complètes au r15
conservent les cycles, pixels et gardes ; une assertion vérifie l'exclusivité
des classes de commandes.
R18 prépare le test de dernière ligne de copie pendant le transfert,
rééquilibre le décalage du lecteur entre les registres existants et simplifie
le test de dépassement de bloc du blitter. Ces modifications ne doivent
changer ni les transactions ni les cycles ; les preuves sont consignées
dans la fiche de tests avant qualification physique.
R20 découple dans `board/ddr_gpu_arb.v` l'échantillonnage du tampon CPU vide
de la requête tardive : aucune commande validée ni aucun cycle d'acceptation
ne change. Le moniteur d'équivalence ne compare les charges utiles DDR que
sous leur strobe, et conserve la comparaison de tous les contrôles à chaque
cycle. Un banc à données/masques variables vérifie aussi les écritures CPU.
Statut et preuves : `TESTS/TESTS_GPU_V1.md` ; ne pas considérer le jalon
comme qualifié sur carte avant sa validation explicite dans cette fiche.

### Registre d’adresse V1 et DSP — r22

Gowin 1.9.12 absorbe deux registres à enables distincts dans le pipeline C
du copieur avec ordre inversé (r20). Le registre `gpu_v1.packet_base` est
conservé dans la logique par `syn_preserve=1` (SUG550-2.1E §4.3/§5.12).
Preuve primitive officielle : `TESTS/test_gpu_copy_dsp.py`, 64 reproductions
et 64 résultats corrigés. Audit : `tools/check_gpu_copy_synthesis.py`.
Aucun changement des IP fournisseur, de l’ABI ou des cycles RTL.

L’audit r22 révèle aussi une double absorption inversée pour `z_end`.
R23 protège donc le paquet complet de 256 bits ; le garde-fou couvre
`gpu_copy565` et `gpu_v1`. Le firmware exige la validation du changement
de page Z, des copies entre pages, des masques et des gardes mémoire.

### Test Q positif — r24

`gpu_perspective` capture le signe de Q puis vérifie son dénominateur
enregistré non nul à l’étape ABS déjà présente. Cela coupe le chemin
addition 49 bits + comparaison complète, sans changer les cycles visibles.
Équivalence cycle par cycle : 2 252 paires, puis 751 commandes intégrées.

### Pont de commandes AHB — r25 à r31

Dans `board/ahb_exts_bridge.v`, les charges utiles privées sont capturées
en IDLE, tandis que seul le prédicat d'acceptation fait passer en DATA.
HREADY reçoit une valeur à chaque cycle, sans enable combinatoire tardif.
Le test redondant de HREADY dans IDLE est supprimé sur l'invariant des états
atteignables. Toutes les sorties publiques et les cycles sont identiques
au pont r24 : 250 000 cycles, 23 629 acceptations dont 22 annulées par reset
avant émission, données/cibles vérifiées séparément.

Le CST place les trois registres `m_hready_s0`, `st_0_s0`, `st_1_s5` près
du cœur dur, en R4C150 ; les noms sont vérifiés dans la netlist r31. Le SDC
reste identique. R31 passe le timing, la suite complète sur carte et
30 minutes d'endurance (58 680 images) ; les scènes sont confirmées
visuellement. Image et sources archivées, bilan dans `TESTS/TESTS_GPU_V1.md`.
