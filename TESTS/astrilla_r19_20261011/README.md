# Version ASTRILLA R19 chargée et validée

Ce dossier archive la version finale de la démonstration autonome de cinq
minutes, testée sur la Pro Dock avec le FPGA G22r0.

- Programme final : `pack/astrilla_hw.bin`, décrit par `pack/astrilla.json`.
- Sources exactes du programme : `pack/source/`, avec empreintes dans le manifest.
- Ressources DDR : `assets/astrilla/packed/astrilla.bin`, à la racine du dépôt.
- Résumé des mesures : `summary.json` ; tests matériels : `check_accepted/` ;
  preuve de chargement du programme : `load_accepted/`.
- Références finales : `board_expected.json`, `reference_accepted/` et
  `edges_accepted/` ; simulation exhaustive : `geometry_accepted/`.
- [Compte rendu détaillé](../ASTRILLA_R19_20261011.md).

Résultat : 170 poses exactes, 16 901 images en 308,687 secondes, 54,751 FPS,
pire rendu de 16,847 ms, aucune erreur GPU ni sous-débordement vidéo.

Le FPGA associé est archivé dans
`TESTS/gpu_geometry_20261011/g22r0_trial.tar.gz`, accompagné de son SHA-256.
L'archive contient le bitstream exact, les sources FPGA figées, les paramètres,
la netlist et les rapports du build. Ses chemins sont relatifs à la racine du
dépôt. Elle conserve le premier pack d'essai G22r0 : le programme final R19 est
celui du présent dossier `pack/`, et non le programme de cet ancien pack.

G22r0 reste **expérimental, non qualifié en timing** : −0,564 ns, 9 violations
setup, 0 hold. Les résultats fonctionnels de R19 ne constituent pas une
qualification du timing. Les manifests conservent explicitement ce statut.

Les dossiers `pack_pre_*`, `pack_near_shared`, `check`, `check_budget` et
`check_release` retracent les essais intermédiaires. Ils ne sont pas la version
retenue. Les images et vidéos de simulation régénérables restent hors Git,
à l'exception de l'aperçu compact `r19_apercu.png`.
