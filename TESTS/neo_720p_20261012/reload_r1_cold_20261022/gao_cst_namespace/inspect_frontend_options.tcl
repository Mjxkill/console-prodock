# Introspection only: no project inputs, synthesis, PNR or hardware action.
puts "BEGIN_FRONTEND_COMMANDS"
puts [lsort [info commands]]
puts "END_FRONTEND_COMMANDS"
set_device -name GW5AST-138C GW5AST-LV138PG484AC1/I0
puts "BEGIN_SET_OPTION_HELP"
set_option -h
puts "END_SET_OPTION_HELP"
exit 0
