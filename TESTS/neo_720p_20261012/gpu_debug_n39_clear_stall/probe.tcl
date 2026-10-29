init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "GPU instrumentation is absent"}
proc snapshot {label} {
    if {([lindex [read_memory 0xe9005004 32 1] 0] & 5) != 4} {error "Debug source not ready or busy"}
    set expected [expr {([lindex [read_memory 0xe900500c 32 1] 0] + 1) & 0xffffffff}]
    write_memory 0xe9005004 32 {1}
    set complete 0
    for {set i 0} {$i < 50} {incr i} {
        sleep 1
        if {[lindex [read_memory 0xe9005004 32 1] 0] == 6 && [lindex [read_memory 0xe900500c 32 1] 0] == $expected} {
            set complete 1
            break
        }
    }
    if {!$complete} {error "GPU snapshot timeout"}
    echo "GPU_SNAPSHOT $label [read_memory 0xe9005000 32 16]"
}
snapshot before
echo GPU_SNAPSHOT_COMPLETE
shutdown
