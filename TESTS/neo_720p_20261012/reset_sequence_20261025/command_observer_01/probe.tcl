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
proc observe {name} {
    sleep 2
    echo "GPU_$name [read_memory 0xe9001000 32 26]"
    for {set i 0} {$i<3} {incr i} {
        echo "RAW_${name}_$i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
        sleep 2
    }
    set before [lindex [read_memory 0xe900500c 32 1] 0]
    set status [lindex [read_memory 0xe9005004 32 1] 0]
    if {($status&5)==4} {
        write_memory 0xe9005004 32 {1}
        sleep 10
    }
    echo "DEBUG_$name [read_memory 0xe9005000 32 17]"
}
if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Wrong observer"}
observe INITIAL
packet legacy_affine_before {0xc000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0}
observe legacy_affine_before
packet preflight {0x16000000 0x12000000 0x12001000 0x200040 0x400040 0x0 0x0 0x0}
observe preflight
packet zero_width {0x16000000 0x0 0x1000 0x10 0x200020 0x0 0x0 0x0}
observe zero_width
packet preflight_again {0x16000000 0x12000000 0x12001000 0x200040 0x400040 0x0 0x0 0x0}
observe preflight_again
packet matrix_row0 {0x1f000000 0x0 0x10000 0x0 0x0 0x0 0x0 0x0}
observe matrix_row0
packet matrix_invalid_row {0x1f000000 0x3 0x0 0x0 0x0 0x0 0x0 0x0}
observe matrix_invalid_row
packet light {0x21000000 0x0 0x0 0x100 0x0 0x0 0x0 0x0}
observe light
packet material {0x19000000 0x0 0x100 0xffff 0x4020100 0x0 0x0 0x0}
observe material
packet texture {0x18000000 0x1700000 0x10001 0x20 0x0 0x0 0x0 0x0}
observe texture
packet plane {0x1a000000 0x10000 0x0 0x0 0x0 0x0 0x0 0x0}
observe plane
packet invalidate {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0}
observe invalidate
packet legacy_affine_after {0xc000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0}
observe legacy_affine_after
packet invalidate_repeat {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0}
observe invalidate_repeat
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo COMMAND_OBSERVATION_COMPLETE
shutdown
