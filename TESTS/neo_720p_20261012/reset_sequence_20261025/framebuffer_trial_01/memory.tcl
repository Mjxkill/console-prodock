riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
set registers [get_reg -force {pc priv satp}]
set pc [dict get $registers pc]
if {($pc!=0x80000000 && $pc!=0x80000004) || [dict get $registers priv]!=3 || [dict get $registers satp]!=0} {error "Expected parked CPU in M mode, no Linux"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000000 32 1] 0]!=0x47505531 || [lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong GPU/geometry"}
echo "PARKED_R15 $pc"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_00.bin} 0x0 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_01.bin} 0x1000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_02.bin} 0x10000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_03.bin} 0x100000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_04.bin} 0x1000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_05.bin} 0x1700000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_06.bin} 0x1700800 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_07.bin} 0x1701000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_08.bin} 0x2000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_09.bin} 0x4000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_10.bin} 0x8000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_11.bin} 0x10000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_12.bin} 0x12000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_13.bin} 0x20000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_14.bin} 0x30000000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/pattern_15.bin} 0x3ffff800 bin
echo ALL_REGIONS_WRITTEN
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_00.bin} 0x0 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_01.bin} 0x1000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_02.bin} 0x10000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_03.bin} 0x100000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_04.bin} 0x1000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_05.bin} 0x1700000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_06.bin} 0x1700800 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_07.bin} 0x1701000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_08.bin} 0x2000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_09.bin} 0x4000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_10.bin} 0x8000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_11.bin} 0x10000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_12.bin} 0x12000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_13.bin} 0x20000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_14.bin} 0x30000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_0_15.bin} 0x3ffff800 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_00.bin} 0x0 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_01.bin} 0x1000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_02.bin} 0x10000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_03.bin} 0x100000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_04.bin} 0x1000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_05.bin} 0x1700000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_06.bin} 0x1700800 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_07.bin} 0x1701000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_08.bin} 0x2000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_09.bin} 0x4000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_10.bin} 0x8000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_11.bin} 0x10000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_12.bin} 0x12000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_13.bin} 0x20000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_14.bin} 0x30000000 2048
dump_image {/home/michael/console/TESTS/neo_720p_20261012/reset_sequence_20261025/framebuffer_trial_01/read_1_15.bin} 0x3ffff800 2048
echo MEMORY_CAPTURE_COMPLETE

shutdown
