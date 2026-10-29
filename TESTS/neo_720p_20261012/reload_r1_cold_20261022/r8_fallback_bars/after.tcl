init
halt
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected bare-metal parking"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "Wrong parking PC"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x80000000 32 1] 0]!=0x10500073} {error "Wrong parking ROM"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong board geometry"}
sleep 100
echo "FALLBACK_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "FALLBACK_1 [read_memory 0xe9000000 32 32]"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback display does not match"}
echo CPU_LEFT_HALTED
shutdown
