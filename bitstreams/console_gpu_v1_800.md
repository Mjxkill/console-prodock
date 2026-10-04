# GPU V1 — image SRAM validée

4 octobre 2026, build `gpu_v1_r31`, Tang Mega 138K Pro Dock FPG676.

Les sept points vidéo sont livrés : cibles RGB565/Z16 paramétrables, cache
DDR pour textures jusqu'à 512 × 512, API 2D RGB565, alpha par texel/additif/
Gouraud, brouillard/mipmaps, mode 400 × 240 agrandi ×2 avec HUD natif,
ABI/pilote/outils et qualification. Les commandes historiques sont conservées.

- AE350 800 MHz, AHB 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- `f` vérifie mémoire, douze poses couleur/Z/LCD et changement de résolution ;
  `g` anime les trois scènes ; `c` met en pause.
- Zéro violation setup/hold : marge minimale globale +0,140 ns ;
  pires setups GPU/DDR +0,706 ns et AHB +1,524 ns. SDC inchangé.
- Ensemble FPGA : 65 812 éléments logiques (47,61 %), 43 754 registres
  (31,45 %), 242 BSRAM (71,18 %), 83 DSP (27,85 %), 8/8 PRIMARY.
  Firmware : 63 832 octets ITCM, 29 184 octets BSS.
- Deux rechargements SRAM, nouvelle énumération HS à chaque fois,
  217 640 octets binaires exacts ; suite GPU complète passée.
- Douze références couleur/Z et LCD exactes, test de copie entre pages et
  changement de Z passé, gardes mémoire intactes. Trois scènes confirmées
  visuellement par l'utilisateur.
- Endurance : 1802.141 s,
  58680 images et 191552
  octets d'écho USB exacts pendant l'animation, sans underflow, refus,
  corruption détectée ni réénumération. Références revérifiées après le test.
  Dessin maximal : 30.533 ms ;
  composition : 504/2556 cycles par ligne.

Avant les échos d'endurance, aventure/couloir : environ 27,4 images/s ;
route : 54,58 images/s. Les échos occupent momentanément la boucle CPU et
leur durée compte dans l'intervalle de présentation. Le LCD reste à environ
55,04 Hz. Les scènes sont des charges de qualification, pas des jeux finis.
Le dessin comparatif prend 28,464 ms en 400 × 240 contre 102,228 ms en
800 × 480 (facteur 3,59). Ces mesures valent pour les contenus testés.

SHA-256 du `.fs` : `60806fa2e988641e5b67ddcc5b13873c5b39c87621d5f1a23bbcf5e80b6d6aee`.
Le `.sources.json` décrit les 119 sources figées ; leur archive vérifiée est
[`r31_sources.tar.gz`](../TESTS/gpu_v1_20261004/r31_sources.tar.gz), accompagnée
de son SHA-256. Le `.validation.json` donne le bilan automatique.

Le garde-fou `check_gpu_copy_synthesis.py` est obligatoire : une absorption
incorrecte de registres à activations distinctes dans les DSP avait laissé
passer le timing tout en corrompant les copies r20. Conserver `syn_preserve`
sur le paquet V1 ; les preuves et la correction sont documentées.

Charger uniquement en SRAM sur le FTDI **2023112818**, après identification
de son numéro bus:périphérique actuel. La flash n'a pas été modifiée.
Reconstruction : options placement 3, route 1, réplication désactivée et
IP USB Gowin High-Speed/PHY Advance, selon la fiche de tests et le manifeste.

[Fonctionnalités et limites](../ARCHI/FONCTIONNALITES_ACTUELLES.md) ·
[Contrat](../ARCHI/GPU_V1.md) ·
[Validation détaillée](../TESTS/TESTS_GPU_V1.md).
