init
halt
set failed [catch {
    if {[lindex [reg satp] 2]==0} {error "Expected Linux"}
    riscv set_enable_virt2phys off
    if {[lindex [read_memory 0x08192802 16 1] 0]!=0x0073 || [lindex [read_memory 0x08192804 16 1] 0]!=0x1050 || [lindex [read_memory 0x0947d028 32 1] 0]!=3} {error "Wrong Linux fingerprint"}
    if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong board geometry"}
    echo "QUIESCED_LINUX_PC [reg pc]"
} reason]
if {$failed} {resume; error $reason}
echo LINUX_LEFT_HALTED
shutdown
