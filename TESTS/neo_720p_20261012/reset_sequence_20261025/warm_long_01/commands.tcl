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
if {[lindex [read_memory 0xe9001000 32 1] 0]!=0x424c5432} {error "Wrong command ABI"}
proc packet {name words} {
    if {[llength $words]!=8} {error "Packet length"}
    if {[lindex [read_memory 0xe9001004 32 1] 0]!=0} {error "GPU busy before packet"}
    set before [read_memory 0xe9001008 32 2]
    set extra [list [lindex [read_memory 0xe900101c 32 1] 0] [lindex [read_memory 0xe9001024 32 1] 0]]
    set next [expr {([lindex $before 0]+1)&65535}]
    foreach w $words {write_memory 0xe9001010 32 [list $w]}
    set complete 0
    for {set i 0} {$i<100} {incr i} {
        set after [read_memory 0xe9001004 32 3]
        if {[lindex $after 0]==0 && ([lindex $after 1]&65535)==$next} {set complete 1; break}
        sleep 10
    }
    echo "PACKET_$name BEFORE $before AFTER $after"
    if {!$complete} {error "GPU fence timeout"}
    if {[lindex $after 2]!=[lindex $before 1]} {error "GPU error count changed"}
    set extra_after [list [lindex [read_memory 0xe900101c 32 1] 0] [lindex [read_memory 0xe9001024 32 1] 0]]
    if {$extra_after!=$extra} {error "GPU extra errors changed"}
}
packet TARGET {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0}
sleep 2
echo "GPU_TARGET [read_memory 0xe9001000 32 26]"
echo "RAW_TARGET_0 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
echo "RAW_TARGET_1 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
echo "RAW_TARGET_2 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
packet INVALIDATE {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0}
sleep 2
echo "GPU_INVALIDATE [read_memory 0xe9001000 32 26]"
echo "RAW_INVALIDATE_0 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
echo "RAW_INVALIDATE_1 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
echo "RAW_INVALIDATE_2 [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
sleep 2
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo WARM_TRIAL_COMPLETE

shutdown
