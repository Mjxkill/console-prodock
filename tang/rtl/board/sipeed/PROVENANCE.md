# Provenance — pont AHB → DDR3 de Sipeed

Fichiers copiés tels quels (2026-09-19) depuis le dépôt public
`https://github.com/sipeed/TangMega-138KPro-example`, dossier `ae350_customized_demo/src/ddr3_memory/`,
**licence Apache 2.0** (Copyright 2024 Shenzhen Sipeed Technology Co,Ltd.), démonstrateur AE350 du Tang Mega 138K Pro
(même SoM / mêmes DDR3 Hynix H5TQ4G63 que la Console) :
- `gw_ahb_ddr3.v` : `gw_ahb_ddr3_top` (pont AHB 64 bits « Customized Data Memory » de l'AE350 → interface utilisateur de l'IP
  DDR3 standalone, FIFOs de franchissement d'horloge), code Gowin/Sipeed en clair, non modifié.
- `ddr3_memory_rdfifo.v`, `ddr3_memory_wrfifo.v` : netlists de l'IP FIFO Gowin utilisées par le pont (générées Gowin 1.9.10.03,
  GW5AST-138B), non modifiées.
La netlist de l'IP DDR3 elle-même est regénérée par nous (`../ddr3_standalone/`), pas copiée.

**Modification (2026-09-19)** : `gw_ahb_ddr3.v` — largeur des ports DDR3 DQ/DQS/DM ramenée de 32 à 16 bits dans
`gw_ahb_ddr3_top` et `gw_ahb_ddr3`. Raison : le pont pilote une interface utilisateur de 128 bits (`lpddr_wr_data`,
masque 16 bits, `addr = octets/2`), c'est-à-dire une DDR3 de 16 bits ; avec l'IP en 32 bits (256 bits, comme dans le
démonstrateur Sipeed lui-même) les mots hauts de chaque rafale sont écrits à zéro et les lectures du cœur valent 0
(constaté sur carte, TESTS_V3 §E1). Le passage à 32 bits demanderait de réécrire le chemin de données du pont (E1-g).
