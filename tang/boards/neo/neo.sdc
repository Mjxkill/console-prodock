// Tang Console PG484C: constrain every fabric clock, including HDMI x5.
create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]
create_clock -name bus80_clk -period 12.5 -waveform {0 6.25} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT0}]
create_clock -name core_clk -period 1.25 -waveform {0 0.625} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT1}]
create_clock -name rtc_clk -period 100 -waveform {0 50} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT4}]
create_clock -name ddr3_mem_clk -period 3.333 -waveform {0 1.667} [get_pins {u_soc/u_pll_ddr3/u_pll/PLL_inst/CLKOUT2}]
create_clock -name ddr3_sys_clk -period 13.333 -waveform {0 6.667} [get_pins {u_soc/g_ddr.u_ddr/u_ip/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]
create_generated_clock -name vid_clk5x -source [get_ports {clk}] -multiply_by 119 -divide_by 16 [get_pins {u_video_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name vid_pclk -source [get_ports {clk}] -multiply_by 119 -divide_by 80 [get_pins {u_video_pll/PLL_inst/CLKOUT2}]
// Only macro-owned core/RTC crossings are excluded. Fabric mailboxes, dual
// clock RAMs and FIFO Gray pointers stay visible with explicit delay bounds.
set_clock_groups -asynchronous -group [get_clocks {core_clk}] -group [get_clocks {rtc_clk}] -group [get_clocks {clk50 bus80_clk ddr3_mem_clk ddr3_sys_clk vid_pclk vid_clk5x}]
set_max_delay 8 -from [get_clocks {clk50}] -to [get_clocks {ddr3_sys_clk}]
set_false_path -hold -from [get_clocks {clk50}] -to [get_clocks {ddr3_sys_clk}]
set_max_delay 8 -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {clk50}]
set_false_path -hold -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {clk50}]
set_max_delay 8 -from [get_clocks {bus80_clk}] -to [get_clocks {ddr3_sys_clk}]
set_false_path -hold -from [get_clocks {bus80_clk}] -to [get_clocks {ddr3_sys_clk}]
set_max_delay 8 -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {bus80_clk}]
set_false_path -hold -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {bus80_clk}]
set_max_delay 8 -from [get_clocks {bus80_clk}] -to [get_clocks {vid_pclk}]
set_false_path -hold -from [get_clocks {bus80_clk}] -to [get_clocks {vid_pclk}]
set_max_delay 8 -from [get_clocks {vid_pclk}] -to [get_clocks {bus80_clk}]
set_false_path -hold -from [get_clocks {vid_pclk}] -to [get_clocks {bus80_clk}]
set_max_delay 8 -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {vid_pclk}]
set_false_path -hold -from [get_clocks {ddr3_sys_clk}] -to [get_clocks {vid_pclk}]
set_max_delay 8 -from [get_clocks {vid_pclk}] -to [get_clocks {ddr3_sys_clk}]
set_false_path -hold -from [get_clocks {vid_pclk}] -to [get_clocks {ddr3_sys_clk}]
// clk50 and bus80 also exchange asynchronous FIFO pointers/reset releases.
set_max_delay 8 -from [get_clocks {clk50}] -to [get_clocks {bus80_clk}]
set_max_delay 8 -from [get_clocks {bus80_clk}] -to [get_clocks {clk50}]
set_false_path -hold -from [get_clocks {clk50}] -to [get_clocks {bus80_clk}]
set_false_path -hold -from [get_clocks {bus80_clk}] -to [get_clocks {clk50}]
// No phase-based hold requirement exists between independent clocks. Maximum
// delay bounds remain active; all intra-domain setup/hold paths stay checked.
// Asynchronous assertion only: deassertion is synchronized in these flops.
set_false_path -to [get_pins {ae350_rst_sync_*/PRESET}]
set_false_path -to [get_pins {u_hdmi/g_reset*.reset_sync*/PRESET}]
// Asynchronous serial input: only the first synchronizer D is exempt.
set_false_path -from [get_ports {uart_rx}] -to [get_pins {u_console_input/u_debug_rx/rx_sync_0_s1/D}]
set_false_path -to [get_pins {u_soc/u_ae350/u_RiscV_AE350_SOC/u_AE350_SOC/UART2_RXD}]
// USB HS: qualified Pro Dock reference, adapted to Neo's top-level pins.
create_generated_clock -name CLK_48M -source [get_ports {clk}] -master_clock clk50 -divide_by 50 -multiply_by 48 [get_pins {u_pll_f/PLL_inst/CLKOUT0}]
create_generated_clock -name PHY_CLKOUT -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 4 -multiply_by 5 [get_pins {u_pll_b/PLL_inst/CLKOUT1}]
create_generated_clock -name fclk_960M -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 2 -multiply_by 40 [get_pins {u_pll_b/PLL_inst/CLKOUT0}]
create_clock -name sclk -period 8.333 -waveform {0 4.166} [get_nets {u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/sclk}] -add
// Inside the encrypted SoftPHY these domains follow the vendor constraints.
set_clock_groups -asynchronous -group [get_clocks {PHY_CLKOUT}] -group [get_clocks {sclk}] -group [get_clocks {fclk_960M}]
// Fabric mailboxes/FIFO pointers remain bounded, including USB status/MSC.
set_max_delay 8 -from [get_clocks {PHY_CLKOUT}] -to [get_clocks {bus80_clk}]
set_max_delay 8 -from [get_clocks {bus80_clk}] -to [get_clocks {PHY_CLKOUT}]
set_false_path -hold -from [get_clocks {PHY_CLKOUT}] -to [get_clocks {bus80_clk}]
set_false_path -hold -from [get_clocks {bus80_clk}] -to [get_clocks {PHY_CLKOUT}]
set_max_delay 8 -from [get_clocks {clk50}] -to [get_clocks {PHY_CLKOUT}]
set_max_delay 8 -from [get_clocks {PHY_CLKOUT}] -to [get_clocks {clk50}]
set_false_path -hold -from [get_clocks {clk50}] -to [get_clocks {PHY_CLKOUT}]
set_false_path -hold -from [get_clocks {PHY_CLKOUT}] -to [get_clocks {clk50}]
set_false_path -to [get_pins {u_console_input/u_bridge/rx_sync_0_s0/D}]
set_false_path -to [get_pins {u_console_output/u_rx/rx_sync_0_s1/D}]
// Only the first serial input synchronizers are asynchronous; their second
// stage and all host logic remain timed at 80 MHz (no broad host exception).
set_false_path -to [get_pins {u_gamepads/g_port*.u_pad/u_host/dp_sync_0*/D}]
set_false_path -to [get_pins {u_gamepads/g_port*.u_pad/u_host/dm_sync_0*/D}]
// N14 registers the host ROM output on every 80 MHz edge before decode.
// Its value is unchanged at each 3/20 CE. ROM and interpreter paths are
// therefore timed at one bus cycle; the earlier 6/5 exception is removed.
report_timing -setup -max_paths 1000 -max_common_paths 1
report_timing -hold -max_paths 200 -max_common_paths 1
report_timing -recovery -max_paths 100 -max_common_paths 1
report_timing -removal -max_paths 100 -max_common_paths 1
