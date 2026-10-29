init
halt
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Unexpected running OS"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU not parked"}
riscv set_enable_virt2phys off
set code [read_memory 0x80000000 32 2]
echo "PARKING_CODE $code"
if {[lindex $code 0]!=0x10500073 || [lindex $code 1]!=0xffdff06f} {error "Unknown ROM parking code"}
echo PARKING_CONFIRMED
shutdown
