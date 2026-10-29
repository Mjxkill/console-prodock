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
echo "PARKED_CPU $pc"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
foreach addr {0xe9001004 0xe9001008 0xe9001034 0xe9005088 0xe900508c} {
    if {[lindex [read_memory $addr 32 1] 0]!=0} {error "R19 fresh state mismatch"}
}
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/legacy_seed.bin} 0x800000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/legacy_seed.bin} 0x800000 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/color_seed.bin} 0x11ffffe0 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/color_seed.bin} 0x11ffffe0 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/depth_seed.bin} 0x1200ffe0 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_clear_isolate_01/depth_seed.bin} 0x1200ffe0 bin
echo SEEDS_READY

shutdown
