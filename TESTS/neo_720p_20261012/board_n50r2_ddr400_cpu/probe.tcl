riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
echo "NEO_PC [reg pc]"
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
echo "NEO_GPU_BEFORE [read_memory 0xe9001000 32 26]"
echo "NEO_USB_MSC [read_memory 0xe9003000 32 2]"
echo "NEO_USB_TRACE_BEFORE [read_memory 0xe9002000 32 3]"
write_memory 0xe900200c 32 {2}
sleep 20
echo "NEO_USB_TRACE_AFTER [read_memory 0xe9002000 32 3]"
echo "NEO_USB_TRACE_SNAPSHOT [read_memory 0xe9002040 32 32]"
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/pattern.bin} 0x12000000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/read1.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/read2.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/stage_head.bin} 0x10000000 4096
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/pattern.bin} 0xa000f000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/ilm_read.bin} 0xa000f000 4096
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/pattern.bin} 0xa000c000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/pattern.bin} 0xa000c000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/memory_probe.bin} 0xa0000000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/memory_probe.bin} 0xa0000000 bin
resume 0xa0000000
sleep 500
halt
echo "NEO_CPU_PROBE_PC [reg pc]"
echo "NEO_CPU_PROBE_STATUS [read_memory 0xa000e000 32 4]"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/cpu_jtag_written.bin} 0xa000b000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/cpu_written.bin} 0xa000d000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/board_n50r2_ddr400_cpu/jtag_cpu_written.bin} 0x12000000 4096
shutdown
