# PROVENANCE — netlists fermées et IP externes (2026-09-26)

Les fichiers chiffrés/fermés de `tang/rtl/usb/` et `tang/rtl/ddrtest/` viennent du dépôt
officiel Sipeed `TangMega-138KPro-example` (Apache 2.0 / CC BY-SA 4.0), copiés tels quels :

- `usb2_0_softphy.v` — netlist `USB2_0_SoftPHY_Top` (USB2 soft PHY, 9 broches + RC) —
  `usb2_soft/usb_uart_loopback/src/usb2_0_softphy/usb2_0_softphy.v`
- `usb_device_controller.v` — netlist `USB_Device_Controller_Top` (CDC-ACM, 16 EP) —
  `usb2_soft/usb_uart_loopback/src/usb_device_controller/usb_device_controller.v`
- `usb_descriptor.v` — source ouverte, modifiée ? NON : copie exacte de
  `usb2_soft/usb_uart_loopback/src/usb_descriptor.v` (les paramètres strings sont passés par
  l'instanciation, pas modifiés dans le fichier).
- `gowin_pll_f.v`, `gowin_pll_b.v` — PLLs générées par Gowin 1.9.10.03, copiées de l'exemple.
  **PLL_F modifiée localement (E1)** : CLKOUT1/2 activés (100/400 MHz pour le DDR3) — voir le diff.
- `uart/`, `integer_division/` — sources Sipeed/Gowin, copies conformes.
- `sync_fifo/` — sources Sipeed/Gowin ; **modification E2** dans `usb_fifo.v` :
  la validité d'un octet reçu est conditionnée par `i_ep_rx_rdy`, comme la lecture
  FIFO, pour permettre la régulation du débit vers l'UART AE350.
  **Correction de reprise USB IN (29 septembre 2026)** dans `sync_tx_pkt_fifo.v` :
  le pointeur de prélecture `rp_next` est rétabli avec `rp` à la fin d'une
  tentative de paquet. Sans cela, une retransmission à lectures consécutives
  corrompt son deuxième octet. Reproduit par `TESTS/rtl/usb_tx_retry_tb.sv`.
  Dans `usb_fifo.v`, la longueur d'un paquet IN est conservée jusqu'à son
  acquittement (seulement pour un paquet non vide annoncé disponible ;
  aucun paquet réservé lors d'un sondage à vide) : les octets UART arrivés
  entre deux tentatives doivent rester
  dans le paquet suivant. L'autorisation `txcork` et cette longueur sont
  acquises ensemble : le paquet peut s'ouvrir pendant l'attente active de
  données, puis reste stable pendant sa lecture. Un octet tardif ne doit pas
  ouvrir un paquet de longueur nulle. La sélection d'un
  endpoint simultanée au début de transaction reste prise en compte.
  Reproduit par `TESTS/rtl/usb_in_packet_tb.sv`.
- `ddrtest/ddr3_memory_interface/` — netlist `DDR3_Memory_Interface_Top` (PHY DDR3) —
  `pro_ddr_test/src/ddr3_memory_interface/`.
- `ddrtest/gowin_pll/` — PLL DDR Sipeed (copie).
- `ddrtest/ddr3_test.v`, `fifo.v`, `uart_tx.v` — sources du test Sipeed (copies conformes).
- `video/lcd_timing.v`, `video/gowin_pll_lcd.v` — exemples Sipeed `rgb_screen/800_480_screen`
  (timing 800×480 pour le panneau CJ050QGH50), lcd_timing : **HS/VS ajoutés localement** (E0b).

Règle du projet : ne jamais modifier le contenu chiffré ; les modifications RTL se font dans
les modules du projet (`console_top.v`, machines CDC/DDR3).

## Modification L11 du socle DDR3 (29 septembre 2026)

`board/ddr_ui_adapt.v` et `board/ddr_arb.v` : l'état « file pleine » de leur
file d'étiquettes est calculé par sélection tardive entre trois comparaisons
des pointeurs courants. Valeur identique à l'expression d'origine sur les
4 096 cas (`TESTS/rtl/ddr_tag_queue_equiv.sv`).

Revue USB/L11 : `board/ddr_arb.v` sélectionne ensuite le maître et les
données indépendamment de `ready`, qui ne conditionne que l'acceptation.
Les priorités, les cycles acceptés, les masques et les étiquettes de lecture
restent identiques sur 4 096 cas (`TESTS/rtl/ddr_arb_equiv.sv`). Cela enlève
le trajet combinatoire DDR ready/reset → sélection d'adresse → rotation
→ tampon CPU de l'arbitre GPU, sans ajouter de cycle.

Revue r9 : `ddr_ui_adapt.v` prépare l'étiquette dans l'emplacement libre
sans attendre `push`. Elle n'est publiée que par l'avance du pointeur ;
aucune écriture à file pleine. Interfaces comparées sur 20 000 cycles
contre r8 (`TESTS/rtl/ddr_ui_equiv.sv`).

## Ajouts E2 — AE350 et diagnostic LED (27 septembre 2026)

- `board/` : socle AE350/DDR3 porté du projet local `logic_analyser_wifi`,
  configuré pour le Pro Dock FPG676, avec DDR3 32 bits. Provenance du pont et
  de ses FIFO détaillée dans `board/sipeed/PROVENANCE.md`.
- `board/riscv_ae350_soc_ext/riscv_ae350_soc.v` : IP AE350 régénérée par Gowin
  1.9.12 avec la configuration `cfg/` et le firmware local d'écho E2.
- `ae350/uart2_to_ep2.v` : pont UART/CDC du projet, corrigé et testé en E2.
- `../ref_demo/` : démonstrateur `ae350_customized_demo` de Sipeed Pro Dock,
  adapté pour le test LED à 800 MHz et bus 80 MHz ; IP AE350 régénérée avec
  `../ref_demo_cfg/` et `fw_console/demo/demo_led.S`.
- Les configurations et wrappers de PLL sont adaptés localement ; le contenu
  chiffré des IP est produit par les outils du fournisseur.
