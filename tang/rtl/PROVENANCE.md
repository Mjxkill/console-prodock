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
- `uart/`, `sync_fifo/`, `integer_division/` — sources Sipeed/Gowin, copies conformes.
- `ddrtest/ddr3_memory_interface/` — netlist `DDR3_Memory_Interface_Top` (PHY DDR3) —
  `pro_ddr_test/src/ddr3_memory_interface/`.
- `ddrtest/gowin_pll/` — PLL DDR Sipeed (copie).
- `ddrtest/ddr3_test.v`, `fifo.v`, `uart_tx.v` — sources du test Sipeed (copies conformes).
- `video/lcd_timing.v`, `video/gowin_pll_lcd.v` — exemples Sipeed `rgb_screen/800_480_screen`
  (timing 800×480 pour le panneau CJ050QGH50), lcd_timing : **HS/VS ajoutés localement** (E0b).

Règle du projet : ne jamais modifier le contenu chiffré ; les modifications RTL se font dans
les modules du projet (`console_top.v`, machines CDC/DDR3).
