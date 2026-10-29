# Tang Console Neo 138K

Sortie HDMI 1280×720. Les expériences de portage restent dans les snapshots Neo et dans tools/neo. DDR 5.9/300 MHz conservée pour le diagnostic R19.

[Retour à la carte du dépôt](../README.md)

Catalogue détaillé : [catalogue.json](catalogue.json).

Les [sources communes](../commun/README.md) complètent cette liste.

- [Top Neo](../../../tang/boards/neo/console_neo.v)
- [Brochage et placement](../../../tang/boards/neo/neo.cst)
- [Contraintes temporelles](../../../tang/boards/neo/neo.sdc)
- [Constructeur Neo](../../../tools/build_console_neo.py)
- [État du diagnostic R19](../../../TESTS/neo_720p_20261012/local_capture_20261026/handoff.json)

## 103 entrées de développement

| Fichier unique | Type |
|---|---|
| [linux/drivers/neo-gamepads.c](../../../linux/drivers/neo-gamepads.c) | source |
| [linux/neo-linux.dts](../../../linux/neo-linux.dts) | source |
| [linux/tests/test_neo_gamepads.py](../../../linux/tests/test_neo_gamepads.py) | test |
| [linux/tests/test_scanout_720p.py](../../../linux/tests/test_scanout_720p.py) | test |
| [linux/userspace/neo-gamepad-input.h](../../../linux/userspace/neo-gamepad-input.h) | source |
| [tang/boards/neo/console_neo.v](../../../tang/boards/neo/console_neo.v) | source |
| [tang/boards/neo/ddr6.json](../../../tang/boards/neo/ddr6.json) | source |
| [tang/boards/neo/ddr6/DDR3_define.v](../../../tang/boards/neo/ddr6/DDR3_define.v) | source |
| [tang/boards/neo/ddr6/ddr3_name.v](../../../tang/boards/neo/ddr6/ddr3_name.v) | source |
| [tang/boards/neo/ddr6/ddr3_standalone.v](../../../tang/boards/neo/ddr6/ddr3_standalone.v) | source |
| [tang/boards/neo/ddr6/generation.json](../../../tang/boards/neo/ddr6/generation.json) | source |
| [tang/boards/neo/ddr6/gwmc_param.v](../../../tang/boards/neo/ddr6/gwmc_param.v) | source |
| [tang/boards/neo/ddr6_300.json](../../../tang/boards/neo/ddr6_300.json) | source |
| [tang/boards/neo/ddr6_300/DDR3_define.v](../../../tang/boards/neo/ddr6_300/DDR3_define.v) | source |
| [tang/boards/neo/ddr6_300/ddr3_name.v](../../../tang/boards/neo/ddr6_300/ddr3_name.v) | source |
| [tang/boards/neo/ddr6_300/ddr3_standalone.v](../../../tang/boards/neo/ddr6_300/ddr3_standalone.v) | source |
| [tang/boards/neo/ddr6_300/generation.json](../../../tang/boards/neo/ddr6_300/generation.json) | source |
| [tang/boards/neo/ddr6_300/gwmc_param.v](../../../tang/boards/neo/ddr6_300/gwmc_param.v) | source |
| [tang/boards/neo/ddr6_325.json](../../../tang/boards/neo/ddr6_325.json) | source |
| [tang/boards/neo/ddr6_325/DDR3_define.v](../../../tang/boards/neo/ddr6_325/DDR3_define.v) | source |
| [tang/boards/neo/ddr6_325/ddr3_name.v](../../../tang/boards/neo/ddr6_325/ddr3_name.v) | source |
| [tang/boards/neo/ddr6_325/ddr3_standalone.v](../../../tang/boards/neo/ddr6_325/ddr3_standalone.v) | source |
| [tang/boards/neo/ddr6_325/generation.json](../../../tang/boards/neo/ddr6_325/generation.json) | source |
| [tang/boards/neo/ddr6_325/gowin_pll_ddr3.v](../../../tang/boards/neo/ddr6_325/gowin_pll_ddr3.v) | source |
| [tang/boards/neo/ddr6_325/gowin_pll_ddr3_mod.v](../../../tang/boards/neo/ddr6_325/gowin_pll_ddr3_mod.v) | source |
| [tang/boards/neo/ddr6_325/gwmc_param.v](../../../tang/boards/neo/ddr6_325/gwmc_param.v) | source |
| [tang/boards/neo/ddr6_400.json](../../../tang/boards/neo/ddr6_400.json) | source |
| [tang/boards/neo/ddr6_400/DDR3_define.v](../../../tang/boards/neo/ddr6_400/DDR3_define.v) | source |
| [tang/boards/neo/ddr6_400/ddr3_name.v](../../../tang/boards/neo/ddr6_400/ddr3_name.v) | source |
| [tang/boards/neo/ddr6_400/ddr3_standalone.v](../../../tang/boards/neo/ddr6_400/ddr3_standalone.v) | source |
| [tang/boards/neo/ddr6_400/generation.json](../../../tang/boards/neo/ddr6_400/generation.json) | source |
| [tang/boards/neo/ddr6_400/gowin_pll_ddr3_mod.v](../../../tang/boards/neo/ddr6_400/gowin_pll_ddr3_mod.v) | source |
| [tang/boards/neo/ddr6_400/gwmc_param.v](../../../tang/boards/neo/ddr6_400/gwmc_param.v) | source |
| [tang/boards/neo/ddr_dcfifo_registers.v](../../../tang/boards/neo/ddr_dcfifo_registers.v) | source |
| [tang/boards/neo/ddr_fifo_registers.json](../../../tang/boards/neo/ddr_fifo_registers.json) | source |
| [tang/boards/neo/ddr_tagged.json](../../../tang/boards/neo/ddr_tagged.json) | source |
| [tang/boards/neo/ddr_tagged_split.json](../../../tang/boards/neo/ddr_tagged_split.json) | source |
| [tang/boards/neo/ddr_ui_adapt.v](../../../tang/boards/neo/ddr_ui_adapt.v) | source |
| [tang/boards/neo/ddr_ui_adapt_split.v](../../../tang/boards/neo/ddr_ui_adapt_split.v) | source |
| [tang/boards/neo/import.json](../../../tang/boards/neo/import.json) | source |
| [tang/boards/neo/neo.cst](../../../tang/boards/neo/neo.cst) | constraint |
| [tang/boards/neo/neo.sdc](../../../tang/boards/neo/neo.sdc) | constraint |
| [tang/boards/neo/neo_console_input.v](../../../tang/boards/neo/neo_console_input.v) | source |
| [tang/boards/neo/neo_ddr_startup.v](../../../tang/boards/neo/neo_ddr_startup.v) | source |
| [tang/boards/neo/neo_gamepads.v](../../../tang/boards/neo/neo_gamepads.v) | source |
| [tang/boards/neo/neo_gpu_debug.v](../../../tang/boards/neo/neo_gpu_debug.v) | source |
| [tang/boards/neo/neo_gpu_response.v](../../../tang/boards/neo/neo_gpu_response.v) | source |
| [tang/boards/neo/neo_scan_queue.v](../../../tang/boards/neo/neo_scan_queue.v) | source |
| [tang/boards/neo/soft_usb.vh](../../../tang/boards/neo/soft_usb.vh) | source |
| [tang/boards/neo/usbhost/LICENSE](../../../tang/boards/neo/usbhost/LICENSE) | source |
| [tang/boards/neo/usbhost/firmware/asukp.py](../../../tang/boards/neo/usbhost/firmware/asukp.py) | source |
| [tang/boards/neo/usbhost/firmware/ukp.s](../../../tang/boards/neo/usbhost/firmware/ukp.s) | source |
| [tang/boards/neo/usbhost/import.json](../../../tang/boards/neo/usbhost/import.json) | source |
| [tang/boards/neo/usbhost/usb_gamepad.v](../../../tang/boards/neo/usbhost/usb_gamepad.v) | source |
| [tang/boards/neo/usbhost/usb_gamepad_controls.v](../../../tang/boards/neo/usbhost/usb_gamepad_controls.v) | source |
| [tang/boards/neo/usbhost/usb_gamepad_reports.v](../../../tang/boards/neo/usbhost/usb_gamepad_reports.v) | source |
| [tang/boards/neo/usbhost/usb_hid_host_rom.hex](../../../tang/boards/neo/usbhost/usb_hid_host_rom.hex) | source |
| [tang/boards/neo/usbhost/usb_hid_host_rom.v](../../../tang/boards/neo/usbhost/usb_hid_host_rom.v) | source |
| [tang/boards/neo/usbhost/usb_ls_engine.v](../../../tang/boards/neo/usbhost/usb_ls_engine.v) | source |
| [tang/boards/neo/vendor/hdmi_out.v](../../../tang/boards/neo/vendor/hdmi_out.v) | source |
| [tang/boards/neo/vendor/svo_tmds.v](../../../tang/boards/neo/vendor/svo_tmds.v) | source |
| [tang/boards/neo/vendor/uart_console_bridge.v](../../../tang/boards/neo/vendor/uart_console_bridge.v) | source |
| [tang/boards/neo/vendor/uart_rx.v](../../../tang/boards/neo/vendor/uart_rx.v) | source |
| [tang/boards/neo/vendor/uart_tx.v](../../../tang/boards/neo/vendor/uart_tx.v) | source |
| [tang/boards/neo/vendor/video_pll.v](../../../tang/boards/neo/vendor/video_pll.v) | source |
| [tools/build_console_neo.py](../../../tools/build_console_neo.py) | build |
| [tools/check_neo_fifo_mapped.py](../../../tools/check_neo_fifo_mapped.py) | build |
| [tools/check_neo_fifo_synthesis.py](../../../tools/check_neo_fifo_synthesis.py) | build |
| [tools/check_neo_timing.py](../../../tools/check_neo_timing.py) | build |
| [tools/neo/build_ddr_ip.py](../../../tools/neo/build_ddr_ip.py) | build |
| [tools/neo/build_reference.py](../../../tools/neo/build_reference.py) | build |
| [tools/neo/build_reset_probe.py](../../../tools/neo/build_reset_probe.py) | build |
| [tools/neo/check_ddr_startup_mapped.py](../../../tools/neo/check_ddr_startup_mapped.py) | build |
| [tools/neo/check_gpu.py](../../../tools/neo/check_gpu.py) | build |
| [tools/neo/check_usb.py](../../../tools/neo/check_usb.py) | build |
| [tools/neo/command_prefetch.py](../../../tools/neo/command_prefetch.py) | build |
| [tools/neo/console.py](../../../tools/neo/console.py) | build |
| [tools/neo/ddr_phy_timing.py](../../../tools/neo/ddr_phy_timing.py) | build |
| [tools/neo/ddr_startup.py](../../../tools/neo/ddr_startup.py) | build |
| [tools/neo/finish_pixels.py](../../../tools/neo/finish_pixels.py) | build |
| [tools/neo/gpu_control_routes.py](../../../tools/neo/gpu_control_routes.py) | build |
| [tools/neo/gpu_debug.py](../../../tools/neo/gpu_debug.py) | build |
| [tools/neo/gpu_replication.py](../../../tools/neo/gpu_replication.py) | build |
| [tools/neo/gpu_reset.py](../../../tools/neo/gpu_reset.py) | build |
| [tools/neo/gpu_response.py](../../../tools/neo/gpu_response.py) | build |
| [tools/neo/incremental.py](../../../tools/neo/incremental.py) | build |
| [tools/neo/load_linux.py](../../../tools/neo/load_linux.py) | build |
| [tools/neo/pixel_command_prefetch.py](../../../tools/neo/pixel_command_prefetch.py) | build |
| [tools/neo/pixel_mask.py](../../../tools/neo/pixel_mask.py) | build |
| [tools/neo/pixel_selector.py](../../../tools/neo/pixel_selector.py) | build |
| [tools/neo/probe_address_pairs.py](../../../tools/neo/probe_address_pairs.py) | build |
| [tools/neo/probe_geometry.py](../../../tools/neo/probe_geometry.py) | build |
| [tools/neo/probe_gpu_debug.py](../../../tools/neo/probe_gpu_debug.py) | build |
| [tools/neo/probe_gpu_legacy.py](../../../tools/neo/probe_gpu_legacy.py) | build |
| [tools/neo/probe_memory.py](../../../tools/neo/probe_memory.py) | build |
| [tools/neo/raster_payload.py](../../../tools/neo/raster_payload.py) | build |
| [tools/neo/recover_linux_shell.py](../../../tools/neo/recover_linux_shell.py) | build |
| [tools/neo/run_reset_probe.py](../../../tools/neo/run_reset_probe.py) | build |
| [tools/neo/system_reset.py](../../../tools/neo/system_reset.py) | build |
| [tools/neo/timing.py](../../../tools/neo/timing.py) | build |
| [tools/neo/timing_closure.py](../../../tools/neo/timing_closure.py) | build |
| [tools/neo/validate_pending.py](../../../tools/neo/validate_pending.py) | build |
| [tools/route_console_neo.py](../../../tools/route_console_neo.py) | build |

