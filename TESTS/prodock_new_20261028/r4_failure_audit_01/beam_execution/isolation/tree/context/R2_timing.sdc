// ae350_e2.sdc — E2 : LCD + USB + AE350 + DDR3 (socle analyseur porté, fréquences la16.sdc V3).
create_clock -name clk50 -period 20 -waveform {0 10} [get_ports {clk}]
create_clock -name sclk -period 8.333 -waveform {0 4.166} [get_nets {u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/sclk}] -add

// Reprise de usb_uart_loopback/src/usb_ref.sdc (Sipeed/Gowin) : le PHY
// fournit ses traversées entre 60/120/960 MHz, traitées comme asynchrones.
create_generated_clock -name CLK_48M -source [get_ports {clk}] -master_clock clk50 -divide_by 50 -multiply_by 48 [get_pins {u_pll_f/PLL_inst/CLKOUT0}]
create_generated_clock -name PHY_CLKOUT -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 4 -multiply_by 5 [get_pins {u_pll_b/PLL_inst/CLKOUT1}]
create_generated_clock -name fclk_960M -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 2 -multiply_by 40 [get_pins {u_pll_b/PLL_inst/CLKOUT0}]
create_generated_clock -name LCD_35M -source [get_ports {clk}] -master_clock clk50 -divide_by 30 -multiply_by 21 [get_pins {u_pll_lcd/PLL_inst/CLKOUT0}]
set_clock_groups -asynchronous -group [get_clocks {PHY_CLKOUT}] -group [get_clocks {sclk}] -group [get_clocks {fclk_960M}]

// horloges du SoC AE350 (la16.sdc V3) : bus 80 MHz + core 800 MHz + RTC 10 MHz
create_clock -name bus80_clk -period 12.5 -waveform {0 6.25} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT0}]
create_clock -name core_clk -period 1.25 -waveform {0 0.625} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT1}]
create_clock -name rtc_clk -period 100 -waveform {0 50} [get_pins {u_pll_ae350/u_pll/PLL_inst/CLKOUT4}]
create_clock -name ddr3_ref_clk -period 20 -waveform {0 10} [get_pins {u_soc/u_pll_ddr3/u_pll/PLL_inst/CLKOUT0}]
create_clock -name ddr3_mem_clk -period 3.333 -waveform {0 1.667} [get_pins {u_soc/u_pll_ddr3/u_pll/PLL_inst/CLKOUT2}]
create_clock -name ddr3_sys_clk -period 13.333 -waveform {0 6.667} [get_pins {u_soc/g_ddr.u_ddr/u_ip/gw3_top/u_ddr_phy_top/fclkdiv/CLKOUT}]

set_clock_groups -asynchronous -group [get_clocks {clk50 sclk}] -group [get_clocks {bus80_clk}] -group [get_clocks {core_clk}] -group [get_clocks {rtc_clk}] -group [get_clocks {ddr3_ref_clk ddr3_mem_clk ddr3_sys_clk}]

// UART : échantillonnage asynchrone par le récepteur matériel AE350 et par
// rx_sync[0:1] dans le pont. Le chemin entre les deux bascules reste analysé.
set_false_path -to [get_pins {u_pont/rx_sync_0_s0/D}]
set_false_path -to [get_pins {u_soc/u_ae350/u_RiscV_AE350_SOC/u_AE350_SOC/UART2_RXD}]

// G1 graphics CDC: palette/commit/status (AHB <-> pixel), line request/ack
// and dual-clock line RAM (DDR UI <-> pixel). No combinational transfer is
// used as a destination enable; mailbox payloads are held until acknowledged.
set_clock_groups -asynchronous -group [get_clocks {LCD_35M}] -group [get_clocks {bus80_clk ddr3_sys_clk}]

// Queries only; no additional constraints or exceptions.
report_timing -setup -from_clock [get_clocks {ddr3_sys_clk}] -to_clock [get_clocks {ddr3_sys_clk}] -max_paths 2000 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {bus80_clk}] -to_clock [get_clocks {bus80_clk}] -max_paths 2000 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {LCD_35M}] -to_clock [get_clocks {LCD_35M}] -max_paths 2000 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {PHY_CLKOUT}] -to_clock [get_clocks {PHY_CLKOUT}] -max_paths 2000 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {sclk}] -to_clock [get_clocks {sclk}] -max_paths 2000 -max_common_paths 1
