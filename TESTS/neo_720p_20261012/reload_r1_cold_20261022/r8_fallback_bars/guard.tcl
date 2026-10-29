init
halt
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected bare-metal parking"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "Wrong parking PC"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x80000000 32 1] 0]!=0x10500073} {error "Wrong parking ROM"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong board geometry"}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=3 || [lindex [read_memory 0xe9000030 32 1] 0]!=0} {error "Not the isolated RGB trial"}
echo "BEFORE [read_memory 0xe9000000 32 32]"
echo CPU_LEFT_HALTED
shutdown
