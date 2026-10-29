riscv expose_csrs 1994,1996,2000
init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Unexpected CPU after reload"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU not parked"}
if {[lindex [read_memory 0x80000000 32 2] 0]!=0x10500073} {error "Parking ROM differs"}
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong geometry"}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
echo "SCAN_DISABLED [read_memory 0xe9000000 32 32]"
load_image {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/r8_rgb_only/framebuffer.bin} 0x1700000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/r8_rgb_only/framebuffer.bin} 0x1700000 bin
write_memory 0xe9000004 32 {0x1700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 100
echo "SCAN_RGB0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "SCAN_RGB1 [read_memory 0xe9000000 32 32]"
echo SCANOUT_TRIAL_COMPLETE
shutdown
