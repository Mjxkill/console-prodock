# Configuration parser only. No netlist, project, synthesis, PNR or hardware.
puts "BEGIN_FRONTEND_COMMANDS"
puts [lsort [info commands]]
puts "END_FRONTEND_COMMANDS"
set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
puts "BEGIN_SET_OPTION_HELP"
set_option -h
puts "END_SET_OPTION_HELP"
set proposed [file join [file dirname [info script]] startup_clock.proposed.cst]
set outcome [catch {set_option -gao_cst $proposed} message]
puts "GAO_CST_SET_OPTION_RETURN:$outcome"
puts "GAO_CST_SET_OPTION_MESSAGE:$message"
puts "BEGIN_SAVE_ALL_OPTIONS"
saveto -all_options frontend_options.tcl
puts "END_SAVE_ALL_OPTIONS"
exit 0
