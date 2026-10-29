riscv expose_csrs 1994,1996,2000
init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected M-mode parking, no Linux"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU is not parked"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Not Neo 1280x720 geometry"}
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
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
sleep 200
snapshot RGB0
sleep 1000
snapshot RGB1
echo SCAN_OBSERVER_TRIAL_COMPLETE
shutdown