## 214 dossiers de construction

Les chemins historiques restent en place : les scripts, Tcl et preuves les référencent. Les déplacer sans migration de ces dépendances casserait la reproductibilité.

| Snapshot | FS conservés | Taille après nettoyage | Protection / état |
|---|---:|---:|---|
| [console_neo_n1](../../../tang/impl/console_neo_n1) | 0 | 3.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n10](../../../tang/impl/console_neo_n10) | 0 | 85.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n11](../../../tang/impl/console_neo_n11) | 1 | 262.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n12](../../../tang/impl/console_neo_n12) | 1 | 272.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n12r1](../../../tang/impl/console_neo_n12r1) | 1 | 265.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n13](../../../tang/impl/console_neo_n13) | 1 | 274.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n13r1](../../../tang/impl/console_neo_n13r1) | 1 | 261.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n13r2](../../../tang/impl/console_neo_n13r2) | 1 | 261.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n14](../../../tang/impl/console_neo_n14) | 1 | 277.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n14r1](../../../tang/impl/console_neo_n14r1) | 1 | 269.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n15](../../../tang/impl/console_neo_n15) | 1 | 278.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n15r1](../../../tang/impl/console_neo_n15r1) | 1 | 262.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n16](../../../tang/impl/console_neo_n16) | 1 | 273.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n16r1](../../../tang/impl/console_neo_n16r1) | 1 | 264.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n16r2](../../../tang/impl/console_neo_n16r2) | 0 | 88.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n17](../../../tang/impl/console_neo_n17) | 1 | 272.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n17r1](../../../tang/impl/console_neo_n17r1) | 1 | 261.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n18](../../../tang/impl/console_neo_n18) | 1 | 275.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n18r1](../../../tang/impl/console_neo_n18r1) | 0 | 27.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n18r2](../../../tang/impl/console_neo_n18r2) | 1 | 263.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n19](../../../tang/impl/console_neo_n19) | 1 | 264.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n2](../../../tang/impl/console_neo_n2) | 0 | 3.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n20](../../../tang/impl/console_neo_n20) | 1 | 271.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n20opt_0](../../../tang/impl/console_neo_n20opt_0) | 1 | 261.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n20opt_1](../../../tang/impl/console_neo_n20opt_1) | 1 | 263.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n20r1](../../../tang/impl/console_neo_n20r1) | 1 | 264.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n21](../../../tang/impl/console_neo_n21) | 1 | 274.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n21r1](../../../tang/impl/console_neo_n21r1) | 1 | 259.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n21split_0](../../../tang/impl/console_neo_n21split_0) | 1 | 262.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n22](../../../tang/impl/console_neo_n22) | 1 | 258.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n23](../../../tang/impl/console_neo_n23) | 1 | 270.0 Mio | Conservé : dépendance ou référence |
| [console_neo_n24](../../../tang/impl/console_neo_n24) | 1 | 256.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n24r1](../../../tang/impl/console_neo_n24r1) | 1 | 263.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n25](../../../tang/impl/console_neo_n25) | 0 | 87.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n25r1](../../../tang/impl/console_neo_n25r1) | 0 | 4.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n25r2](../../../tang/impl/console_neo_n25r2) | 1 | 258.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n25r3](../../../tang/impl/console_neo_n25r3) | 1 | 263.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n26](../../../tang/impl/console_neo_n26) | 1 | 272.6 Mio | Conservé : dépendance ou référence |
| [console_neo_n26r1](../../../tang/impl/console_neo_n26r1) | 1 | 260.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n27](../../../tang/impl/console_neo_n27) | 1 | 260.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n28](../../../tang/impl/console_neo_n28) | 1 | 259.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n29](../../../tang/impl/console_neo_n29) | 1 | 270.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n29r1](../../../tang/impl/console_neo_n29r1) | 1 | 264.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n29r2](../../../tang/impl/console_neo_n29r2) | 1 | 263.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n3](../../../tang/impl/console_neo_n3) | 0 | 22.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n30](../../../tang/impl/console_neo_n30) | 1 | 271.0 Mio | Conservé : dépendance ou référence |
| [console_neo_n30r1](../../../tang/impl/console_neo_n30r1) | 1 | 265.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n31](../../../tang/impl/console_neo_n31) | 1 | 277.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n31r1](../../../tang/impl/console_neo_n31r1) | 1 | 261.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n32](../../../tang/impl/console_neo_n32) | 1 | 276.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n32r1](../../../tang/impl/console_neo_n32r1) | 1 | 260.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n33](../../../tang/impl/console_neo_n33) | 1 | 276.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n33p1_0](../../../tang/impl/console_neo_n33p1_0) | 1 | 265.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n33p_0](../../../tang/impl/console_neo_n33p_0) | 0 | 28.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n34](../../../tang/impl/console_neo_n34) | 1 | 276.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n34r1](../../../tang/impl/console_neo_n34r1) | 1 | 264.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n35](../../../tang/impl/console_neo_n35) | 1 | 276.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n35r1](../../../tang/impl/console_neo_n35r1) | 0 | 41.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n36](../../../tang/impl/console_neo_n36) | 0 | 5.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n36r0](../../../tang/impl/console_neo_n36r0) | 1 | 268.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n37r0](../../../tang/impl/console_neo_n37r0) | 1 | 267.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n38r0](../../../tang/impl/console_neo_n38r0) | 1 | 563.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n38r1](../../../tang/impl/console_neo_n38r1) | 1 | 268.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n38r2_newide](../../../tang/impl/console_neo_n38r2_newide) | 1 | 266.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n38r3_primary](../../../tang/impl/console_neo_n38r3_primary) | 1 | 268.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n39r0](../../../tang/impl/console_neo_n39r0) | 1 | 563.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n39r1](../../../tang/impl/console_neo_n39r1) | 1 | 265.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n3r1](../../../tang/impl/console_neo_n3r1) | 0 | 22.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n3r2](../../../tang/impl/console_neo_n3r2) | 0 | 22.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n3r3](../../../tang/impl/console_neo_n3r3) | 1 | 227.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n4](../../../tang/impl/console_neo_n4) | 1 | 227.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n40r0](../../../tang/impl/console_neo_n40r0) | 1 | 562.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n40r1](../../../tang/impl/console_neo_n40r1) | 0 | 28.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n40r2](../../../tang/impl/console_neo_n40r2) | 1 | 268.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n41r0](../../../tang/impl/console_neo_n41r0) | 1 | 268.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n41r1_newide](../../../tang/impl/console_neo_n41r1_newide) | 1 | 266.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n41syn](../../../tang/impl/console_neo_n41syn) | 0 | 28.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n42r0](../../../tang/impl/console_neo_n42r0) | 1 | 267.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n42syn](../../../tang/impl/console_neo_n42syn) | 0 | 29.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n43r0](../../../tang/impl/console_neo_n43r0) | 1 | 270.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n43syn](../../../tang/impl/console_neo_n43syn) | 0 | 32.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n44r0](../../../tang/impl/console_neo_n44r0) | 0 | 93.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r1](../../../tang/impl/console_neo_n44r1) | 1 | 378.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r2](../../../tang/impl/console_neo_n44r2) | 1 | 378.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r3](../../../tang/impl/console_neo_n44r3) | 1 | 378.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r4](../../../tang/impl/console_neo_n44r4) | 1 | 378.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r5](../../../tang/impl/console_neo_n44r5) | 1 | 378.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r6](../../../tang/impl/console_neo_n44r6) | 1 | 379.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n44r7](../../../tang/impl/console_neo_n44r7) | 0 | 93.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n44syn](../../../tang/impl/console_neo_n44syn) | 0 | 32.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n45r0](../../../tang/impl/console_neo_n45r0) | 0 | 31.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n45r1](../../../tang/impl/console_neo_n45r1) | 1 | 379.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n45r2](../../../tang/impl/console_neo_n45r2) | 1 | 379.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n45r3](../../../tang/impl/console_neo_n45r3) | 1 | 378.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n45r4](../../../tang/impl/console_neo_n45r4) | 0 | 341.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n45syn](../../../tang/impl/console_neo_n45syn) | 0 | 32.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n46r0](../../../tang/impl/console_neo_n46r0) | 1 | 375.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n46syn](../../../tang/impl/console_neo_n46syn) | 0 | 7.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n46syn1](../../../tang/impl/console_neo_n46syn1) | 0 | 32.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n46syn2](../../../tang/impl/console_neo_n46syn2) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n47r0](../../../tang/impl/console_neo_n47r0) | 1 | 378.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n47r1](../../../tang/impl/console_neo_n47r1) | 1 | 382.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n47r2](../../../tang/impl/console_neo_n47r2) | 1 | 375.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n47syn](../../../tang/impl/console_neo_n47syn) | 0 | 7.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n47syn1](../../../tang/impl/console_neo_n47syn1) | 0 | 32.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n48r0](../../../tang/impl/console_neo_n48r0) | 1 | 653.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n48r1](../../../tang/impl/console_neo_n48r1) | 1 | 651.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n48syn](../../../tang/impl/console_neo_n48syn) | 0 | 7.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n48syn1](../../../tang/impl/console_neo_n48syn1) | 0 | 7.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n48syn2](../../../tang/impl/console_neo_n48syn2) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n49syn](../../../tang/impl/console_neo_n49syn) | 0 | 32.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n5](../../../tang/impl/console_neo_n5) | 1 | 238.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n50r0](../../../tang/impl/console_neo_n50r0) | 1 | 651.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n50r1](../../../tang/impl/console_neo_n50r1) | 1 | 651.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n50r2](../../../tang/impl/console_neo_n50r2) | 1 | 651.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n50r3](../../../tang/impl/console_neo_n50r3) | 0 | 93.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n50r4](../../../tang/impl/console_neo_n50r4) | 0 | 92.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n50syn](../../../tang/impl/console_neo_n50syn) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n51r0](../../../tang/impl/console_neo_n51r0) | 1 | 378.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n51syn](../../../tang/impl/console_neo_n51syn) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n52r0](../../../tang/impl/console_neo_n52r0) | 1 | 378.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r1](../../../tang/impl/console_neo_n52r1) | 1 | 646.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n52r10](../../../tang/impl/console_neo_n52r10) | 0 | 92.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r11](../../../tang/impl/console_neo_n52r11) | 1 | 385.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r11_preparation_rejected](../../../tang/impl/console_neo_n52r11_preparation_rejected) | 0 | 7.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r12](../../../tang/impl/console_neo_n52r12) | 0 | 103.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r2](../../../tang/impl/console_neo_n52r2) | 0 | 32.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r3](../../../tang/impl/console_neo_n52r3) | 0 | 42.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r4](../../../tang/impl/console_neo_n52r4) | 1 | 374.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r5](../../../tang/impl/console_neo_n52r5) | 1 | 386.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r6](../../../tang/impl/console_neo_n52r6) | 1 | 375.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r7](../../../tang/impl/console_neo_n52r7) | 1 | 385.4 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r8](../../../tang/impl/console_neo_n52r8) | 1 | 385.5 Mio | Historique, sources et rapports conservés |
| [console_neo_n52r9](../../../tang/impl/console_neo_n52r9) | 0 | 103.0 Mio | Historique, sources et rapports conservés |
| [console_neo_n52syn](../../../tang/impl/console_neo_n52syn) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n53r0](../../../tang/impl/console_neo_n53r0) | 1 | 375.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n53syn](../../../tang/impl/console_neo_n53syn) | 0 | 32.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n54_mask](../../../tang/impl/console_neo_n54_mask) | 0 | 4.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n54_mask_r1](../../../tang/impl/console_neo_n54_mask_r1) | 0 | 29.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n54_timing](../../../tang/impl/console_neo_n54_timing) | 0 | 29.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n54r0](../../../tang/impl/console_neo_n54r0) | 1 | 264.3 Mio | Historique, sources et rapports conservés |
| [console_neo_n54r1](../../../tang/impl/console_neo_n54r1) | 1 | 640.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n54r2](../../../tang/impl/console_neo_n54r2) | 0 | 100.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n54r3](../../../tang/impl/console_neo_n54r3) | 0 | 29.1 Mio | Historique, sources et rapports conservés |
| [console_neo_n54r4](../../../tang/impl/console_neo_n54r4) | 1 | 370.8 Mio | Historique, sources et rapports conservés |
| [console_neo_n55_selector](../../../tang/impl/console_neo_n55_selector) | 0 | 29.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n55r0](../../../tang/impl/console_neo_n55r0) | 1 | 372.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n55r1](../../../tang/impl/console_neo_n55r1) | 0 | 4.9 Mio | Historique, sources et rapports conservés |
| [console_neo_n55r2](../../../tang/impl/console_neo_n55r2) | 1 | 641.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n56_observe](../../../tang/impl/console_neo_n56_observe) | 1 | 642.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r1](../../../tang/impl/console_neo_n56r1) | 1 | 641.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r10_gao_startup](../../../tang/impl/console_neo_n56r10_gao_startup) | 2 | 631.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r11_gao_tck_bufs](../../../tang/impl/console_neo_n56r11_gao_tck_bufs) | 0 | 29.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r12_gao_tck_bufg](../../../tang/impl/console_neo_n56r12_gao_tck_bufg) | 0 | 29.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r13_gao_tck_cst](../../../tang/impl/console_neo_n56r13_gao_tck_cst) | 0 | 29.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r14_gao_tck_cst_seeded](../../../tang/impl/console_neo_n56r14_gao_tck_cst_seeded) | 1 | 591.0 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r15_reset50ms](../../../tang/impl/console_neo_n56r15_reset50ms) | 1 | 641.6 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r16_gao_pixels](../../../tang/impl/console_neo_n56r16_gao_pixels) | 0 | 283.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r17_gao_opcode](../../../tang/impl/console_neo_n56r17_gao_opcode) | 0 | 235.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r18_local_capture](../../../tang/impl/console_neo_n56r18_local_capture) | 0 | 54.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r18r1_local_capture](../../../tang/impl/console_neo_n56r18r1_local_capture) | 1 | 672.9 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r19_capture_ce_local](../../../tang/impl/console_neo_n56r19_capture_ce_local) | 1 | 647.5 Mio | Diagnostic Neo actuellement chargé le 26 octobre après coupure utilisateur. Mire visible et JTAG actif ; CPU arrêté. GPU complet non qualifié ; CLEAR natif bloquait dans les essais historiques. Timing FAIL. |
| [console_neo_n56r2](../../../tang/impl/console_neo_n56r2) | 1 | 642.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r20_memory_observer](../../../tang/impl/console_neo_n56r20_memory_observer) | 0 | 29.6 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r20r1_memory_observer](../../../tang/impl/console_neo_n56r20r1_memory_observer) | 0 | 91.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r3](../../../tang/impl/console_neo_n56r3) | 1 | 642.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r4](../../../tang/impl/console_neo_n56r4) | 1 | 643.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r5](../../../tang/impl/console_neo_n56r5) | 1 | 663.0 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r6_scan_reset](../../../tang/impl/console_neo_n56r6_scan_reset) | 1 | 642.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r7_hdmi_pg0](../../../tang/impl/console_neo_n56r7_hdmi_pg0) | 1 | 642.3 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r8_hdmi_sg4](../../../tang/impl/console_neo_n56r8_hdmi_sg4) | 1 | 641.9 Mio | Repli Neo pour la mire HDMI, conservé. Ne qualifie pas le framebuffer DDR ni le GPU complet. |
| [console_neo_n56r9_route1](../../../tang/impl/console_neo_n56r9_route1) | 1 | 644.6 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route2](../../../tang/impl/console_neo_n56r9_route2) | 1 | 645.6 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route3_scan_reset](../../../tang/impl/console_neo_n56r9_route3_scan_reset) | 1 | 644.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route4_c150](../../../tang/impl/console_neo_n56r9_route4_c150) | 1 | 644.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route5_c155](../../../tang/impl/console_neo_n56r9_route5_c155) | 1 | 645.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route6_hdmi_c155](../../../tang/impl/console_neo_n56r9_route6_hdmi_c155) | 1 | 645.2 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route7_hdmi_c140](../../../tang/impl/console_neo_n56r9_route7_hdmi_c140) | 1 | 643.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route8_hdmi_c150](../../../tang/impl/console_neo_n56r9_route8_hdmi_c150) | 1 | 645.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_route9_dma_c150](../../../tang/impl/console_neo_n56r9_route9_dma_c150) | 1 | 645.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n56r9_scan_observer](../../../tang/impl/console_neo_n56r9_scan_observer) | 0 | 29.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n57_usb35_r0](../../../tang/impl/console_neo_n57_usb35_r0) | 0 | 30.1 Mio | Conservé : dépendance ou référence |
| [console_neo_n57_usb35_r1](../../../tang/impl/console_neo_n57_usb35_r1) | 1 | 641.0 Mio | Conservé : dépendance ou référence |
| [console_neo_n57_usb35_syn](../../../tang/impl/console_neo_n57_usb35_syn) | 0 | 29.4 Mio | Conservé : dépendance ou référence |
| [console_neo_n5r1](../../../tang/impl/console_neo_n5r1) | 1 | 228.2 Mio | Historique, sources et rapports conservés |
| [console_neo_n6](../../../tang/impl/console_neo_n6) | 0 | 22.7 Mio | Conservé : dépendance ou référence |
| [console_neo_n6r1](../../../tang/impl/console_neo_n6r1) | 1 | 228.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n7](../../../tang/impl/console_neo_n7) | 1 | 241.5 Mio | Conservé : dépendance ou référence |
| [console_neo_n7r1](../../../tang/impl/console_neo_n7r1) | 1 | 230.7 Mio | Historique, sources et rapports conservés |
| [console_neo_n8](../../../tang/impl/console_neo_n8) | 0 | 22.8 Mio | Conservé : dépendance ou référence |
| [console_neo_n8r1](../../../tang/impl/console_neo_n8r1) | 1 | 231.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n8r2](../../../tang/impl/console_neo_n8r2) | 1 | 231.6 Mio | Historique, sources et rapports conservés |
| [console_neo_n9](../../../tang/impl/console_neo_n9) | 0 | 73.8 Mio | Historique, sources et rapports conservés |
| [neo_ddr6_300_ip_r0](../../../tang/impl/neo_ddr6_300_ip_r0) | 0 | 11.1 Mio | Historique, sources et rapports conservés |
| [neo_ddr6_325_ip_r0](../../../tang/impl/neo_ddr6_325_ip_r0) | 0 | 11.2 Mio | Historique, sources et rapports conservés |
| [neo_ddr6_400_ip_r0](../../../tang/impl/neo_ddr6_400_ip_r0) | 0 | 10.9 Mio | Historique, sources et rapports conservés |
| [neo_ddr6_ip_r0](../../../tang/impl/neo_ddr6_ip_r0) | 0 | 1.3 Mio | Historique, sources et rapports conservés |
| [neo_ddr6_ip_r1](../../../tang/impl/neo_ddr6_ip_r1) | 0 | 10.9 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_auto](../../../tang/impl/neo_reset_jtag_auto) | 0 | 1.3 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_auto_newide](../../../tang/impl/neo_reset_jtag_auto_newide) | 1 | 54.1 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_auto_r1](../../../tang/impl/neo_reset_jtag_auto_r1) | 1 | 53.7 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_local](../../../tang/impl/neo_reset_jtag_local) | 0 | 1.3 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_local_newide](../../../tang/impl/neo_reset_jtag_local_newide) | 1 | 54.1 Mio | Historique, sources et rapports conservés |
| [neo_reset_jtag_local_r1](../../../tang/impl/neo_reset_jtag_local_r1) | 1 | 53.7 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto](../../../tang/impl/neo_reset_probe_auto) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto_newide](../../../tang/impl/neo_reset_probe_auto_newide) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto_newide_r1](../../../tang/impl/neo_reset_probe_auto_newide_r1) | 1 | 53.9 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto_r1](../../../tang/impl/neo_reset_probe_auto_r1) | 1 | 53.6 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto_r2](../../../tang/impl/neo_reset_probe_auto_r2) | 1 | 53.5 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_auto_r3](../../../tang/impl/neo_reset_probe_auto_r3) | 1 | 53.5 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_local](../../../tang/impl/neo_reset_probe_local) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_local_r1](../../../tang/impl/neo_reset_probe_local_r1) | 1 | 53.6 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_local_r2](../../../tang/impl/neo_reset_probe_local_r2) | 1 | 53.5 Mio | Historique, sources et rapports conservés |
| [neo_reset_probe_local_r3](../../../tang/impl/neo_reset_probe_local_r3) | 1 | 53.5 Mio | Historique, sources et rapports conservés |
