set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
set_option -top_module console_neo
set_option -output_base_name console_neo
set_option -verilog_std sysv2017
set_option -use_cpu_as_gpio 1
set_option -use_sspi_as_gpio 0
set_option -include_path {/home/michael/console/tang/impl/console_neo_n56r19_capture_ce_local/source/tang/rtl;/home/michael/console/tang/impl/console_neo_n56r19_capture_ce_local/source/tang}
set_option -gen_text_timing_rpt 1
set_option -gen_verilog_sim_netlist 1
set_option -gen_sdf 1
set_option -place_option 3
set_option -route_option 2
set_option -replicate_resources 0
set_option -clock_route_order 1
add_file {/home/michael/console/tang/impl/console_neo_fifo_banked_20261103_r1/console_neo.vg}
add_file {/home/michael/console/tang/impl/console_neo_fifo_banked_20261103_r1/neo.cst}
add_file {/home/michael/console/tang/impl/console_neo_fifo_banked_20261103_r1/neo.sdc}
run pnr
