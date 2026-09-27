# build_e2.tcl — E2 : LCD + CDC + socle AE350 de l'analyseur (soc + DDR3 standalone + pont Sipeed).
set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file rtl/console_top.v
add_file rtl/video/lcd_timing.v
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
add_file rtl/board/ddr_gpu_arb.v
add_file rtl/board/ddr_arb.v
add_file rtl/board/ddr_dcfifo.v
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
add_file constr/ae350_e2.cst
add_file constr/ae350_e2.sdc
set_option -top_module console_top
set_option -output_base_name console_e2
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
run all
