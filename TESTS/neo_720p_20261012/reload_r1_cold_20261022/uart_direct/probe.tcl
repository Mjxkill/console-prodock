init
halt
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected parking privilege"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "Wrong parking PC"}
if {[lindex [read_memory 0x80000000 32 1] 0]!=0x10500073} {error "Wrong boot ROM"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500 || [lindex [read_memory 0xe9000008 32 1] 0]!=0} {error "Not the fallback display state"}
echo "UART_BEFORE [read_memory 0xf030002c 32 3]"
write_memory 0xf030002c 32 {0x83}
write_memory 0xf0300020 32 {43}
write_memory 0xf0300024 32 {0}
write_memory 0xf030002c 32 {3}
write_memory 0xf0300028 32 {7}
write_memory 0xf0300024 32 {0}
echo UART_DIRECT_READY
for {set i 0} {$i<128} {incr i} {
    set received 0
    for {set j 0} {$j<400} {incr j} {
        set status [lindex [read_memory 0xf0300034 32 1] 0]
        if {$status & 1} {set received 1;break}
        sleep 5
    }
    if {!$received} {error "UART receive timeout at $i"}
    set value [lindex [read_memory 0xf0300020 32 1] 0]
    echo "UART_DIRECT_RX $i $status $value"
}
echo UART_DIRECT_COMPLETE
shutdown
