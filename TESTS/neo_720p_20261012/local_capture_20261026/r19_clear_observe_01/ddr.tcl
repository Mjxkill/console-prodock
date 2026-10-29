init
halt
riscv set_enable_virt2phys off
set registers [get_reg -force {pc priv satp}]
set pc [dict get $registers pc]
if {($pc!=0x80000000 && $pc!=0x80000004) || [dict get $registers priv]!=3 || [dict get $registers satp]!=0} {error "Expected parked CPU in M mode, no Linux"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000000 32 1] 0]!=0x47505531 || [lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong GPU/geometry"}
echo "PARKED_CPU $pc"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}

foreach {addr expected} {0xe9005080 0x4e435031 0xe9005088 9 0xe900508c 9 0xe9001004 1 0xe9001008 10 0xe9001034 0} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 stalled-state anchor changed"}
}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_observe_01/color.bin} 0x11ffffe0 4160
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_observe_01/depth.bin} 0x1200ffe0 4160
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_observe_01/source.bin} 0x1201ffe0 16448
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo "GPU_FINAL [read_memory 0xe9001000 32 26]"
echo DDR_OBSERVATION_COMPLETE

shutdown
