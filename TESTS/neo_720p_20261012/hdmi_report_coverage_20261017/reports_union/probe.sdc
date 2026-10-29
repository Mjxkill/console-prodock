create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]
create_generated_clock -name vid_clk5x -source [get_ports {clk}] -multiply_by 119 -divide_by 16 [get_pins {u_video_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name vid_pclk -source [get_ports {clk}] -multiply_by 119 -divide_by 80 [get_pins {u_video_pll/PLL_inst/CLKOUT2}]
set_false_path -to [get_pins {u_hdmi/g_reset*.reset_sync*/PRESET}]
report_timing -setup -max_paths 200 -max_common_paths 2
report_timing -hold -max_paths 200 -max_common_paths 2
report_timing -recovery -max_paths 200 -max_common_paths 2
report_timing -removal -max_paths 200 -max_common_paths 2
report_timing -recovery -to [get_pins {u_hdmi/g_ser[0].u_ser/RESET}] -max_paths 10 -max_common_paths 3
report_timing -removal -to [get_pins {u_hdmi/g_ser[0].u_ser/RESET}] -max_paths 10 -max_common_paths 3
