gdb_port disabled
tcl_port disabled
telnet_port disabled
init
halt
proc register_value {name} {return [lindex [reg $name] 2]}
set saved_pc [register_value pc]
set saved_a0 [register_value a0]
set saved_a7 [register_value a7]
set modified 0
set failure [catch {
    if {[register_value priv] != 0} {error "Not a userspace process"}
    if {$saved_pc < 0x301ac || $saved_pc > 0x301c4} {error "Not the observed BusyBox loop"}
    riscv set_enable_virt2phys on
    set code [read_memory 0x301ac 32 7]
    foreach actual $code expected {0x0106a783 0x0117f733 0x1606282f 0x00f81663 0x1ee625af 0xfe059ae3 0xff0794e3} {
        if {$actual != $expected} {error "BusyBox instruction fingerprint mismatch"}
    }
    if {[lindex [read_memory 0x2e5f0 32 1] 0] != 0x73} {error "ECALL instruction mismatch"}
    echo "NEO_STUCK_BUSYBOX pc=$saved_pc code=$code"
    set modified 1
    reg a0 0
    reg a7 94
    reg pc 0x2e5f0
} reason]
if {$failure} {
    if {$modified} {
        reg a0 $saved_a0
        reg a7 $saved_a7
        reg pc $saved_pc
    }
    resume
    echo "NEO_RECOVERY_REFUSED $reason"
} else {
    resume
    echo NEO_BUSYBOX_EXIT_REQUESTED
}
shutdown
