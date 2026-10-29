set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/probe.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/probe.cst}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/probe.sdc}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/video_pll.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/hdmi_out.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/svo_tmds.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/gowin_pll_f.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/generated_cdc_origins_20261017/generated_original/gowin_pll_b.v}
set_option -top_module probe
set_option -output_base_name probe
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -place_option 3
set_option -route_option 2
run all
