create_project -name pll_inspection -dir {/home/michael/console/TESTS/neo_common_cause_20261027/video_pll_generator_01/project} -pn GW5AST-LV138PG484AC1/I0 -device_version C
create_ipc -name clock_plladv -module_name NeoPLLInspection -file_name neo_pll_inspection -language Verilog -dir {/home/michael/console/TESTS/neo_common_cause_20261027/video_pll_generator_01/ip}
set_property CONFIG.General_Mode {true} [get_ips NeoPLLInspection]
set_property CONFIG.Adcanced_Mode {false} [get_ips NeoPLLInspection]
set_property CONFIG.CLKIN_FREQ {50.000} [get_ips NeoPLLInspection]
set_property CONFIG.CLKOUT0_FREQ {371.875} [get_ips NeoPLLInspection]
set_property CONFIG.CLKOUT0_TOLERANCE {0.0} [get_ips NeoPLLInspection]
set_property CONFIG.CLKOUT2_EN {true} [get_ips NeoPLLInspection]
set_property CONFIG.CLKOUT2_FREQ {74.375} [get_ips NeoPLLInspection]
set_property CONFIG.CLKOUT2_TOLERANCE {0.0} [get_ips NeoPLLInspection]
set_property CONFIG.LOCK_EN {true} [get_ips NeoPLLInspection]
set_property CONFIG.INIT_CLK_FREQ {50} [get_ips NeoPLLInspection]
report_property [get_ips NeoPLLInspection]
generate_target [get_ips NeoPLLInspection]
puts {PLL_INSPECTION_GENERATED_NO_PNR}
exit 0
