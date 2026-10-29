create_clock -name clk50 -period 20 [get_ports {clk}]
create_clock -name tck -period 1000 [get_ports {tck}]
