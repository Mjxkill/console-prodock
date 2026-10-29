
# Passive observer commands only. Version0 is retained as a failure, not ignored.
proc single {address} {
    set row [read_memory $address 32 1]
    if {[llength $row]!=1} {error "Invalid single length"}
    set value [lindex $row 0]
    if {$value<0 || $value>0xffffffff} {error "Invalid single word"}
    return $value
}
proc status {} {return [list [single 0xe9002000] [single 0xe9002004] [single 0xe9002008]]}
proc idle {label expected} {
    set value [status]
    echo "ACTIVITY_CONTROL $label $value"
    if {[lindex $value 0]!=0x55544e41 || [lindex $value 1]!=0 || [lindex $value 2]!=$expected} {error "Unexpected control"}
}
proc capture {label command expected} {
    if {![dict exists {ARM {1 1} DISARM {6 2} STOPPED {2 3} STABLE {2 4}} $label]} {error "Forbidden phase"}
    if {[dict get {ARM {1 1} DISARM {6 2} STOPPED {2 3} STABLE {2 4}} $label] ne [list $command $expected]} {error "Forbidden command"}
    idle "${label}_BEFORE" [expr {$expected-1}]
    echo "ACTIVITY_WRITE $label $command $expected"
    write_memory 0xe900200c 32 [list $command]
    set deadline [expr {[clock milliseconds]+2000}]
    set acknowledged 0
    for {set poll 0} {$poll<100} {incr poll} {
        set value [status]
        if {[lindex $value 0]!=0x55544e41} {error "Observer ID changed"}
        set flags [lindex $value 1]
        set sequence [lindex $value 2]
        if {$flags&2} {error "Observer rejected command"}
        if {$sequence!=$expected && $sequence!=$expected-1} {error "Unexpected sequence"}
        if {$flags==0 && $sequence==$expected} {set acknowledged 1;break}
        if {[clock milliseconds]>=$deadline} {break}
        sleep 2
    }
    if {!$acknowledged} {error "Observer acknowledgement timeout"}
    idle "${label}_ACK" $expected
    set previous {}
    foreach which {first repeat} {
        set words [read_memory 0xe9002040 32 32]
        echo "ACTIVITY_BANK $label $command $expected $which $words"
        if {[llength $words]!=32} {error "Invalid bank length"}
        foreach word $words {if {$word<0 || $word>0xffffffff} {error "Invalid bank word"}}
        if {[lindex $words 0]!=0x55544e41 || [lindex $words 2]!=$command} {error "Bank ID or command differs"}
        set version [lindex $words 1]
        if {$version!=0 && $version!=1} {error "Unsupported version value"}
        if {$version==0} {echo "ACTIVITY_CONTRACT_FAIL $label $which version0"}
        if {$which eq "repeat"} {
            for {set i 0} {$i<32} {incr i} {if {[lindex $words $i]!=[lindex $previous $i]} {error "Bank unstable"}}
        }
        set previous $words
    }
    idle "${label}_AFTER" $expected
}
idle INITIAL 0
capture ARM 1 1
sleep 200
capture DISARM 6 2
sleep 100
capture STOPPED 2 3
sleep 100
capture STABLE 2 4
# The completion marker records collected data; Python retains every failure.
echo ACTIVITY_READS_DONE
