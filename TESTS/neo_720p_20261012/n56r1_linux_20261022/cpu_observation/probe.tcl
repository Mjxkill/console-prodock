riscv expose_csrs 1994,1996,2000
init
set previous [nds.cpu curstate]
if {$previous ne "running" && $previous ne "halted"} {error "Unexpected CPU state"}
echo "BOOT_PREVIOUS_STATE $previous"
halt
set failed [catch {
    foreach name {pc priv satp mstatus mie mtvec mepc mcause mtval sp ra a0 a1 a2 a3 a4 a5 a6 a7 csr1994 csr1996 csr2000} {
        echo "BOOT_REGISTER $name [reg $name]"
    }
    set pc [lindex [reg pc] 2]
    if {[lindex [reg priv] 2] == 3 && [lindex [reg satp] 2] == 0} {
        riscv set_enable_virt2phys off
        echo "BOOT_CODE [read_memory [expr {$pc&0xfffffffc}] 32 8]"
    }
    if {$previous eq "running"} {
        for {set sample 0} {$sample < 5} {incr sample} {
            resume
            sleep 50
            halt
            echo "BOOT_PC $sample [reg pc] [reg priv]"
        }
    }
} reason]
if {$previous eq "running"} {resume}
if {$failed} {error $reason}
echo BOOT_OBSERVATION_COMPLETE
shutdown
