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
proc packet {name words} {
    if {[llength $words]!=8} {error "Command length"}
    set before [read_memory 0xe9001000 32 26]
    if {[lindex $before 1]!=0} {error "GPU busy before packet"}
    set next [expr {([lindex $before 2]+1)&65535}]
    foreach w $words {
        if {[lindex [read_memory 0xe9001004 32 1] 0]&2} {error "Unexpected FIFO full"}
        write_memory 0xe9001010 32 [list $w]
    }
    set complete 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001000 32 26]
        if {[lindex $after 1]==0 && ([lindex $after 2]&65535)==$next} {set complete 1;break}
        sleep 10
    }
    echo "PACKET_$name $after"
    if {!$complete} {error "GPU completion timeout"}
    foreach j {3 7 9 13 19} {if {[lindex $after $j]!=[lindex $before $j]} {error "GPU error counter $j changed"}}
}
foreach {addr expected} {0xe9005080 0x4e435031 0xe9005088 9 0xe900508c 9 0xe9001008 9 0xe9001034 0} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 anchor changed"}
}
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/seed.bin} 0x11ffffe0 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/zseed.bin} 0x1200ffe0 bin
load_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/source.bin} 0x1201ffe0 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/seed.bin} 0x11ffffe0 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/zseed.bin} 0x1200ffe0 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/source.bin} 0x1201ffe0 bin
echo CPU_SEEDS_VERIFIED
packet TARGET {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0}
packet CLEAR {0x1c000000 0x3 0x5aa5 0x7bde 0x0 0x800010 0x0 0x0}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/clear_color.bin} 0x11ffffe0 4160
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_memory_01/clear_depth.bin} 0x1200ffe0 4160
echo CLEAR_COMPLETE

shutdown
