set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/probe.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/probe.cst}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/probe.sdc}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/video_pll.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/hdmi_out.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/svo_tmds.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/hdmi_bars_dhce/video_720p.v}
set_option -top_module probe
set_option -output_base_name probe
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -place_option 3
set_option -route_option 2
run all
