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

echo "NCP_RAW_BEFORE_ASSERT [read_memory 0xe9005080 32 7]"
foreach {addr expected} {
  0xe9005080 0x4e435031 0xe9005088 0 0xe900508c 0
  0xe9001004 0 0xe9001008 0 0xe9001034 0
} {
  if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "Unexpected idle GPU/NCP counters"}
}
echo "NCP_COUNTERS [read_memory 0xe9005088 32 2]"
echo "WARM_CHECK_0"

# Only observer command SNAPSHOT=2. No other command is issued.
proc single {address} {
    set row [read_memory $address 32 1]
    if {[llength $row]!=1} {error "Single read length differs"}
    set value [lindex $row 0]
    if {$value<0 || $value>0xffffffff} {error "Invalid word"}
    return $value
}
proc status {} {return [list [single 0xe9002000] [single 0xe9002004] [single 0xe9002008]]}
proc idle {label expected} {
    set control [status]
    echo "SNAPSHOT_CONTROL $label $control"
    if {[lindex $control 0]!=0x55544e41 || [lindex $control 1]!=0 || [lindex $control 2]!=$expected} {error "Control differs"}
}
idle INITIAL 0
set initial [list [single 0xe9002040] [single 0xe9002044] [single 0xe9002048]]
echo "SNAPSHOT_INITIAL_BANK $initial"
if {[lindex $initial 0]!=0 || [lindex $initial 1]!=0 || [lindex $initial 2]!=0} {error "Bank not fresh"}
echo "SNAPSHOT_WRITE 2"
write_memory 0xe900200c 32 {2}
set deadline [expr {[clock milliseconds]+2000}]
set acknowledged 0
for {set poll 0} {$poll<100} {incr poll} {
    set value [status]
    if {[lindex $value 0]!=0x55544e41} {error "Observer identity changed"}
    set flags [lindex $value 1]
    set sequence [lindex $value 2]
    if {$flags&2} {error "SNAPSHOT rejected"}
    if {$sequence!=0 && $sequence!=1} {error "Unexpected sequence"}
    if {$flags==0 && $sequence==1} {set acknowledged 1;break}
    if {[clock milliseconds]>=$deadline} {break}
    sleep 2
}
if {!$acknowledged} {error "SNAPSHOT acknowledgement timeout"}
echo "SNAPSHOT_ACK 1"
idle ACK 1
for {set passage 0} {$passage<2} {incr passage} {
    foreach address {0xe9002000 0xe9002004 0xe9002008 0xe9002040 0xe9002044 0xe9002048} {
        echo "SNAPSHOT_READ $passage pre $address [single $address]"
    }
    foreach count {3 32} {
        set words [read_memory 0xe9002040 32 $count]
        echo "SNAPSHOT_BLOCK $passage $count $words"
        if {[llength $words]!=$count} {error "Block length differs"}
    }
    foreach address {0xe9002000 0xe9002004 0xe9002008 0xe9002040 0xe9002044 0xe9002048} {
        echo "SNAPSHOT_READ $passage post $address [single $address]"
    }
    idle "PASS$passage" 1
}
# Completion marker is not a PASS: Python validates every captured header.
echo SNAPSHOT_READS_DONE

shutdown
