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

proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_FRESH $gpu"
if {[lindex $gpu 0]!=0x424c5432} {error "GPU signature differs"}
foreach index {1 2 3 7 9 13 19} {
    if {[lindex $gpu $index]!=0} {error "GPU is not fresh after reload"}
}
set ncp [read_memory 0xe9005080 32 7]
echo "NCP_FRESH $ncp"
if {[lindex $ncp 0]!=0x4e435031 || [lindex $ncp 2]!=0 || [lindex $ncp 3]!=0} {
    error "Observer is not fresh after reload"
}
set beat [word 0xe9005098]
set frame [word 0xe9000018]
sleep 200
set frame2 [word 0xe9000018]
if {$frame2==$frame || [word 0xe9005098]==$beat} {error "Video or GPU clock stopped"}
echo "FRAME_PROGRESS $frame $frame2"
echo R19_RELOADED_PARKED_BARS
shutdown
