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

shutdown
