set_device -name GW5AST-138B GW5AST-LV138FPG676AC1/I0
set_option -include_path {source/tang/rtl}
set_option -top_module console_top
set_option -output_base_name console_prodock_sd_reset_20261030_r6
set_option -verilog_std v2001
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -gen_verilog_sim_netlist 1
set_option -gen_sdf 1
set_option -route_option 2
set_option -replicate_resources 0
set_option -place_option 3
add_file {impl/gwsynthesis/console_prodock_sd_reset_20261030_r6.vg}
add_file {constraints_resolved.cst}
add_file {source/diagnostics/timing_reports.sdc}
run pnr
