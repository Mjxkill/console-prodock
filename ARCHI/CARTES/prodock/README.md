# Tang Mega Pro Dock 138K

Sortie LCD 800×480. La référence FPGA G22r0 et le paquet NEBULA R17 restent protégés ; le jeu courant est un candidat logiciel distinct.

[Retour à la carte du dépôt](../README.md)

Catalogue détaillé : [catalogue.json](catalogue.json).

Les [sources communes](../commun/README.md) complètent cette liste.

- [Empreintes et fichiers protégés](../../../tang/boards/prodock/reference.json)
- [Restauration matérielle de référence](../../../TESTS/prodock_restore_20261021/README.md)
- [Jeu en cours de refonte](../../../games/luma3d/candidates/arcade_polish_r1/PLAN.md)

## 161 entrées de développement

| Fichier unique | Type |
|---|---|
| [fw_console/Makefile](../../../fw_console/Makefile) | build |
| [fw_console/astra.ld](../../../fw_console/astra.ld) | source |
| [fw_console/astra_assets.h](../../../fw_console/astra_assets.h) | source |
| [fw_console/astra_main.c](../../../fw_console/astra_main.c) | source |
| [fw_console/astra_scene.h](../../../fw_console/astra_scene.h) | source |
| [fw_console/astrilla.ld](../../../fw_console/astrilla.ld) | source |
| [fw_console/astrilla_3d.h](../../../fw_console/astrilla_3d.h) | source |
| [fw_console/astrilla_assets.h](../../../fw_console/astrilla_assets.h) | source |
| [fw_console/astrilla_flight.h](../../../fw_console/astrilla_flight.h) | source |
| [fw_console/astrilla_geometry.h](../../../fw_console/astrilla_geometry.h) | source |
| [fw_console/astrilla_hud.h](../../../fw_console/astrilla_hud.h) | source |
| [fw_console/astrilla_hud_font.h](../../../fw_console/astrilla_hud_font.h) | source |
| [fw_console/astrilla_main.c](../../../fw_console/astrilla_main.c) | source |
| [fw_console/astrilla_meshes.h](../../../fw_console/astrilla_meshes.h) | source |
| [fw_console/astrilla_scene.h](../../../fw_console/astrilla_scene.h) | source |
| [fw_console/demo/demo_led.S](../../../fw_console/demo/demo_led.S) | source |
| [fw_console/demo/itcm/itcm0](../../../fw_console/demo/itcm/itcm0) | source |
| [fw_console/demo/itcm/itcm1](../../../fw_console/demo/itcm/itcm1) | source |
| [fw_console/demo/itcm/itcm2](../../../fw_console/demo/itcm/itcm2) | source |
| [fw_console/demo/itcm/itcm3](../../../fw_console/demo/itcm/itcm3) | source |
| [fw_console/gpu_3d_demo.h](../../../fw_console/gpu_3d_demo.h) | source |
| [fw_console/gpu_3d_scene.h](../../../fw_console/gpu_3d_scene.h) | source |
| [fw_console/gpu_affine_demo.h](../../../fw_console/gpu_affine_demo.h) | source |
| [fw_console/gpu_affine_scene.h](../../../fw_console/gpu_affine_scene.h) | source |
| [fw_console/gpu_demo.h](../../../fw_console/gpu_demo.h) | source |
| [fw_console/gpu_diag.c](../../../fw_console/gpu_diag.c) | source |
| [fw_console/gpu_layers_demo.h](../../../fw_console/gpu_layers_demo.h) | source |
| [fw_console/gpu_palette.h](../../../fw_console/gpu_palette.h) | source |
| [fw_console/gpu_raster_demo.h](../../../fw_console/gpu_raster_demo.h) | source |
| [fw_console/gpu_raster_reference.h](../../../fw_console/gpu_raster_reference.h) | source |
| [fw_console/gpu_raster_scene.h](../../../fw_console/gpu_raster_scene.h) | source |
| [fw_console/gpu_rgb_overlay_scene.h](../../../fw_console/gpu_rgb_overlay_scene.h) | source |
| [fw_console/gpu_sprites_demo.h](../../../fw_console/gpu_sprites_demo.h) | source |
| [fw_console/gpu_tiles_demo.h](../../../fw_console/gpu_tiles_demo.h) | source |
| [fw_console/gpu_tiles_scene.h](../../../fw_console/gpu_tiles_scene.h) | source |
| [fw_console/gpu_v1_demo.h](../../../fw_console/gpu_v1_demo.h) | source |
| [fw_console/gpu_v1_expected.h](../../../fw_console/gpu_v1_expected.h) | source |
| [fw_console/gpu_v1_scene.h](../../../fw_console/gpu_v1_scene.h) | source |
| [fw_console/itcm.ld](../../../fw_console/itcm.ld) | source |
| [fw_console/itcm_all.ld](../../../fw_console/itcm_all.ld) | source |
| [fw_console/luma.ld](../../../fw_console/luma.ld) | source |
| [fw_console/luma_assets.h](../../../fw_console/luma_assets.h) | source |
| [fw_console/luma_fx_scene.h](../../../fw_console/luma_fx_scene.h) | source |
| [fw_console/luma_main.c](../../../fw_console/luma_main.c) | source |
| [fw_console/luma_scene.h](../../../fw_console/luma_scene.h) | source |
| [fw_console/main.c](../../../fw_console/main.c) | source |
| [fw_console/mini/mini.ld](../../../fw_console/mini/mini.ld) | source |
| [fw_console/mini/mini_boot.S](../../../fw_console/mini/mini_boot.S) | source |
| [fw_console/mini/mini_uart.S](../../../fw_console/mini/mini_uart.S) | source |
| [fw_console/mini/mini_wfi.S](../../../fw_console/mini/mini_wfi.S) | source |
| [fw_console/orbital.ld](../../../fw_console/orbital.ld) | source |
| [fw_console/orbital_assets.h](../../../fw_console/orbital_assets.h) | source |
| [fw_console/orbital_main.c](../../../fw_console/orbital_main.c) | source |
| [fw_console/orbital_scene.h](../../../fw_console/orbital_scene.h) | source |
| [fw_console/racer_demo.h](../../../fw_console/racer_demo.h) | source |
| [fw_console/racer_scene.h](../../../fw_console/racer_scene.h) | source |
| [fw_console/sd_probe_main.c](../../../fw_console/sd_probe_main.c) | source |
| [fw_console/sd_test_main.c](../../../fw_console/sd_test_main.c) | source |
| [fw_console/usb_disk_main.c](../../../fw_console/usb_disk_main.c) | source |
| [fw_console/world3d_main.c](../../../fw_console/world3d_main.c) | source |
| [fw_console/world3d_scene.h](../../../fw_console/world3d_scene.h) | source |
| [linux/prodock-linux.dts](../../../linux/prodock-linux.dts) | source |
| [tang/build_gpu.tcl](../../../tang/build_gpu.tcl) | source |
| [tang/constr/ae350_e2.cst](../../../tang/constr/ae350_e2.cst) | constraint |
| [tang/constr/ae350_e2.sdc](../../../tang/constr/ae350_e2.sdc) | constraint |
| [tang/constr/console_e0b.cst](../../../tang/constr/console_e0b.cst) | constraint |
| [tang/constr/console_e0b.sdc](../../../tang/constr/console_e0b.sdc) | constraint |
| [tang/constr/console_e0b_usbonly.sdc](../../../tang/constr/console_e0b_usbonly.sdc) | constraint |
| [tang/constr/ddr_e1.cst](../../../tang/constr/ddr_e1.cst) | constraint |
| [tang/constr/ddr_e1.sdc](../../../tang/constr/ddr_e1.sdc) | constraint |
| [tang/constr/ddr_e1_cdc.cst](../../../tang/constr/ddr_e1_cdc.cst) | constraint |
| [tang/constr/e1_noddr.cst](../../../tang/constr/e1_noddr.cst) | constraint |
| [tang/constr/e1_noddr.sdc](../../../tang/constr/e1_noddr.sdc) | constraint |
| [tang/constr/gpu.cst](../../../tang/constr/gpu.cst) | constraint |
| [tang/constr/gpu.sdc](../../../tang/constr/gpu.sdc) | constraint |
| [tang/constr/gpu_usb_first.cst](../../../tang/constr/gpu_usb_first.cst) | constraint |
| [tang/constr/gpu_usb_fs.cst](../../../tang/constr/gpu_usb_fs.cst) | constraint |
| [tang/constr/prodock_softusb_placement.cst](../../../tang/constr/prodock_softusb_placement.cst) | constraint |
| [tang/constr/usb_ref_part.cst](../../../tang/constr/usb_ref_part.cst) | constraint |
| [tang/rtl/ae350/ae350_soc.v](../../../tang/rtl/ae350/ae350_soc.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.ipc](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.ipc) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.vo](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.vo) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface_tmp.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface_tmp.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.ipc](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.ipc) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.vo](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.vo) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo_tmp.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo_tmp.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.ipc](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.ipc) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.v) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.vo](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.vo) | source |
| [tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo_tmp.v](../../../tang/rtl/ae350/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo_tmp.v) | source |
| [tang/rtl/ae350/ddr3_memory/gw_ahb_ddr3.v](../../../tang/rtl/ae350/ddr3_memory/gw_ahb_ddr3.v) | source |
| [tang/rtl/ae350/key_debounce.v](../../../tang/rtl/ae350/key_debounce.v) | source |
| [tang/rtl/ae350/pll_ae350/gowin_pll_ae350.ipc](../../../tang/rtl/ae350/pll_ae350/gowin_pll_ae350.ipc) | source |
| [tang/rtl/ae350/pll_ae350/gowin_pll_ae350.mod](../../../tang/rtl/ae350/pll_ae350/gowin_pll_ae350.mod) | source |
| [tang/rtl/ae350/pll_ae350/gowin_pll_ae350_tmp.v](../../../tang/rtl/ae350/pll_ae350/gowin_pll_ae350_tmp.v) | source |
| [tang/rtl/ae350/pll_ae350/pll_init.v](../../../tang/rtl/ae350/pll_ae350/pll_init.v) | source |
| [tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.ipc](../../../tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.ipc) | source |
| [tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.mod](../../../tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.mod) | source |
| [tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.v](../../../tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3.v) | source |
| [tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3_tmp.v](../../../tang/rtl/ae350/pll_ddr3/gowin_pll_ddr3_tmp.v) | source |
| [tang/rtl/ae350/soc/riscv_ae350_soc.ipc](../../../tang/rtl/ae350/soc/riscv_ae350_soc.ipc) | source |
| [tang/rtl/ae350/soc/riscv_ae350_soc.v](../../../tang/rtl/ae350/soc/riscv_ae350_soc.v) | source |
| [tang/rtl/ae350/soc/riscv_ae350_soc.vo](../../../tang/rtl/ae350/soc/riscv_ae350_soc.vo) | source |
| [tang/rtl/ae350/soc/riscv_ae350_soc_tmp.v](../../../tang/rtl/ae350/soc/riscv_ae350_soc_tmp.v) | source |
| [tang/rtl/board/cfg/gw_dtcm_config.v](../../../tang/rtl/board/cfg/gw_dtcm_config.v) | source |
| [tang/rtl/board/cfg/gw_itcm_config.v](../../../tang/rtl/board/cfg/gw_itcm_config.v) | source |
| [tang/rtl/board/cfg/gwmc_param.v](../../../tang/rtl/board/cfg/gwmc_param.v) | source |
| [tang/rtl/board/cfg/riscv_ae350_config.v](../../../tang/rtl/board/cfg/riscv_ae350_config.v) | source |
| [tang/rtl/board/cfg/riscv_ae350_config.v.avec_exts](../../../tang/rtl/board/cfg/riscv_ae350_config.v.avec_exts) | source |
| [tang/rtl/board/cfg/riscv_ae350_config.v.e1_sans_exts](../../../tang/rtl/board/cfg/riscv_ae350_config.v.e1_sans_exts) | source |
| [tang/rtl/board/cfg/riscv_ae350_soc.prj](../../../tang/rtl/board/cfg/riscv_ae350_soc.prj) | source |
| [tang/rtl/board/cfg/riscv_ae350_soc_tmp.v](../../../tang/rtl/board/cfg/riscv_ae350_soc_tmp.v) | source |
| [tang/rtl/board/ddr3_standalone/cfg/DDR3_define.v](../../../tang/rtl/board/ddr3_standalone/cfg/DDR3_define.v) | source |
| [tang/rtl/board/ddr3_standalone/cfg/ddr3.prj](../../../tang/rtl/board/ddr3_standalone/cfg/ddr3.prj) | source |
| [tang/rtl/board/ddr3_standalone/cfg/ddr3_name.v](../../../tang/rtl/board/ddr3_standalone/cfg/ddr3_name.v) | source |
| [tang/rtl/board/ddr3_standalone/cfg/ddr3_standalone_tmp.v](../../../tang/rtl/board/ddr3_standalone/cfg/ddr3_standalone_tmp.v) | source |
| [tang/rtl/board/ddr3_standalone/cfg/gwmc_param.v](../../../tang/rtl/board/ddr3_standalone/cfg/gwmc_param.v) | source |
| [tang/rtl/board/ddr3_standalone/ddr3_standalone.v](../../../tang/rtl/board/ddr3_standalone/ddr3_standalone.v) | source |
| [tang/rtl/board/ddr3_standalone_32b/cfg/gwmc_param.v](../../../tang/rtl/board/ddr3_standalone_32b/cfg/gwmc_param.v) | source |
| [tang/rtl/board/riscv_ae350_soc.v](../../../tang/rtl/board/riscv_ae350_soc.v) | source |
| [tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v.avec_exts](../../../tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v.avec_exts) | source |
| [tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v.e1_sans_exts](../../../tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v.e1_sans_exts) | source |
| [tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_soc_tmp.v](../../../tang/rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_soc_tmp.v) | source |
| [tang/rtl/console_e0b_plonly.v](../../../tang/rtl/console_e0b_plonly.v) | source |
| [tang/rtl/console_e0b_usbonly.v](../../../tang/rtl/console_e0b_usbonly.v) | source |
| [tang/rtl/console_gpu.v](../../../tang/rtl/console_gpu.v) | source |
| [tang/rtl/console_gpu_usb_fs.v](../../../tang/rtl/console_gpu_usb_fs.v) | source |
| [tang/rtl/console_top.v](../../../tang/rtl/console_top.v) | source |
| [tang/rtl/console_top_noddr.v](../../../tang/rtl/console_top_noddr.v) | source |
| [tang/rtl/console_usb_diag.v](../../../tang/rtl/console_usb_diag.v) | source |
| [tang/rtl/console_usb_first.v](../../../tang/rtl/console_usb_first.v) | source |
| [tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.ipc](../../../tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.ipc) | source |
| [tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.v](../../../tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.v) | source |
| [tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.vo](../../../tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.vo) | source |
| [tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface_tmp.v](../../../tang/rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface_tmp.v) | source |
| [tang/rtl/ddrtest/ddr3_test.v](../../../tang/rtl/ddrtest/ddr3_test.v) | source |
| [tang/rtl/ddrtest/ddr_test_cdc.v](../../../tang/rtl/ddrtest/ddr_test_cdc.v) | source |
| [tang/rtl/ddrtest/ddr_test_loop.v](../../../tang/rtl/ddrtest/ddr_test_loop.v) | source |
| [tang/rtl/ddrtest/fifo.v](../../../tang/rtl/ddrtest/fifo.v) | source |
| [tang/rtl/ddrtest/gowin_pll/gowin_pll.ipc](../../../tang/rtl/ddrtest/gowin_pll/gowin_pll.ipc) | source |
| [tang/rtl/ddrtest/gowin_pll/gowin_pll.mod](../../../tang/rtl/ddrtest/gowin_pll/gowin_pll.mod) | source |
| [tang/rtl/ddrtest/gowin_pll/gowin_pll.v](../../../tang/rtl/ddrtest/gowin_pll/gowin_pll.v) | source |
| [tang/rtl/ddrtest/gowin_pll/gowin_pll_tmp.v](../../../tang/rtl/ddrtest/gowin_pll/gowin_pll_tmp.v) | source |
| [tang/rtl/ddrtest/uart_tx.v](../../../tang/rtl/ddrtest/uart_tx.v) | source |
| [tang/rtl/usb/fs_phy/usb_softphy.ipc](../../../tang/rtl/usb/fs_phy/usb_softphy.ipc) | source |
| [tang/rtl/usb/fs_phy/usb_softphy.v](../../../tang/rtl/usb/fs_phy/usb_softphy.v) | source |
| [tang/rtl/usb/fs_phy/usb_softphy_tmp.v](../../../tang/rtl/usb/fs_phy/usb_softphy_tmp.v) | source |
| [tang/rtl/usb/gowin_pll.mod](../../../tang/rtl/usb/gowin_pll.mod) | source |
| [tang/rtl/usb/gowin_pll_b.ipc](../../../tang/rtl/usb/gowin_pll_b.ipc) | source |
| [tang/rtl/usb/gowin_pll_f.ipc](../../../tang/rtl/usb/gowin_pll_f.ipc) | source |
| [tang/rtl/usb/integer_division/integer_division.ipc](../../../tang/rtl/usb/integer_division/integer_division.ipc) | source |
| [tang/rtl/usb/integer_division/integer_division.vo](../../../tang/rtl/usb/integer_division/integer_division.vo) | source |
| [tang/rtl/usb/integer_division/integer_division_tmp.v](../../../tang/rtl/usb/integer_division/integer_division_tmp.v) | source |
| [tang/rtl/usb/uart/usb_uart_config.v.bak](../../../tang/rtl/usb/uart/usb_uart_config.v.bak) | source |
| [tang/rtl/video/gowin_pll_lcd.v](../../../tang/rtl/video/gowin_pll_lcd.v) | source |
| [tang/rtl/video/lcd_timing.v](../../../tang/rtl/video/lcd_timing.v) | source |
| [tools/build_gpu.py](../../../tools/build_gpu.py) | build |
| [tools/build_gpu_geometry.py](../../../tools/build_gpu_geometry.py) | build |
| [tools/reroute_gpu.py](../../../tools/reroute_gpu.py) | build |

