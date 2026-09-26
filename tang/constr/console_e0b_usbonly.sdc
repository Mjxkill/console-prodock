// console_e0b_usbonly.sdc — USB seul (diagnostic), pas de LCD.
create_clock -name clk_50M -period 20 -waveform {0 10} [get_ports {clk}]
create_clock -name sclk -period 8.333 -waveform {0 4.166} [get_nets {u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/sclk}] -add

create_generated_clock -name CLK_48M -source [get_ports {clk}] -master_clock clk_50M -divide_by 50 -multiply_by 48 [get_pins {u_pll_f/PLL_inst/CLKOUT0}]
create_generated_clock -name PHY_CLKOUT -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 4 -multiply_by 5 [get_pins {u_pll_b/PLL_inst/CLKOUT1}]
create_generated_clock -name fclk_960M  -source [get_pins {u_pll_f/PLL_inst/CLKOUT0}] -master_clock CLK_48M -divide_by 2 -multiply_by 40 [get_pins {u_pll_b/PLL_inst/CLKOUT0}]

set_clock_groups -asynchronous -group [get_clocks {PHY_CLKOUT}] -group [get_clocks {sclk}] -group [get_clocks {fclk_960M}]

set_false_path -from [get_pins {u_uart/u_Integer_Division/integer_division_inst/integer_division_frac_inst/reg_divisor_*_s0/Q}]  -setup
set_false_path -from [get_pins {u_uart/u_Integer_Division/integer_division_inst/integer_division_frac_inst/reg_dividend_*_s0/Q}]  -setup
