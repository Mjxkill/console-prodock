set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/probe.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/probe.cst}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/probe.sdc}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/video_pll.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/hdmi_out.v}
add_file {/home/michael/console/TESTS/neo_720p_20261012/hdmi_dce_sites_r1_20261017/pg9_c181/svo_tmds.v}
set_option -top_module probe
set_option -output_base_name probe
set_option -use_cpu_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -place_option 3
set_option -route_option 2
run all