## 270 dossiers de construction

Les chemins historiques restent en place : les scripts, Tcl et preuves les référencent. Les déplacer sans migration de ces dépendances casserait la reproductibilité.

| Snapshot | FS conservés | Taille après nettoyage | Protection / état |
|---|---:|---:|---|
| [gpu_dual_prodock_p1](../../../tang/impl/gpu_dual_prodock_p1) | 0 | 39.2 Mio | Historique, sources et rapports conservés |
| [gpu_dual_prodock_p1r1](../../../tang/impl/gpu_dual_prodock_p1r1) | 1 | 335.0 Mio | Historique, sources et rapports conservés |
| [gpu_dual_prodock_p2](../../../tang/impl/gpu_dual_prodock_p2) | 0 | 112.2 Mio | Historique, sources et rapports conservés |
| [gpu_dual_prodock_p3](../../../tang/impl/gpu_dual_prodock_p3) | 1 | 310.2 Mio | Historique, sources et rapports conservés |
| [gpu_dual_prodock_p4](../../../tang/impl/gpu_dual_prodock_p4) | 0 | 102.2 Mio | Historique, sources et rapports conservés |
| [gpu_fast_r1](../../../tang/impl/gpu_fast_r1) | 1 | 55.9 Mio | Historique, sources et rapports conservés |
| [gpu_fast_r2](../../../tang/impl/gpu_fast_r2) | 1 | 55.4 Mio | Historique, sources et rapports conservés |
| [gpu_g0](../../../tang/impl/gpu_g0) | 0 | 6.4 Mio | Historique, sources et rapports conservés |
| [gpu_g1](../../../tang/impl/gpu_g1) | 0 | 4.9 Mio | Historique, sources et rapports conservés |
| [gpu_g1_r2](../../../tang/impl/gpu_g1_r2) | 0 | 11.0 Mio | Historique, sources et rapports conservés |
| [gpu_g1_r3](../../../tang/impl/gpu_g1_r3) | 1 | 49.3 Mio | Historique, sources et rapports conservés |
| [gpu_g2_r1](../../../tang/impl/gpu_g2_r1) | 1 | 51.3 Mio | Historique, sources et rapports conservés |
| [gpu_g2_r2](../../../tang/impl/gpu_g2_r2) | 0 | 12.5 Mio | Historique, sources et rapports conservés |
| [gpu_g2_r3](../../../tang/impl/gpu_g2_r3) | 1 | 51.2 Mio | Historique, sources et rapports conservés |
| [gpu_g2_ramps](../../../tang/impl/gpu_g2_ramps) | 1 | 51.2 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r1](../../../tang/impl/gpu_g3_r1) | 1 | 51.6 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r2](../../../tang/impl/gpu_g3_r2) | 0 | 13.3 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r3](../../../tang/impl/gpu_g3_r3) | 0 | 13.5 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r4](../../../tang/impl/gpu_g3_r4) | 0 | 13.7 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r5](../../../tang/impl/gpu_g3_r5) | 0 | 13.6 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r6](../../../tang/impl/gpu_g3_r6) | 0 | 13.4 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r7](../../../tang/impl/gpu_g3_r7) | 0 | 13.3 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r8](../../../tang/impl/gpu_g3_r8) | 0 | 13.3 Mio | Historique, sources et rapports conservés |
| [gpu_g3_r9](../../../tang/impl/gpu_g3_r9) | 1 | 52.0 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r1](../../../tang/impl/gpu_g4_r1) | 1 | 54.3 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r10](../../../tang/impl/gpu_g4_r10) | 1 | 53.6 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r11](../../../tang/impl/gpu_g4_r11) | 1 | 53.6 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r12](../../../tang/impl/gpu_g4_r12) | 1 | 53.7 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r2](../../../tang/impl/gpu_g4_r2) | 1 | 53.3 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r3](../../../tang/impl/gpu_g4_r3) | 1 | 53.3 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r4](../../../tang/impl/gpu_g4_r4) | 1 | 53.4 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r5](../../../tang/impl/gpu_g4_r5) | 1 | 53.2 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r6](../../../tang/impl/gpu_g4_r6) | 1 | 53.3 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r7](../../../tang/impl/gpu_g4_r7) | 0 | 13.0 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r8](../../../tang/impl/gpu_g4_r8) | 1 | 53.4 Mio | Historique, sources et rapports conservés |
| [gpu_g4_r9](../../../tang/impl/gpu_g4_r9) | 1 | 53.7 Mio | Historique, sources et rapports conservés |
| [gpu_g5_r1](../../../tang/impl/gpu_g5_r1) | 1 | 54.6 Mio | Historique, sources et rapports conservés |
| [gpu_g5_r2](../../../tang/impl/gpu_g5_r2) | 1 | 54.5 Mio | Historique, sources et rapports conservés |
| [gpu_g5_r3](../../../tang/impl/gpu_g5_r3) | 1 | 54.5 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g1](../../../tang/impl/gpu_geometry_g1) | 0 | 15.3 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g10](../../../tang/impl/gpu_geometry_g10) | 0 | 111.6 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g11](../../../tang/impl/gpu_geometry_g11) | 0 | 112.3 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g12](../../../tang/impl/gpu_geometry_g12) | 0 | 50.0 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g13](../../../tang/impl/gpu_geometry_g13) | 1 | 334.7 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g14](../../../tang/impl/gpu_geometry_g14) | 1 | 333.2 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g15](../../../tang/impl/gpu_geometry_g15) | 1 | 332.2 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g16](../../../tang/impl/gpu_geometry_g16) | 0 | 101.7 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g16p4](../../../tang/impl/gpu_geometry_g16p4) | 0 | 102.9 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g16r](../../../tang/impl/gpu_geometry_g16r) | 0 | 102.9 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g17](../../../tang/impl/gpu_geometry_g17) | 0 | 103.2 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g18](../../../tang/impl/gpu_geometry_g18) | 0 | 103.2 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g18a1](../../../tang/impl/gpu_geometry_g18a1) | 0 | 103.0 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g19](../../../tang/impl/gpu_geometry_g19) | 1 | 335.0 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g2](../../../tang/impl/gpu_geometry_g2) | 0 | 108.3 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g20](../../../tang/impl/gpu_geometry_g20) | 0 | 100.5 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g21](../../../tang/impl/gpu_geometry_g21) | 1 | 335.7 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g22](../../../tang/impl/gpu_geometry_g22) | 0 | 39.3 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g22r](../../../tang/impl/gpu_geometry_g22r) | 0 | 101.7 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g22r0](../../../tang/impl/gpu_geometry_g22r0) | 1 | 626.1 Mio | Référence historique Pro Dock protégée. Setup −0,564 ns ; limites USB documentées. Le statut référence ne vaut pas timing PASS. |
| [gpu_geometry_g3](../../../tang/impl/gpu_geometry_g3) | 1 | 292.2 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g4](../../../tang/impl/gpu_geometry_g4) | 0 | 38.8 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g5](../../../tang/impl/gpu_geometry_g5) | 1 | 268.5 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g6](../../../tang/impl/gpu_geometry_g6) | 1 | 269.7 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g7](../../../tang/impl/gpu_geometry_g7) | 0 | 98.6 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g8](../../../tang/impl/gpu_geometry_g8) | 1 | 273.4 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g8i](../../../tang/impl/gpu_geometry_g8i) | 1 | 282.0 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g8p](../../../tang/impl/gpu_geometry_g8p) | 0 | 109.8 Mio | Historique, sources et rapports conservés |
| [gpu_geometry_g9](../../../tang/impl/gpu_geometry_g9) | 0 | 109.6 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r1](../../../tang/impl/gpu_l11_r1) | 0 | 15.5 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r10](../../../tang/impl/gpu_l11_r10) | 0 | 16.9 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r11](../../../tang/impl/gpu_l11_r11) | 0 | 18.5 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r12](../../../tang/impl/gpu_l11_r12) | 0 | 16.7 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r13](../../../tang/impl/gpu_l11_r13) | 0 | 16.7 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r14](../../../tang/impl/gpu_l11_r14) | 1 | 57.0 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r2](../../../tang/impl/gpu_l11_r2) | 0 | 16.8 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r3](../../../tang/impl/gpu_l11_r3) | 0 | 16.9 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r4](../../../tang/impl/gpu_l11_r4) | 0 | 15.5 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r5](../../../tang/impl/gpu_l11_r5) | 0 | 16.7 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r6](../../../tang/impl/gpu_l11_r6) | 0 | 15.5 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r7](../../../tang/impl/gpu_l11_r7) | 0 | 16.7 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r8](../../../tang/impl/gpu_l11_r8) | 0 | 16.6 Mio | Historique, sources et rapports conservés |
| [gpu_l11_r9](../../../tang/impl/gpu_l11_r9) | 0 | 16.8 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r1](../../../tang/impl/gpu_l11_usb_r1) | 1 | 56.8 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r10](../../../tang/impl/gpu_l11_usb_r10) | 1 | 56.9 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r11](../../../tang/impl/gpu_l11_usb_r11) | 1 | 57.1 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r12](../../../tang/impl/gpu_l11_usb_r12) | 1 | 57.2 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r13](../../../tang/impl/gpu_l11_usb_r13) | 1 | 57.1 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r2](../../../tang/impl/gpu_l11_usb_r2) | 1 | 56.6 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r3](../../../tang/impl/gpu_l11_usb_r3) | 1 | 56.7 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r4](../../../tang/impl/gpu_l11_usb_r4) | 1 | 57.1 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r5](../../../tang/impl/gpu_l11_usb_r5) | 1 | 56.9 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r6](../../../tang/impl/gpu_l11_usb_r6) | 1 | 57.0 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r7](../../../tang/impl/gpu_l11_usb_r7) | 1 | 56.9 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r8](../../../tang/impl/gpu_l11_usb_r8) | 1 | 57.0 Mio | Historique, sources et rapports conservés |
| [gpu_l11_usb_r9](../../../tang/impl/gpu_l11_usb_r9) | 1 | 57.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r10](../../../tang/impl/gpu_l12_diag_r10) | 0 | 16.3 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r11](../../../tang/impl/gpu_l12_diag_r11) | 1 | 57.6 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r12](../../../tang/impl/gpu_l12_diag_r12) | 1 | 57.6 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r13](../../../tang/impl/gpu_l12_diag_r13) | 1 | 57.5 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r14](../../../tang/impl/gpu_l12_diag_r14) | 1 | 58.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r15](../../../tang/impl/gpu_l12_diag_r15) | 1 | 57.7 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r16](../../../tang/impl/gpu_l12_diag_r16) | 1 | 57.5 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r17](../../../tang/impl/gpu_l12_diag_r17) | 1 | 57.6 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r18](../../../tang/impl/gpu_l12_diag_r18) | 0 | 17.8 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r19](../../../tang/impl/gpu_l12_diag_r19) | 1 | 62.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r20](../../../tang/impl/gpu_l12_diag_r20) | 1 | 58.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r21_fs](../../../tang/impl/gpu_l12_diag_r21_fs) | 1 | 58.7 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r22_fs](../../../tang/impl/gpu_l12_diag_r22_fs) | 1 | 59.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r23_fs](../../../tang/impl/gpu_l12_diag_r23_fs) | 1 | 68.7 Mio | Conservé : dépendance ou référence |
| [gpu_l12_diag_r24](../../../tang/impl/gpu_l12_diag_r24) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r25](../../../tang/impl/gpu_l12_diag_r25) | 1 | 57.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r26](../../../tang/impl/gpu_l12_diag_r26) | 1 | 58.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r27](../../../tang/impl/gpu_l12_diag_r27) | 0 | 18.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r28](../../../tang/impl/gpu_l12_diag_r28) | 1 | 57.8 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r29](../../../tang/impl/gpu_l12_diag_r29) | 1 | 268.8 Mio | Conservé : dépendance ou référence |
| [gpu_l12_diag_r30](../../../tang/impl/gpu_l12_diag_r30) | 1 | 58.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r31](../../../tang/impl/gpu_l12_diag_r31) | 0 | 17.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r32](../../../tang/impl/gpu_l12_diag_r32) | 0 | 17.8 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r7](../../../tang/impl/gpu_l12_diag_r7) | 1 | 57.6 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r8](../../../tang/impl/gpu_l12_diag_r8) | 1 | 57.6 Mio | Historique, sources et rapports conservés |
| [gpu_l12_diag_r9](../../../tang/impl/gpu_l12_diag_r9) | 1 | 57.5 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r1](../../../tang/impl/gpu_l12_r1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r2](../../../tang/impl/gpu_l12_r2) | 1 | 57.2 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r3](../../../tang/impl/gpu_l12_r3) | 1 | 57.3 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r4](../../../tang/impl/gpu_l12_r4) | 1 | 57.5 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r5](../../../tang/impl/gpu_l12_r5) | 1 | 57.2 Mio | Historique, sources et rapports conservés |
| [gpu_l12_r6](../../../tang/impl/gpu_l12_r6) | 1 | 57.4 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_cdc_r1](../../../tang/impl/gpu_l12_usb_hs33_cdc_r1) | 1 | 59.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_cdc_r2](../../../tang/impl/gpu_l12_usb_hs33_cdc_r2) | 1 | 60.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_cdc_r3](../../../tang/impl/gpu_l12_usb_hs33_cdc_r3) | 1 | 60.4 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_cdc_r4](../../../tang/impl/gpu_l12_usb_hs33_cdc_r4) | 1 | 353.3 Mio | Conservé : dépendance ou référence |
| [gpu_l12_usb_hs33_ep0_r1](../../../tang/impl/gpu_l12_usb_hs33_ep0_r1) | 0 | 19.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_ep0_r2](../../../tang/impl/gpu_l12_usb_hs33_ep0_r2) | 1 | 60.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_ep0_r3](../../../tang/impl/gpu_l12_usb_hs33_ep0_r3) | 1 | 60.3 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_idle_r1](../../../tang/impl/gpu_l12_usb_hs33_idle_r1) | 1 | 149.7 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_idle_r2](../../../tang/impl/gpu_l12_usb_hs33_idle_r2) | 1 | 149.9 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_idle_r3](../../../tang/impl/gpu_l12_usb_hs33_idle_r3) | 1 | 366.8 Mio | Conservé : dépendance ou référence |
| [gpu_l12_usb_hs33_lock2ms_r1](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_lock2ms_r2](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r2) | 1 | 60.2 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_lock2ms_r3](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r3) | 0 | 20.4 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_lock2ms_r4](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r4) | 1 | 60.1 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_lock2ms_r5](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r5) | 1 | 60.2 Mio | Historique, sources et rapports conservés |
| [gpu_l12_usb_hs33_lock2ms_r6](../../../tang/impl/gpu_l12_usb_hs33_lock2ms_r6) | 1 | 60.0 Mio | Historique, sources et rapports conservés |
| [gpu_l1315_r1](../../../tang/impl/gpu_l1315_r1) | 1 | 169.3 Mio | Historique, sources et rapports conservés |
| [gpu_l1315_r2](../../../tang/impl/gpu_l1315_r2) | 1 | 169.4 Mio | Historique, sources et rapports conservés |
| [gpu_l1315_r3](../../../tang/impl/gpu_l1315_r3) | 1 | 169.6 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r1](../../../tang/impl/gpu_perspective_r1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r10](../../../tang/impl/gpu_perspective_r10) | 1 | 177.4 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r2](../../../tang/impl/gpu_perspective_r2) | 0 | 23.9 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r3](../../../tang/impl/gpu_perspective_r3) | 1 | 179.7 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r4](../../../tang/impl/gpu_perspective_r4) | 1 | 177.8 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r5](../../../tang/impl/gpu_perspective_r5) | 1 | 178.2 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r6](../../../tang/impl/gpu_perspective_r6) | 1 | 177.6 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r7](../../../tang/impl/gpu_perspective_r7) | 1 | 178.3 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r8](../../../tang/impl/gpu_perspective_r8) | 1 | 176.4 Mio | Historique, sources et rapports conservés |
| [gpu_perspective_r9](../../../tang/impl/gpu_perspective_r9) | 1 | 176.9 Mio | Historique, sources et rapports conservés |
| [gpu_racer_r1](../../../tang/impl/gpu_racer_r1) | 1 | 54.8 Mio | Historique, sources et rapports conservés |
| [gpu_racer_r2](../../../tang/impl/gpu_racer_r2) | 1 | 54.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c1](../../../tang/impl/gpu_sdusb_c1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c10](../../../tang/impl/gpu_sdusb_c10) | 1 | 233.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c11](../../../tang/impl/gpu_sdusb_c11) | 0 | 7.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c12](../../../tang/impl/gpu_sdusb_c12) | 0 | 7.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c13](../../../tang/impl/gpu_sdusb_c13) | 1 | 230.2 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c14](../../../tang/impl/gpu_sdusb_c14) | 1 | 229.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c15](../../../tang/impl/gpu_sdusb_c15) | 1 | 229.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c16](../../../tang/impl/gpu_sdusb_c16) | 0 | 29.0 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c17](../../../tang/impl/gpu_sdusb_c17) | 1 | 229.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c18](../../../tang/impl/gpu_sdusb_c18) | 1 | 230.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c19](../../../tang/impl/gpu_sdusb_c19) | 1 | 230.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c1b](../../../tang/impl/gpu_sdusb_c1b) | 1 | 230.5 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c2](../../../tang/impl/gpu_sdusb_c2) | 1 | 230.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c20](../../../tang/impl/gpu_sdusb_c20) | 1 | 230.9 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c21](../../../tang/impl/gpu_sdusb_c21) | 1 | 230.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c22](../../../tang/impl/gpu_sdusb_c22) | 1 | 231.1 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c23](../../../tang/impl/gpu_sdusb_c23) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c24](../../../tang/impl/gpu_sdusb_c24) | 0 | 41.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c25](../../../tang/impl/gpu_sdusb_c25) | 0 | 40.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c26](../../../tang/impl/gpu_sdusb_c26) | 1 | 231.2 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c27](../../../tang/impl/gpu_sdusb_c27) | 1 | 231.6 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c28](../../../tang/impl/gpu_sdusb_c28) | 0 | 68.8 Mio | Conservé : dépendance ou référence |
| [gpu_sdusb_c29](../../../tang/impl/gpu_sdusb_c29) | 0 | 38.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c3](../../../tang/impl/gpu_sdusb_c3) | 1 | 230.4 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c30](../../../tang/impl/gpu_sdusb_c30) | 0 | 26.5 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c31](../../../tang/impl/gpu_sdusb_c31) | 1 | 228.9 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c32](../../../tang/impl/gpu_sdusb_c32) | 0 | 37.9 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c33](../../../tang/impl/gpu_sdusb_c33) | 1 | 474.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c34](../../../tang/impl/gpu_sdusb_c34) | 0 | 47.1 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c35](../../../tang/impl/gpu_sdusb_c35) | 0 | 359.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c36](../../../tang/impl/gpu_sdusb_c36) | 0 | 359.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c37](../../../tang/impl/gpu_sdusb_c37) | 1 | 501.0 Mio | Conservé : dépendance ou référence |
| [gpu_sdusb_c4](../../../tang/impl/gpu_sdusb_c4) | 1 | 230.1 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c5](../../../tang/impl/gpu_sdusb_c5) | 0 | 29.0 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c6](../../../tang/impl/gpu_sdusb_c6) | 1 | 230.4 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c7](../../../tang/impl/gpu_sdusb_c7) | 1 | 231.0 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c8](../../../tang/impl/gpu_sdusb_c8) | 1 | 230.8 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_c9](../../../tang/impl/gpu_sdusb_c9) | 1 | 229.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_r325](../../../tang/impl/gpu_sdusb_r325) | 0 | 40.7 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_r40](../../../tang/impl/gpu_sdusb_r40) | 0 | 41.3 Mio | Historique, sources et rapports conservés |
| [gpu_sdusb_r622](../../../tang/impl/gpu_sdusb_r622) | 1 | 230.4 Mio | Historique, sources et rapports conservés |
| [gpu_usb_advance_r1](../../../tang/impl/gpu_usb_advance_r1) | 1 | 51.4 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cdc_audit_r19_1](../../../tang/impl/gpu_usb_cdc_audit_r19_1) | 1 | 409.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cdc_audit_r19_2](../../../tang/impl/gpu_usb_cdc_audit_r19_2) | 1 | 409.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cdc_audit_r19_3](../../../tang/impl/gpu_usb_cdc_audit_r19_3) | 1 | 411.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cdc_audit_r19_4](../../../tang/impl/gpu_usb_cdc_audit_r19_4) | 1 | 411.3 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cdc_audit_r29_1](../../../tang/impl/gpu_usb_cdc_audit_r29_1) | 1 | 410.8 Mio | Conservé : dépendance ou référence |
| [gpu_usb_cen_audit_hs33_r1](../../../tang/impl/gpu_usb_cen_audit_hs33_r1) | 0 | 177.3 Mio | Historique, sources et rapports conservés |
| [gpu_usb_cen_audit_hs33_r2](../../../tang/impl/gpu_usb_cen_audit_hs33_r2) | 1 | 236.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_controller32_fs_model_r1](../../../tang/impl/gpu_usb_controller32_fs_model_r1) | 1 | 189.5 Mio | Conservé : dépendance ou référence |
| [gpu_usb_controller33_hs_model_r1](../../../tang/impl/gpu_usb_controller33_hs_model_r1) | 1 | 190.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_controller33_hs_msc_model_r1](../../../tang/impl/gpu_usb_controller33_hs_msc_model_r1) | 1 | 190.0 Mio | Conservé : dépendance ou référence |
| [gpu_usb_dedicated_fs_r1](../../../tang/impl/gpu_usb_dedicated_fs_r1) | 0 | 17.1 Mio | Historique, sources et rapports conservés |
| [gpu_usb_dedicated_fs_r2](../../../tang/impl/gpu_usb_dedicated_fs_r2) | 1 | 57.9 Mio | Historique, sources et rapports conservés |
| [gpu_usb_dedicated_fs_r3](../../../tang/impl/gpu_usb_dedicated_fs_r3) | 0 | 22.5 Mio | Historique, sources et rapports conservés |
| [gpu_usb_first_r1](../../../tang/impl/gpu_usb_first_r1) | 1 | 50.3 Mio | Historique, sources et rapports conservés |
| [gpu_usb_first_r2](../../../tang/impl/gpu_usb_first_r2) | 0 | 11.1 Mio | Historique, sources et rapports conservés |
| [gpu_usb_first_r3](../../../tang/impl/gpu_usb_first_r3) | 1 | 50.2 Mio | Historique, sources et rapports conservés |
| [gpu_usb_fs_diag_r1](../../../tang/impl/gpu_usb_fs_diag_r1) | 1 | 50.9 Mio | Historique, sources et rapports conservés |
| [gpu_usb_hs32_ready_r1](../../../tang/impl/gpu_usb_hs32_ready_r1) | 1 | 53.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_hs33_ep0_r1](../../../tang/impl/gpu_usb_hs33_ep0_r1) | 1 | 229.1 Mio | Conservé : dépendance ou référence |
| [gpu_usb_hs33_ready_r1](../../../tang/impl/gpu_usb_hs33_ready_r1) | 1 | 53.2 Mio | Historique, sources et rapports conservés |
| [gpu_usb_hs33_ready_r2](../../../tang/impl/gpu_usb_hs33_ready_r2) | 1 | 57.5 Mio | Historique, sources et rapports conservés |
| [gpu_usb_isolation_r1](../../../tang/impl/gpu_usb_isolation_r1) | 0 | 6.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_isolation_r2](../../../tang/impl/gpu_usb_isolation_r2) | 1 | 50.5 Mio | Historique, sources et rapports conservés |
| [gpu_usb_isolation_r3](../../../tang/impl/gpu_usb_isolation_r3) | 1 | 50.4 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phase_audit_r29_r1](../../../tang/impl/gpu_usb_phase_audit_r29_r1) | 1 | 288.6 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy34_advance_model_r1](../../../tang/impl/gpu_usb_phy34_advance_model_r1) | 2 | 378.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy34_model_r1](../../../tang/impl/gpu_usb_phy34_model_r1) | 1 | 190.2 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy34_r1](../../../tang/impl/gpu_usb_phy34_r1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy34_r2](../../../tang/impl/gpu_usb_phy34_r2) | 1 | 51.7 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_config_r1](../../../tang/impl/gpu_usb_phy35_config_r1) | 0 | 0.0 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_gui_r1](../../../tang/impl/gpu_usb_phy35_gui_r1) | 0 | 2.9 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_model_r1](../../../tang/impl/gpu_usb_phy35_model_r1) | 1 | 189.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_r1](../../../tang/impl/gpu_usb_phy35_r1) | 0 | 0.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_r2](../../../tang/impl/gpu_usb_phy35_r2) | 0 | 0.8 Mio | Historique, sources et rapports conservés |
| [gpu_usb_phy35_r3](../../../tang/impl/gpu_usb_phy35_r3) | 1 | 51.7 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r1](../../../tang/impl/gpu_v1_r1) | 1 | 213.1 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r10](../../../tang/impl/gpu_v1_r10) | 0 | 78.5 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r11](../../../tang/impl/gpu_v1_r11) | 1 | 224.0 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r12](../../../tang/impl/gpu_v1_r12) | 0 | 78.5 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r13](../../../tang/impl/gpu_v1_r13) | 1 | 224.5 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r14](../../../tang/impl/gpu_v1_r14) | 1 | 224.8 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r15](../../../tang/impl/gpu_v1_r15) | 1 | 225.1 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r16](../../../tang/impl/gpu_v1_r16) | 1 | 225.4 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r17](../../../tang/impl/gpu_v1_r17) | 1 | 225.4 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r18](../../../tang/impl/gpu_v1_r18) | 1 | 225.2 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r19](../../../tang/impl/gpu_v1_r19) | 1 | 225.7 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r2](../../../tang/impl/gpu_v1_r2) | 0 | 29.7 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r20](../../../tang/impl/gpu_v1_r20) | 1 | 225.8 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r21](../../../tang/impl/gpu_v1_r21) | 1 | 225.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r22](../../../tang/impl/gpu_v1_r22) | 1 | 225.4 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r23](../../../tang/impl/gpu_v1_r23) | 1 | 225.3 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r24](../../../tang/impl/gpu_v1_r24) | 1 | 225.5 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r25](../../../tang/impl/gpu_v1_r25) | 1 | 226.1 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r26](../../../tang/impl/gpu_v1_r26) | 1 | 226.0 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r27](../../../tang/impl/gpu_v1_r27) | 1 | 225.9 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r28](../../../tang/impl/gpu_v1_r28) | 1 | 225.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r29](../../../tang/impl/gpu_v1_r29) | 0 | 28.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r3](../../../tang/impl/gpu_v1_r3) | 1 | 214.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r30](../../../tang/impl/gpu_v1_r30) | 0 | 28.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r31](../../../tang/impl/gpu_v1_r31) | 1 | 486.1 Mio | Conservé : dépendance ou référence |
| [gpu_v1_r32](../../../tang/impl/gpu_v1_r32) | 1 | 227.4 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r4](../../../tang/impl/gpu_v1_r4) | 0 | 28.4 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r5](../../../tang/impl/gpu_v1_r5) | 0 | 28.7 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r6](../../../tang/impl/gpu_v1_r6) | 1 | 229.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r7](../../../tang/impl/gpu_v1_r7) | 1 | 229.6 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r8](../../../tang/impl/gpu_v1_r8) | 1 | 228.2 Mio | Historique, sources et rapports conservés |
| [gpu_v1_r9](../../../tang/impl/gpu_v1_r9) | 1 | 228.5 Mio | Historique, sources et rapports conservés |
| [usb_sipeed_fs_r1](../../../tang/impl/usb_sipeed_fs_r1) | 3 | 279.9 Mio | Conservé : dépendance ou référence |
| [usb_sipeed_fs_r2](../../../tang/impl/usb_sipeed_fs_r2) | 3 | 281.4 Mio | Historique, sources et rapports conservés |
| [usb_sipeed_reference_r1](../../../tang/impl/usb_sipeed_reference_r1) | 3 | 280.0 Mio | Conservé : dépendance ou référence |
