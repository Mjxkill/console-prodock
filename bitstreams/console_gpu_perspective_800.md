# GPU perspective et composition — image SRAM validée

3 octobre 2026, build `gpu_perspective_r10`, Tang Mega 138K Pro Dock FPG676.

- Carte vidéo complète G0–G6/FAST/L11–L15, avec correction matérielle de
  perspective des textures et couches/tuiles/sprites indexés sur fond RGB565.
- AE350 800 MHz, bus 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- `d` vérifie quatre images avancées ; `e` anime ; `c` met en pause.
  Les commandes `a`/`b` du rendu affine historique restent disponibles.
- Timing sans violation : minimum +0,140 ns, GPU +0,789 ns, AHB +0,977 ns.
- Ensemble FPGA : 46 206 éléments logiques, 34 231 registres,
  239 BSRAM, 53 DSP ; firmware 54 552 octets ITCM, BSS 29 128 octets.
- Deux rechargements SRAM, nouvelle énumération HS à chaque fois ;
  217 640 octets binaires exacts. Suite complète USB, DDR et graphique passée.
- Quatre références couleur/Z et quatre empreintes LCD composées exactes ;
  600 images avancées à 54,84–55,18 images/s, aucun underflow.
  Dessin maximal mesuré 12,881 ms ; composition 2 019 / 2 556 cycles par ligne.
  Ces mesures portent sur la démonstration testée, pas sur toute scène possible.
- La nouvelle animation est laissée active ; sa confirmation visuelle par
  l'utilisateur n'a pas encore été reçue.

Le `.fs`, son `.sha256` et le manifeste des 108 sources figées sont réunis
ici. Snapshot reproductible : `TESTS/gpu_perspective_20261003/r10_sources.tar.gz`.
Les IP USB sont générées avec contrôleur Gowin High-Speed et PHY Advance,
comme indiqué dans le journal de build et le manifeste.

Charger uniquement en SRAM sur le FTDI **2023112818**, après identification
de son numéro bus:périphérique actuel. La flash n'a pas été modifiée.

[Fonctionnalités et limites](../ARCHI/FONCTIONNALITES_ACTUELLES.md) ·
[Contrat](../ARCHI/GPU_PERSPECTIVE_COMPOSITION.md) ·
[Validation détaillée](../TESTS/TESTS_GPU_PERSPECTIVE.md).
