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

Le rasteriseur par intersections entières d'arêtes dans `gpu_triangle.v` et
la voie d'aplats natifs 256 bits dans `gpu_blit_dma.v` sont propres à ce projet.
Ils conservent les règles de pixels et le protocole de commandes précédents.
