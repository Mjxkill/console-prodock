create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]
create_generated_clock -name vid_clk5x -source [get_ports {clk}] -multiply_by 119 -divide_by 16 [get_pins {u_video_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name vid_pclk -source [get_ports {clk}] -multiply_by 119 -divide_by 80 [get_pins {u_video_pll/PLL_inst/CLKOUT2}]
set_false_path -to [get_pins {u_hdmi/g_reset*.reset_sync*/PRESET}]
create_generated_clock -name CLK_48M -source [get_ports {clk}] -master_clock clk50 -divide_by 50 -multiply_by 48 [get_pins {u_pll_f/PLL_inst/CLKOUT0}]
create_generated_clock -name PHY_CLKOUT -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 4 -multiply_by 5 [get_pins {u_pll_b/PLL_inst/CLKOUT1}]
create_generated_clock -name fclk_960M -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 2 -multiply_by 40 [get_pins {u_pll_b/PLL_inst/CLKOUT0}]
create_clock -name bus_test_clock -period 13.446 [get_pins {u_bus_test/PLL_inst/CLKOUT2}]
create_clock -name gpu_test_clock -period 10.757 [get_pins {u_gpu_div/CLKOUT}]
create_clock -name sclk_clock -period 8.333 [get_pins {u_usb_div/CLKOUT}]

report_timing -setup -max_paths 200 -max_common_paths 2
report_timing -hold -max_paths 200 -max_common_paths 2
report_timing -recovery -max_paths 200 -max_common_paths 2
report_timing -removal -max_paths 200 -max_common_paths 2
