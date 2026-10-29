# PREPARE ONLY. No init/transport/CPU resume here. Root owns the controller,
# board identity, R19 SHA, Neo lock, host watchdog and unconditional restoration.
# Source only inside that reviewed controller after its exact R19 guards.
# One write to NGDB+4 requests an observation-only snapshot; no GPU command.
proc microdma_capture_r19 {label} {
    if {![regexp {^[A-Za-z0-9_]+$} $label]} {error "Unsafe capture label"}
    set base 0xe9005000
    set id [lindex [read_memory $base 32 1] 0]
    if {$id != 0x4e474442} {error "R19 NGDB identity mismatch"}
    set before [read_memory 0xe9005004 32 3]
    set status [lindex $before 0]
    set sequence [lindex $before 2]
    if {($status & 5) != 4} {error "NGDB not ready or request already active"}
    echo "MICRODMA_${label}_BEFORE $before"
    mww 0xe9005004 1
    set complete 0
    for {set tries 0} {$tries < 32} {incr tries} {
        set state [read_memory 0xe9005004 32 3]
        if {([lindex $state 0] & 7) == 6 &&
            [lindex $state 2] == (($sequence + 1) & 0xffffffff)} {
            set complete 1
            break
        }
        sleep 2
    }
    if {!$complete} {error "NGDB snapshot did not complete; do not interpret stale payload"}
    # These ten words are held coherent snapshot data: received,last,live[255:0].
    # The headers at +18/+1c are separate asynchronous diagnostic taps.
    set first [read_memory 0xe9005010 32 12]
    set second [read_memory 0xe9005010 32 12]
    foreach i {0 1 4 5 6 7 8 9 10 11} {
        if {[lindex $first $i] != [lindex $second $i]} {
            error "Held snapshot changed during read"
        }
    }
    set after [read_memory 0xe9005004 32 3]
    if {([lindex $after 0] & 7) != 6 || [lindex $after 2] != (($sequence + 1) & 0xffffffff)} {
        error "NGDB snapshot identity changed"
    }
    echo "MICRODMA_${label}_SNAPSHOT_A $first"
    echo "MICRODMA_${label}_SNAPSHOT_B $second"
    echo "MICRODMA_${label}_AFTER $after"
    echo "MICRODMA_${label}_GPU [read_memory 0xe9001000 32 26]"
    return $first
}
