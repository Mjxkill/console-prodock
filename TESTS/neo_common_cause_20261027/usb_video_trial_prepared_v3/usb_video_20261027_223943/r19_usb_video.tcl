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
foreach label {T0 T100 T200 T1200} {
    if {$label eq "T100" || $label eq "T200"} {sleep 100}
    if {$label eq "T1200"} {sleep 1000}
    echo "VIDEO_TIME $label [clock milliseconds]"
    echo "VIDEO_SCAN $label [read_memory 0xe9000000 32 30]"
    echo "VIDEO_GPU $label [read_memory 0xe9001000 32 26]"
    echo "VIDEO_GPU_DEBUG $label [read_memory 0xe9005000 32 17]"
    echo "VIDEO_SCAN_DEBUG $label [read_memory 0xe9006000 32 17]"
    echo "USB_TRACE_STATUS $label [read_memory 0xe9002000 32 3]"
}
echo VIDEO_READONLY_DONE

# Observer-only writes: UTNA command address. No reset, GPU or DDR write.
proc utna_status {} {
    set value [read_memory 0xe9002000 32 3]
    if {[llength $value]!=3 || [lindex $value 0]!=0x55544e41} {error "UTNA identity/length differs"}
    return $value
}
proc utna_idle {expected label} {
    set value [utna_status]
    echo "UTNA_STATUS $label $value"
    if {[lindex $value 1]!=0 || [lindex $value 2]!=$expected} {error "UTNA not idle at expected sequence"}
}
proc utna_command {command expected label} {
    if {$command!=1 && $command!=6 && $command!=2} {error "Forbidden UTNA command"}
    utna_idle [expr {($expected-1)&0xffffffff}] "${label}_before"
    echo "UTNA_WRITE $label $command $expected [clock milliseconds]"
    write_memory 0xe900200c 32 [list $command]
    set deadline [expr {[clock milliseconds]+2000}]
    set acknowledged 0
    for {set poll 0} {$poll<100} {incr poll} {
        set value [utna_status]
        set status [lindex $value 1]
        set seq [lindex $value 2]
        if {$status & 2} {echo "UTNA_REJECT $label $value"; error "UTNA command rejected"}
        if {$seq!=$expected && $seq!=[expr {($expected-1)&0xffffffff}]} {echo "UTNA_BAD_SEQ $label $value"; error "UTNA unexpected sequence"}
        if {$status==0 && $seq==$expected} {set acknowledged 1; break}
        if {[clock milliseconds]>=$deadline} {break}
        sleep 2
    }
    if {!$acknowledged} {echo "UTNA_TIMEOUT $label $value"; error "UTNA acknowledgement timeout"}
    utna_idle $expected "${label}_bank_before"
    set first [read_memory 0xe9002040 32 32]
    echo "UTNA_BANK $label $command $expected $first"
    utna_idle $expected "${label}_bank_middle"
    set second [read_memory 0xe9002040 32 32]
    echo "UTNA_BANK_REPEAT $label $second"
    utna_idle $expected "${label}_bank_after"
    if {[llength $first]!=32 || [llength $second]!=32} {error "UTNA bank length differs"}
    for {set i 0} {$i<32} {incr i} {
        if {[lindex $first $i]!=[lindex $second $i]} {error "UTNA bank unstable at word $i"}
    }
    if {[lindex $first 0]!=0x55544e41 || [lindex $first 1]!=1 || [lindex $first 2]!=$command} {error "UTNA captured header differs"}
    return $first
}
set control [utna_status]
echo "UTNA_INITIAL $control"
if {[lindex $control 1]!=0 || [lindex $control 2]!=0} {error "Expected freshly restored UTNA control state"}
set sequence [lindex $control 2]
set sequence [expr {($sequence+1)&0xffffffff}]
set preclear [utna_command 1 $sequence ARM]
sleep 200
set sequence [expr {($sequence+1)&0xffffffff}]
set disarm [utna_command 6 $sequence DISARM]
if {([lindex $disarm 31]&0x400)==0} {error "Disarm bank did not capture prior armed state"}
if {[lindex $disarm 3]==0} {error "No ticks observed during armed window"}
sleep 100
set sequence [expr {($sequence+1)&0xffffffff}]
set stopped [utna_command 2 $sequence STOPPED]
if {[lindex $stopped 31]&0x400} {error "UTNA still armed after disarm"}
if {[lindex $stopped 3]!=[expr {([lindex $disarm 3]+1)&0xffffffff}]} {error "Final disarm tick differs from RTL contract"}
sleep 100
set sequence [expr {($sequence+1)&0xffffffff}]
set stable [utna_command 2 $sequence STABLE]
if {[lindex $stable 31]&0x400} {error "UTNA rearmed unexpectedly"}
if {[lindex $stable 3]!=[lindex $stopped 3]} {error "Disarmed tick counter is not stable"}
echo "UTNA_PROTOCOL_DONE $sequence [lindex $disarm 3] [lindex $stopped 3] [lindex $stable 3]"
echo "VIDEO_TIME POST_USB [clock milliseconds]"
echo "VIDEO_SCAN POST_USB [read_memory 0xe9000000 32 30]"
echo "VIDEO_GPU POST_USB [read_memory 0xe9001000 32 26]"
echo "USB_TRACE_STATUS POST_USB [utna_status]"
echo USB_VIDEO_DONE

shutdown
