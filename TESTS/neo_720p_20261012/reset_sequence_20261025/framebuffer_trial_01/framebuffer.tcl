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
snapshot DISABLED
load_image {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/r8_rgb_only/framebuffer.bin} 0x01700000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/r8_rgb_only/framebuffer.bin} 0x01700000 bin
echo FRAME_VERIFIED
write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 300
snapshot RGB0
sleep 1000
snapshot RGB1
echo FRAMEBUFFER_TRIAL_COMPLETE

shutdown
