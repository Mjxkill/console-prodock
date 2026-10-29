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
proc snapshot {name} {
    if {[lindex [read_memory 0xe9006000 32 1] 0]!=0x4e474442} {error "Observer ID missing"}
    set before [lindex [read_memory 0xe900600c 32 1] 0]
    write_memory 0xe9006004 32 {1}
    set completed 0
    for {set i 0} {$i<50} {incr i} {
        sleep 1
        set status [lindex [read_memory 0xe9006004 32 1] 0]
        set sequence [lindex [read_memory 0xe900600c 32 1] 0]
        if {$status==6 && $sequence==(($before+1)&0xffffffff)} {set completed 1;break}
    }
    if {!$completed} {error "Snapshot handshake failed"}
    set words [read_memory 0xe9006020 32 8]
    set repeated [read_memory 0xe9006020 32 8]
    if {$words ne $repeated || [lindex [read_memory 0xe900600c 32 1] 0]!=$sequence || [lindex [read_memory 0xe9006004 32 1] 0]!=6} {error "Snapshot changed while being read"}
    if {([lindex $words 7]>>8)!=0x53434e} {error "Scanout snapshot signature differs"}
    echo "SNAP_$name $words"
    echo "SCAN_$name [read_memory 0xe9000000 32 32]"
}

gpu_snapshot first
sleep 100
gpu_snapshot second
sleep 100
gpu_snapshot third
snapshot DISABLED
echo STALLED_SNAPSHOTS_COMPLETE

shutdown
