# build_e1.tcl — E1 : test DDR3 Sipeed (pro_ddr_test) avec émission en boucle, sur Pro Dock.
set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file rtl/ddrtest/ddr_test_loop.v
add_file rtl/ddrtest/ddr3_test.v
add_file rtl/ddrtest/fifo.v
add_file rtl/ddrtest/uart_tx.v
add_file rtl/ddrtest/ddr3_memory_interface/ddr3_memory_interface.v
add_file rtl/ddrtest/gowin_pll/gowin_pll.v
add_file constr/ddr_e1.cst
add_file constr/ddr_e1.sdc
set_option -top_module top
set_option -output_base_name ddr_e1
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
run all