set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file rtl/console_e0b_plonly.v
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
add_file constr/console_e0b.cst
add_file constr/console_e0b.sdc
set_option -top_module console_top
set_option -output_base_name console_e0b_plonly
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
run all
