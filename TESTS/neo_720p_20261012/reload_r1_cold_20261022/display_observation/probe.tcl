init
halt
set failed [catch {
    echo "LINUX_CONTEXT [reg pc] [reg priv] [reg satp]"
    if {[lindex [reg satp] 2]==0} {error "Expected Linux address space"}
    riscv set_enable_virt2phys off
    if {[lindex [read_memory 0x08192802 16 1] 0]!=0x0073 || [lindex [read_memory 0x08192804 16 1] 0]!=0x1050 || [lindex [read_memory 0x0947d028 32 1] 0]!=3} {error "Linux fingerprint differs"}
    if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong display geometry"}
    for {set i 0} {$i<3} {incr i} {
        echo "DISPLAY_SAMPLE $i [read_memory 0xe9000000 32 32]"
        echo "GPU_SAMPLE $i [read_memory 0xe9001000 32 20]"
        echo "UART_SAMPLE $i [read_memory 0xf030002c 32 3]"
        resume
        sleep 100
        halt
        echo "CPU_SAMPLE $i [reg pc] [reg priv]"
    }
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/display_observation/kernel_log.bin} 0x09484744 32768
} reason]
resume
echo LINUX_RESUMED
if {$failed} {error $reason}
echo DISPLAY_OBSERVATION_COMPLETE
shutdown
