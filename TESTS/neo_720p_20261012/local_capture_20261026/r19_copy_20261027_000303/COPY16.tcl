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
proc packet {words} {
    set before [read_memory 0xe9001000 32 26]
    if {[lindex $before 1]!=0} {error "GPU busy before command"}
    set next [expr {([lindex $before 2]+1)&65535}]
    foreach w $words {
        if {[lindex [read_memory 0xe9001004 32 1] 0]&2} {error "FIFO full"}
        write_memory 0xe9001010 32 [list $w]
    }
    set completed 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001000 32 26]
        if {[lindex $after 1]==0 && [lindex $after 2]==$next} {set completed 1;break}
        sleep 2
    }
    echo "GPU_BEFORE $before"
    echo "GPU_AFTER $after"
    echo "COMMAND_COMPLETE $completed"
}
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
proc word {addr} {return [lindex [read_memory $addr 32 1] 0]}
if {[word 0xe9005080]!=0x4e435031 || ([word 0xe9005084]&7)!=4} {error "Observer unavailable"}
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set epoch [expr {1-(([word 0xe9005084]>>5)&1)}]
write_memory 0xe9005084 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer arm timeout"}
echo "ARM_EPOCH $epoch"
packet {0x1d000000 0x808000 0x100001 0x20 0x0 0x0 0x100001 0x0}
write_memory 0xe9005088 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    if {([word 0xe9005084]&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer snapshot timeout"}
set first [read_memory 0xe9005080 32 6]
set second [read_memory 0xe9005080 32 6]
if {$first ne $second} {error "Unstable capture"}
echo "NCP $first"
gpu_snapshot after
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_copy_20261027_000303/COPY16_color.bin} 0x800000 4160
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_copy_20261027_000303/COPY16_source.bin} 0x807fe0 96
dump_image {/home/michael/console/TESTS/neo_720p_20261012/local_capture_20261026/r19_copy_20261027_000303/COPY16_depth.bin} 0x80ffe0 4160
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo CASE_OBSERVED

shutdown
