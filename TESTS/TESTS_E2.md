# E2 — Console AE350 sur USB CDC, Pro Dock FPG676

Note G1 : ce compte rendu décrit le bitstream E2 archivé. Les nouveaux builds
utilisent `fw_console/itcm.ld` (données ILM, pile DLM), car la disposition tout
en ITCM d'E2 ne supporte pas correctement la maintenance du cache.
Voir [TESTS_GPU_G1.md](TESTS_GPU_G1.md).

## Configuration (27 septembre 2026)

Cœur **800 MHz** sur PLL_R[0]/CLKOUT1, AHB/APB **80 MHz** sur CLKOUT0.
La PLL USB F est déplacée en R[2]. LCD 800×480 et DDR3 32 bits restent présents.
Le reset CPU attend la calibration DDR3 et le verrouillage de la PLL système.

Le firmware local `fw_console/main.c` émet une bannière, puis renvoie chaque
octet reçu (écho binaire, sans transformation). Il utilise le BSP Gowin, code,
données et pile en ITCM. L'IP SoC est régénérée après compilation pour embarquer
`fw_console/build/itcm`, au lieu du firmware du projet analyseur.
UART2 : APB 80 MHz, diviseur 43, débit réel ~116279 bauds, 8N1.

## Corrections du pont

- 521 cycles/bit à 60 MHz (~115163 bauds), au lieu de 32.
- Deux bascules de synchronisation RX, vérification du start et du stop,
  rejet des faux départs et du break.
- FIFO TX de huit octets et `ep2_rx_rdy`, avec réserve pour la latence de
  sortie du FIFO USB. Les rafales PC ne sont plus jetées pendant la transmission.
- `usb_rx_buf` : `c_fifo_dval` tient compte de `i_ep_rx_rdy`, comme `RdEn`,
  afin de ne pas annoncer un octet qui n'a pas été extrait.
- L'émission vers USB attend `usb_online` (invariant E1) ; le reset USB
  vide aussi le pont. LED UART cadencée par `phy_clk`, sans horloge sur TXD.

## Vérification en simulation

`TESTS/rtl/uart2_to_ep2_tb.sv`, Verilator : **PASS**.
Réception de 544 octets (toutes les valeurs 00–FF, 521 et 516 cycles/bit,
puis 32 octets à 531 cycles/bit). Émission de 256 octets en quatre rafales USB
de 64 octets via le vrai `usb_rx_buf`, en parallèle de la réception.
Aucune perte, duplication ou inversion ; faux départ et break rejetés.

```sh
verilator --binary --timing -Wno-fatal --top-module uart2_to_ep2_tb \
  --Mdir /tmp/console_e2_uart_test TESTS/rtl/uart2_to_ep2_tb.sv \
  tang/rtl/ae350/uart2_to_ep2.v tang/rtl/usb/sync_fifo/usb_fifo.v \
  tang/rtl/usb/sync_fifo/sync_rx_pkt_fifo.v
/tmp/console_e2_uart_test/Vuart2_to_ep2_tb
```

Compilation firmware : 11832 octets initialisés, 384 octets BSS. Les quatre
fichiers ITCM entrelacés correspondent exactement au binaire.

Build isolé : `tang/impl/diag_pllr0/e2_uart_800/` (sources avant modification,
sources utilisées, empreintes, projet de régénération IP et journaux).

Le premier build tient les fréquences internes mais signale des violations
entre domaines USB et aux entrées UART. Le fichier E2 avait omis les groupes
asynchrones de `usb2_soft/usb_uart_loopback/src/usb_ref.sdc` de Sipeed/Gowin.
Ces contraintes sont reprises avec les horloges explicites 48/60/960 MHz.
Deux exceptions ciblées couvrent UART2_RXD et la première bascule de RX ;
le chemin entre les deux bascules de synchronisation reste analysé.
Le build avec ces contraintes est isolé sous `e2_uart_800_timing/`.

## Essai carte

**VALIDÉ : écho AE350 ↔ USB CDC sur la Pro Dock, 27 septembre 2026.**

Chargement SRAM : Pro Dock série JTAG **2023112818**, USB **3:12** relu avant
programmation, `openFPGALoader` : **100 %, Done / DONE, code 0**.
Énumération : **/dev/ttyACM1**, MegaPro Console, VID:PID **359f:2011**,
série CDC **11252024**. L'index tty peut changer ; le script sélectionne
VID/PID et refuse plusieurs consoles identiques.

| Envoi PC → AE350 → PC | Résultat | Durée |
|---|---|---|
| 1 octet | exact | < 1 ms |
| 64 octets | exact | 6 ms |
| 256 octets | exact | 22 ms |
| 1024 octets | exact | 89 ms |
| 4096 octets | exact | 356 ms |

**5441 octets, aucune perte, aucun doublon, aucun octet supplémentaire.**
Le firmware C est donc exécuté par l'AE350 et les deux sens UART/USB fonctionnent.
Ce test valide l'écho ; il ne valide pas encore un chargeur de programmes,
l'accès DDR3 par le CPU ni le futur interpréteur.

Timing final : **0 endpoint en violation setup/hold**, 110 chemins détaillés
tous non négatifs (minimum **0,139 ns**). Horloges rapportées : cœur 800 MHz,
bus 80 MHz, USB 60 MHz, LCD 35 MHz. Les deux exceptions UART sont actives.

Bitstream conservé : **`bitstreams/console_e2_uart_800_echo.fs`**, empreinte
dans le fichier `.sha256` voisin. Sources et empreintes du build :
`tang/impl/diag_pllr0/e2_uart_800_timing/sha256.json`.
Journaux : `e2_uart_800_timing/load.log` et `uart_test.log`.
Le test LED validé est conservé sous `refdemo_800_fast/`.

Commande de répétition : `python3 tools/check_console_uart.py`.
Dans un terminal série : 115200 bauds, 8N1, sans contrôle de flux, écho local
désactivé ; les caractères sont renvoyés par le firmware.

**Mire LCD 800×480 validée par Michael après ce chargement : « Oui, la mire est correcte ».**
Suite : accès CPU à la DDR3 et première page vidéo pilotée par l'AE350 (E3).

## Reproduction du build

1. `make -C fw_console` compile le firmware et produit les quatre fichiers ITCM.
2. Régénérer l'IP avec `GowinSynthesis -prj riscv_ae350_soc.prj` dans le dossier
   `e2_uart_800/ip/` : le projet utilise la configuration locale
   `rtl/board/riscv_ae350_soc_ext/cfg`, dont `ITCM_INIT_PATH` pointe vers ce firmware.
3. Copier la nouvelle netlist `.vg` vers
   `tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v` et sa copie dans `cfg/`.
4. Lancer `gw_sh build.tcl` dans un dossier de build isolé, avec le projet de
   `e2_uart_800_timing/`, ou `gw_sh build_e2.tcl` depuis `tang/`.

Outils utilisés : `/home/michael/gowin/Gowin_V1.9.12_linux/IDE/bin/`, avec
`LD_LIBRARY_PATH=/home/michael/gowin/Gowin_V1.9.12_linux/IDE/lib`,
`QT_QPA_PLATFORM=offscreen` et `DISPLAY=`. Une reconstruction FPGA seule
ne met **pas** à jour l'image ITCM déjà incorporée dans la netlist SoC.
