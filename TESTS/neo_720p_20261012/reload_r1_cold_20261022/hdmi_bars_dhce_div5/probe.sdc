create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]
create_generated_clock -name vid_clk5x -source [get_ports {clk}] -multiply_by 119 -divide_by 16 [get_pins {u_video_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name vid_pclk -source [get_pins {u_video_pll/PLL_inst/CLKOUT0}] -divide_by 5 [get_pins {u_video_div/CLKOUT}]
set_clock_latency -source 0 [get_clocks {vid_pclk vid_clk5x}]
report_timing -setup -max_paths 200 -max_common_paths 2
report_timing -hold -max_paths 200 -max_common_paths 2
report_timing -recovery -max_paths 200 -max_common_paths 2
report_timing -removal -max_paths 200 -max_common_paths 2
