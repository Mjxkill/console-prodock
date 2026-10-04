# GPU L13/L14/L15 — image SRAM validée

3 octobre 2026, build `gpu_l1315_r3`, Tang Mega 138K Pro Dock FPG676.

- AE350 800 MHz, bus 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- Carte vidéo complète G0–G6/FAST/L11/L12, avec alpha RGB565, triangles
  texturés affines et profondeur Z16.
- Commandes console : `a` teste quatre images, `b` anime, `c` met en pause.
- Origines de plans signées 48 bits, faces complètes, rotation continue sur
  512 phases. Deux cubes séparés avec motifs noirs et bords blancs.
- Timing minimal +0,143 ns ; 42 974 éléments logiques, 32 041 registres,
  223 BSRAM, 49 DSP ; firmware 64 488 octets ITCM.
- Deux chargements SRAM avec HS vérifié, 217 640 octets d'échos exacts ;
  suite complète, références couleur/profondeur exactes et contrôle géométrique
  indépendant. 600 images d'animation ≈55 images/s, aucun underflow,
  rendu maximal mesuré 12,518 ms. Rendu visuellement confirmé par l'utilisateur.

Le fichier `.fs` et son `.sha256` sont accompagnés du manifeste des
106 sources figées dans `.sources.json`. Le projet reproductible est
`tang/impl/gpu_l1315_r3`, avec les mêmes paramètres de génération USB que
`gpu_l12_usb_hs33_idle_r3` (contrôleur 3.3, PHY 3.5 Advance).

Charger uniquement en SRAM sur le FTDI **2023112818**, après identification
de son numéro bus:périphérique actuel. La flash n'a pas été modifiée.

[Contrat et limites](../ARCHI/GPU_L13_L15_RGB_DEPTH.md) ·
[Validation détaillée](../TESTS/TESTS_GPU_L13_L15.md).
