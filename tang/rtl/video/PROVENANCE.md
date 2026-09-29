# Sources G2

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
