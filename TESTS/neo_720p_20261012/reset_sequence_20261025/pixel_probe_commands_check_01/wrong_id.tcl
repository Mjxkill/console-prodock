set mode wrong_id

set writes {}
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc sleep {args} {}
proc echo {s} {puts $s}
proc get_reg {args} {return [dict create pc 0x80000004 priv 3 satp 0]}
proc write_memory {addr width words} {
    if {$addr!=0xe9001010 || $width!=32 || [llength $words]!=1} {error "Unexpected write"}
    lappend ::writes [lindex $words 0]
    puts "MOCK_WRITE [lindex $words 0]"
}
proc read_memory {addr width count} {
    if {$width!=32} {error "Unexpected width"}
    switch -- [format %x $addr] {
        80000000 {return {0x10500073 0xffdff06f}}
        e9000000 {return {0x47505531}}
        e9000070 {return {0x02d00500}}
        e9000008 - e900000c {return {0}}
        e9000060 {return {0x1ff8f800}}
        e9005000 {return {0x4e474442}}
        e9005040 {return {0}}
        e9005018 {
            if {[llength $::writes]==0} {return {0 0}}
            if {$::mode eq "rejected"} {return {0x16000000 0}}
            return {0x16000000 0x16000000}
        }
        e9001000 {
            if {$count!=26} {error "Expected full GPU counters"}
            set gpu [lrepeat 26 0]
            lset gpu 0 0x424c5432
            if {$::mode eq "wrong_id"} {lset gpu 0 0}
            if {$::mode eq "stale"} {lset gpu 2 7}
            if {$::mode eq "pre_error"} {lset gpu 13 1}
            if {[llength $::writes]==8} {
                if {$::mode eq "timeout"} {lset gpu 1 1} else {lset gpu 2 1}
                if {$::mode eq "rejected"} {lset gpu 13 1}
            }
            return $gpu
        }
        default {error "Unexpected address $addr"}
    }
}
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
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=0} {error "GPU has already executed/queued commands; initial capture ambiguous"}
foreach index {3 7 9 13 19} {
    if {[lindex $gpu $index]!=0} {error "Unexpected GPU error before first command"}
}
if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Wrong debug observer"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
foreach w {0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0} {
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==1} {set complete 1; break}
    sleep 10
}
echo "GPU_AFTER $gpu"
for {set i 0} {$i<3} {incr i} {
    echo "RAW_AFTER_$i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
    sleep 2
}
if {!$complete} {error "First TARGET did not terminate"}
echo TARGET_CAPTURE_REQUEST_COMPLETE
if {[llength $writes]!=8} {error "Wrong packet size"}
set expected {0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0}
foreach a $writes b $expected {if {$a!=$b} {error "Wrong packet contents"}}
echo OFFLINE_COMMAND_CHECK_PASS
