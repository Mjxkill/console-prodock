set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
add_file source.vg
add_file source.cst
add_file diagnostic.sdc
set_option -top_module console_top
set_option -output_base_name console_cdc_audit
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -route_option 1
set_option -place_option 3
set_option -clock_route_order 0
run pnr
