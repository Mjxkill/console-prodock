create_clock -name source -period 13.332 [get_ports {other}]
create_clock -name sink -period 3.333 [get_ports {clk}]
report_timing -setup -max_paths 30 -max_common_paths 1
report_timing -hold -max_paths 30 -max_common_paths 1
