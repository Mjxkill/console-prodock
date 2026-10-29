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
load_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/pattern.bin} 0x12000000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/read1.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/read2.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/stage_head.bin} 0x10000000 4096
load_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/pattern.bin} 0xa000f000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/ilm_read.bin} 0xa000f000 4096
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU command port"}
set old_font [lindex [read_memory 0xe9001014 32 1] 0]
write_memory 0xe9001014 32 {0x321}
echo "NEO_GPU_FONT_WRITE [read_memory 0xe9001014 32 1]"
write_memory 0xe9001014 32 [list $old_font]
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12001000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/gpu_ffff.bin} 0x12000000 4096
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/gpu_0000.bin} 0x12000000 4096
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0xaaaa}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/gpu_aaaa.bin} 0x12000000 4096
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x5555}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_COMMAND_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU command did not complete"}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_ddr_n36r0_reload2/gpu_5555.bin} 0x12000000 4096
echo "NEO_GPU_ERRORS [read_memory 0xe900100c 32 1] [read_memory 0xe900101c 32 1] [read_memory 0xe9001024 32 1]"
shutdown
