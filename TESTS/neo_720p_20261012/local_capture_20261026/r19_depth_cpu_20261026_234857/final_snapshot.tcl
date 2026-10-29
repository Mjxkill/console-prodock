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
set cc [get_reg -force {csr1994}]
if {[dict get $cc csr1994]!=0} {error "Cache control is not disabled"}
echo "CACHE_CONTROL [dict get $cc csr1994]"
proc gpu_snapshot {label} {
    if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Debug signature"}
    if {([lindex [read_memory 0xe9005004 32 1] 0]&5)!=4} {error "Debug not ready"}
    set expected [expr {([lindex [read_memory 0xe900500c 32 1] 0]+1)&0xffffffff}]
    write_memory 0xe9005004 32 {1}
    set complete 0
    for {set i 0} {$i<50} {incr i} {
        sleep 1
        if {[lindex [read_memory 0xe9005004 32 1] 0]==6 && [lindex [read_memory 0xe900500c 32 1] 0]==$expected} {set complete 1;break}
    }
    if {!$complete} {error "Snapshot timeout"}
    set first [read_memory 0xe9005020 32 8]
    set second [read_memory 0xe9005020 32 8]
    if {$first ne $second || [lindex [read_memory 0xe900500c 32 1] 0]!=$expected} {error "Unstable snapshot"}
    echo "GPU_SNAPSHOT $label [read_memory 0xe9005000 32 16]"
    echo "GPU_COUNTERS $label [read_memory 0xe9001000 32 26]"
    echo "RAW_HEADERS $label [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
}
gpu_snapshot final
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_depth_cpu_20261026_234857/final_color.bin} 0x800000 4160
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_depth_cpu_20261026_234857/final_depth.bin} 0x80ffe0 4160
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo FINAL_OBSERVED

shutdown
