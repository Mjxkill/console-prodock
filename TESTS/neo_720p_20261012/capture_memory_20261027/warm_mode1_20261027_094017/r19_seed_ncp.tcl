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
proc word {addr} {return [lindex [read_memory $addr 32 1] 0]}
if {[word 0xe9005080]!=0x4e435031 || ([word 0xe9005084]&7)!=4} {error "Observer unavailable"}
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set epoch [expr {1-(([word 0xe9005084]>>5)&1)}]
write_memory 0xe9005084 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer arm timeout"}
echo "ARM_EPOCH $epoch"
write_memory 0xe9005088 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    if {([word 0xe9005084]&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer snapshot timeout"}
set first [read_memory 0xe9005080 32 6]
set second [read_memory 0xe9005080 32 6]
if {$first ne $second} {error "Unstable capture"}
echo "NCP $first"
proc word {addr} {return [lindex [read_memory $addr 32 1] 0]}
if {[word 0xe9005080]!=0x4e435031 || ([word 0xe9005084]&7)!=4} {error "Observer unavailable"}
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set epoch [expr {1-(([word 0xe9005084]>>5)&1)}]
write_memory 0xe9005084 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer arm timeout"}
echo "ARM_EPOCH $epoch"
write_memory 0xe9005088 32 {1}
set ok 0
for {set i 0} {$i<100} {incr i} {
    if {([word 0xe9005084]&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set ok 1;break}
    sleep 1
}
if {!$ok} {error "Observer snapshot timeout"}
set first [read_memory 0xe9005080 32 6]
set second [read_memory 0xe9005080 32 6]
if {$first ne $second} {error "Unstable capture"}
echo "NCP $first"
if {[word 0xe9005088]!=2 || [word 0xe900508c]!=2 || [word 0xe9001004]!=0 || [word 0xe9001008]!=0} {error "NCP witness not established"}
echo NCP_WITNESS_2_2

shutdown
