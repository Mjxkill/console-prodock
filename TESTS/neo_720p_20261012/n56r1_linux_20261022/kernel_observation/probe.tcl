init
halt
if {[lindex [reg priv] 2] != 1 || [lindex [reg pc] 2] != 0xc0192806} {error "Not the observed Linux idle point"}
riscv set_enable_virt2phys off
if {[lindex [read_memory 0x08192802 16 1] 0] != 0x0073 || [lindex [read_memory 0x08192804 16 1] 0] != 0x1050} {error "Kernel idle fingerprint differs"}
echo "LINUX_STATE [read_memory 0x947d028 32 1]"
echo "LINUX_JIFFIES [read_memory 0x947bb28 32 2]"
echo "LINUX_LOG_POINTER [read_memory 0x947bae8 32 1]"
echo "LINUX_LOG_LENGTH [read_memory 0x947bae4 32 1]"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/n56r1_linux_20261022/kernel_observation/kernel_log.bin} 0x9484744 32768
echo "UART_LCR [read_memory 0xf030002c 32 1]"
echo "UART_LSR [read_memory 0xf0300034 32 1]"
resume
echo LINUX_RESUMED
echo BOOT_OBSERVATION_COMPLETE
shutdown
