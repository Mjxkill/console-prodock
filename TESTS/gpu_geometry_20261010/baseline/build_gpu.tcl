# Game console: AE350 800 MHz + DDR3 layers/sprites/tile maps + triangle accelerator.
set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file rtl/console_gpu.v
add_file rtl/video/gpu_scanout.v
add_file rtl/video/gpu_rgb_reader.v
add_file rtl/video/gpu_line_reader.v
add_file rtl/video/gpu_sprite_cache.v
add_file rtl/video/gpu_tile_row.v
add_file rtl/video/gpu_accel.v
add_file rtl/video/gpu_raster.v
add_file rtl/video/gpu_v1.v
add_file rtl/video/gpu_texture_cache.v
add_file rtl/video/gpu_copy565.v
add_file rtl/video/gpu_perspective.v
add_file rtl/video/gpu_blit_dma.v
add_file rtl/video/blitter.v
add_file rtl/video/gpu_triangle.v
add_file rtl/video/font_ram.v
add_file rtl/board/ddr_gpu_arb.v
add_file rtl/video/gowin_pll_lcd.v
add_file rtl/usb/gowin_pll_f.v
add_file rtl/usb/gowin_pll_b.v
add_file rtl/usb/uart/uart.v
add_file rtl/usb/uart/uart_rx.vhd
add_file rtl/usb/uart/uart_tx.vhd
add_file rtl/usb/uart/usb_uart_config.v
add_file rtl/usb/usb2_0_softphy.v
add_file rtl/usb/usb_device_controller.v
add_file rtl/usb/usb_descriptor.v
add_file rtl/usb/usb_packet_trace.v
add_file rtl/usb/usb_idle_trace.v
add_file rtl/usb/usb_msc_port.v
add_file rtl/usb/usb_msc_guard.v
add_file rtl/usb/usb_msc_empty.v
add_file rtl/usb/usb_reset_release.v
add_file rtl/usb/sync_fifo/sync_rx_pkt_fifo.v
add_file rtl/usb/sync_fifo/sync_tx_pkt_fifo.v
add_file rtl/usb/sync_fifo/usb_fifo.v
add_file rtl/usb/integer_division/integer_division.v
add_file rtl/ae350/uart2_to_ep2.v
add_file rtl/ae350/pll_ae350/gowin_pll_ae350.v
add_file rtl/ae350/pll_ae350/gowin_pll_ae350_mod.v
add_file rtl/board/ae350_soc.v
add_file rtl/board/ext_regs.v
add_file rtl/board/cdc_clear.v
add_file rtl/board/cdc_word.v
add_file rtl/board/ahb_exts_bridge.v
add_file rtl/board/ddr_subsys.v
add_file rtl/board/ddr_arb.v
add_file rtl/board/ddr_dcfifo.v
add_file rtl/board/ahb_ddr_cdc.v
add_file rtl/board/ddr_writer.v
add_file rtl/board/ddr_reader.v
add_file rtl/board/ddr_ui_adapt.v
add_file rtl/board/key_debounce.v
add_file rtl/board/gowin_pll_ddr3.v
add_file rtl/board/gowin_pll_ddr3_mod.v
add_file rtl/board/pll_init.v
add_file rtl/board/ddr3_standalone_32b/ddr3_standalone.v
add_file rtl/board/sipeed/ddr3_memory_rdfifo.v
add_file rtl/board/sipeed/ddr3_memory_wrfifo.v
add_file rtl/board/ddr3_standalone_32b/cfg/DDR3_define.v
add_file rtl/board/ddr3_standalone_32b/cfg/ddr3_name.v
add_file rtl/board/ddr3_standalone_32b/cfg/ddr3.prj
add_file rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v
add_file rtl/board/riscv_ae350_soc_ext/cfg/riscv_ae350_config.v
add_file rtl/board/riscv_ae350_soc_ext/cfg/gw_itcm_config.v
add_file rtl/board/riscv_ae350_soc_ext/cfg/gw_dtcm_config.v
add_file rtl/board/riscv_ae350_soc_ext/cfg/gwmc_param.v
add_file rtl/board/sipeed/gw_ahb_ddr3.v
add_file constr/gpu.cst
add_file constr/gpu.sdc
set_option -include_path rtl
set_option -top_module console_top
set_option -output_base_name console_gpu
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -gen_verilog_sim_netlist 1
set_option -gen_sdf 1
set_option -route_option 1
set_option -replicate_resources 1
run all
