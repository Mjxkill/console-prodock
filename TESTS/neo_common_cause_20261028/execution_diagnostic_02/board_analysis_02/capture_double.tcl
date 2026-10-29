
set mode [lindex $argv 0]
set requests 0
set payload_reads 0
proc echo {message} {puts $message}
proc sleep {milliseconds} {}
proc mww {address value} {
    global requests
    if {$address != 0xe9005004 || $value != 1} {error "forbidden write"}
    incr requests
}
proc read_memory {address width count} {
    global mode requests payload_reads
    if {$width != 32} {error "wrong width"}
    if {$address == 0xe9005000 && $count == 1} {
        return [list [expr {$mode eq "bad_id" ? 0 : 0x4e474442}]]
    }
    if {$address == 0xe9005004 && $count == 3} {
        if {!$requests} {return [list [expr {$mode eq "busy" ? 5 : 4}] 16 7]}
        if {$mode eq "timeout"} {return {5 16 7}}
        if {$mode eq "stale"} {return {6 16 7}}
        return {6 16 8}
    }
    if {$address == 0xe9005010 && $count == 12} {
        incr payload_reads
        set words {16 0 469762048 469762048 1 16773893 0 269491209 32 0 0 469762048}
        if {$mode eq "changed" && $payload_reads == 2} {lset words 4 2}
        if {$mode eq "async_tap" && $payload_reads == 2} {lset words 2 0}
        return $words
    }
    if {$address == 0xe9001000 && $count == 26} {return [lrepeat 26 0]}
    error "forbidden read"
}
source [lindex $argv 1]
set failed [catch {microdma_capture_r19 CHECK} message]
puts "OUTCOME failed=$failed writes=$requests payload_reads=$payload_reads message=$message"
if {$mode in {good async_tap}} {
    if {$failed || $requests != 1 || $payload_reads != 2} {exit 1}
} else {
    if {!$failed} {exit 1}
    if {$mode in {bad_id busy} && $requests != 0} {exit 1}
}
