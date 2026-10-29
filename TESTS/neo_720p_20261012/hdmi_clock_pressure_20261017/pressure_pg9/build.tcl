set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/probe.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/probe.cst}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/probe.sdc}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/video_pll.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/hdmi_out.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/svo_tmds.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/gowin_pll_f.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_clock_pressure_20261017/pressure_pg9/gowin_pll_b.v}
set_option -top_module probe
set_option -output_base_name probe
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -place_option 3
set_option -route_option 2
run all
