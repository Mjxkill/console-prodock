init
halt
set failed [catch {
    if {[lindex [reg priv] 2] != 1 || [lindex [reg satp] 2] == 0} {error "Expected Linux supervisor context"}
    riscv set_enable_virt2phys off
    set lcr [lindex [read_memory 0xf030002c 32 1] 0]
    if {($lcr & 0x8f) != 3} {error "UART not in 8-bit TX register mode"}
    echo "UART_WITNESS_PC [reg pc]"
    echo "UART_WITNESS_LCR $lcr"
    foreach byte {78 69 79 95 85 65 82 84 95 87 73 84 78 69 83 83 13 10} {
        if {([lindex [read_memory 0xf0300034 32 1] 0]&0x60) != 0x60} {error "UART TX not idle"}
        write_memory 0xf0300020 32 [list $byte]
        sleep 20
    }
} reason]
resume
echo LINUX_RESUMED
if {$failed} {error $reason}
echo BOOT_OBSERVATION_COMPLETE
shutdown
