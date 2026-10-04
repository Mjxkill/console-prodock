# build_e1_cdc.tcl — E1 : test DDR3 Sipeed + console par CDC USB (ttyACM0), sur Pro Dock.
set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file rtl/console_top.v
add_file rtl/ddrtest/ddr3_test.v
add_file rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.v
add_file rtl/ddrtest/gowin_pll/gowin_pll.v
add_file rtl/video/lcd_timing.v
add_file rtl/video/gowin_pll_lcd.v
add_file rtl/usb/gowin_pll_f.v
add_file rtl/usb/gowin_pll_b.v
add_file rtl/usb/uart/uart.v
add_file rtl/usb/uart/uart_rx.vhd
add_file rtl/usb/uart/uart_tx.vhd
add_file rtl/usb/uart/usb_uart_config.v
add_file rtl/usb/usb2_0_softphy.v
add_file rtl/usb/usb_reset_release.v
add_file rtl/usb/usb_device_controller.v
add_file rtl/usb/usb_descriptor.v
add_file rtl/usb/sync_fifo/sync_rx_pkt_fifo.v
add_file rtl/usb/sync_fifo/sync_tx_pkt_fifo.v
add_file rtl/usb/sync_fifo/usb_fifo.v
add_file rtl/usb/integer_division/integer_division.v
add_file constr/ddr_e1_cdc.cst
add_file constr/ddr_e1.sdc
set_option -top_module console_top
set_option -output_base_name ddr_e1_cdc
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
run all
