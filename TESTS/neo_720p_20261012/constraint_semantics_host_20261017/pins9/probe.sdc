create_clock -name source -period 20 [get_ports {other}]
create_clock -name sink -period 20 [get_ports {clk}]
set_clock_latency -source 9 [get_clocks {source}]
set_max_delay 8 -from [get_pins {toggle_s0/Q}] -to [get_pins {stage1_s0/D}]
set_false_path -hold -from [get_clocks {source}] -to [get_clocks {sink}]
report_timing -setup -max_paths 30 -max_common_paths 1
report_timing -hold -max_paths 30 -max_common_paths 1
