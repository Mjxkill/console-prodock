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

echo "NCP_RAW_BEFORE_ASSERT [read_memory 0xe9005080 32 7]"
foreach {addr expected} {
  0xe9005080 0x4e435031 0xe9005088 0 0xe900508c 0
  0xe9001004 0 0xe9001008 0 0xe9001034 0
} {
  if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "Unexpected idle GPU/NCP counters"}
}
echo "NCP_COUNTERS [read_memory 0xe9005088 32 2]"
echo "WARM_CHECK_0"

set u [read_memory 0xe9002000 32 3]
echo "RESTORED_UTNA $u"
if {[lindex $u 0]!=0x55544e41 || [lindex $u 1]!=0 || [lindex $u 2]!=0} {error "Restored UTNA not fresh"}
echo RESTORED_UTNA_FRESH

shutdown
