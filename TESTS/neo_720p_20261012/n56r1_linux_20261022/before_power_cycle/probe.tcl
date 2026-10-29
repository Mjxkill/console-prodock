init
halt
echo "LINUX_CONTEXT [reg pc] [reg priv] [reg satp]"
if {[lindex [reg satp] 2] == 0} {error "Expected Linux address space"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x08192802 16 1] 0] != 0x0073 || [lindex [read_memory 0x08192804 16 1] 0] != 0x1050 || [lindex [read_memory 0x0947d028 32 1] 0] != 3} {error "Running kernel fingerprint differs"}
echo "LINUX_STATE [read_memory 0x947d028 32 1]"
echo "LINUX_JIFFIES [read_memory 0x947bb28 32 2]"
echo "LINUX_LOG_POINTER [read_memory 0x947bae8 32 1]"
echo "LINUX_LOG_LENGTH [read_memory 0x947bae4 32 1]"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/n56r1_linux_20261022/before_power_cycle/kernel_log.bin} 0x9484744 32768
echo "UART_LCR [read_memory 0xf030002c 32 1]"
echo "UART_LSR [read_memory 0xf0300034 32 1]"
echo "LINUX_HALTED_PC [reg pc]"
echo LINUX_LEFT_HALTED
echo BOOT_OBSERVATION_COMPLETE
shutdown
