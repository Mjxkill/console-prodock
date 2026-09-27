set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file ref_demo/ae350_customized_demo.v
add_file ref_demo/gowin_pll_100m.v
add_file ref_demo/gowin_pll_100m_mod.v
add_file ref_demo/pll_init.v
add_file ref_demo/gowin_pll_ddr3/gowin_pll_ddr3.v
add_file ref_demo/key_debounce.v
add_file ref_demo/riscv_ae350_soc/riscv_ae350_soc.v
add_file ref_demo/ddr3_memory/gw_ahb_ddr3.v
add_file ref_demo/ddr3_memory/ddr3_memory_interface/ddr3_memory_interface.v
add_file ref_demo/ddr3_memory/ddr3_memory_rdfifo/ddr3_memory_rdfifo.v
add_file ref_demo/ddr3_memory/ddr3_memory_wrfifo/ddr3_memory_wrfifo.v
add_file ref_demo/ae350_customized_demo.cst
add_file ref_demo/ae350_customized_demo.sdc
set_option -top_module ae350_customized_demo
set_option -output_base_name refdemo
set_option -verilog_std v2001
set_option -use_sspi_as_gpio 0
set_option -gen_text_timing_rpt 1
run all
