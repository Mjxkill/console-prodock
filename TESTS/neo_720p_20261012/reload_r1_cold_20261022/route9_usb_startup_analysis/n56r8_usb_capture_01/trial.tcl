init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected M-mode parking, no Linux"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU is not parked"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Not Neo geometry"}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback bars changed"}
echo N56R8_PARKING_BARS_CONFIRMED

proc info_usb {} {
    set words [read_memory 0xe9002000 32 3]
    echo "AHB_INFO $words"
    if {[lindex $words 0]!=0x55544e41} {error "UTNA ID absent"}
    if {[lindex $words 1]!=0} {error "UTNA busy or rejected; no reset permitted"}
    return [lindex $words 2]
}
proc command_usb {value name} {
    set before [info_usb]
    if {$value!=1 && $value!=2 && $value!=4} {error "Forbidden observer command"}
    echo "AHB_WRITE $value"
    write_memory 0xe900200c 32 [list $value]
    set completed 0
    for {set i 0} {$i<40} {incr i} {
        sleep 5
        set words [read_memory 0xe9002004 32 2]
        if {([lindex $words 0]&2)!=0} {error "UTNA command rejected"}
        if {[lindex $words 0]==0 && [lindex $words 1]==(($before+1)&0xffffffff)} {
            set completed 1
            break
        }
    }
    if {!$completed} {error "UTNA snapshot timeout"}
    set bank [read_memory 0xe9002040 32 32]
    set repeated [read_memory 0xe9002040 32 32]
    if {$bank ne $repeated || [info_usb]!=(($before+1)&0xffffffff)} {error "UTNA snapshot changed"}
    if {[lindex $bank 0]!=0x55544e41 || [lindex $bank 1]!=1 || [lindex $bank 2]!=$value} {error "UTNA snapshot identity differs"}
    echo "AHB_BANK_$name [expr {($before+1)&0xffffffff}] $bank"
}

info_usb
set armed_maybe 1
set failed [catch {
    command_usb 1 ARM
    sleep 1000
    command_usb 2 SAMPLE
} reason]
# Disarm only an idle, identified observer; never clear errors or force reset.
set cleanup_failed [catch {command_usb 4 DISARM} cleanup_reason]
if {$cleanup_failed} {echo "AHB_DISARM_FAILED $cleanup_reason"; error $cleanup_reason}
echo AHB_DISARM_CONFIRMED
if {$failed} {error $reason}
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Bars changed after observer"}
echo AHB_TRIAL_COMPLETE
shutdown
