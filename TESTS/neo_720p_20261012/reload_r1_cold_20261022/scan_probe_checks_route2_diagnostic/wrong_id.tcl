set mode wrong_id

set sequence 4294967295
set word_reads 0
proc echo {value} {puts $value}
proc sleep {ms} {}
proc write_memory {address width words} {
    global sequence mode
    if {$address!=0xe9006004 || $width!=32 || $words ne {1}} {error "Unexpected snapshot command"}
    if {$mode ne "stale_sequence"} {set sequence [expr {($sequence+1)&0xffffffff}]}
}
proc read_memory {address width count} {
    global sequence word_reads mode
    if {$address==0xe9006000} {
        if {$mode eq "wrong_id"} {return {0}}
        return {0x4e474442}
    }
    if {$address==0xe9006004} {
        if {$mode eq "changed_status" && $word_reads>=2} {return {2}}
        return {6}
    }
    if {$address==0xe900600c} {
        if {$mode eq "changed_sequence" && $word_reads>=2} {return [list [expr {$sequence+1}]]}
        return [list $sequence]
    }
    if {$address==0xe9006020} {
        incr word_reads
        set words {0x00610163 0x1700000 0x00a1004f 403284 403282 403280 0x5c0000 0x53434e01}
        if {$mode eq "changed_words" && $word_reads>=2} {lset words 3 403285}
        if {$mode eq "wrong_signature"} {lset words 7 0}
        return $words
    }
    if {$address==0xe9000000 && $count==32} {return [lrepeat 32 0]}
    error "Unexpected read address"
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

if {[catch {snapshot TEST} reason]} {puts stderr $reason; exit 1}
exit 0
