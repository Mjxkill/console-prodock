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

proc single {address} {
 set row [read_memory $address 32 1]
 if {[llength $row]!=1} {error "Single-word read length differs"}
 set value [lindex $row 0]
 if {$value<0 || $value>0xffffffff} {error "Read word out of range"}
 return $value
}
proc fresh {label} {
 set control [list [single 0xe9002000] [single 0xe9002004] [single 0xe9002008]]
 echo "UTNA_FRESH $label $control"
 if {[lindex $control 0]!=0x55544e41 || [lindex $control 1]!=0 || [lindex $control 2]!=0} {error "UTNA control not fresh"}
}
fresh BEFORE
echo "UTNA_READ 0 forward 0 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 0 forward 1 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 0 forward 2 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 0 forward 3 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 0 forward 4 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 0 forward 5 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 0 forward 6 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 0 forward 7 0xe9002084 [single 0xe9002084]"
echo "UTNA_READ 0 reverse 0 0xe9002084 [single 0xe9002084]"
echo "UTNA_READ 0 reverse 1 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 0 reverse 2 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 0 reverse 3 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 0 reverse 4 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 0 reverse 5 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 0 reverse 6 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 0 reverse 7 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 0 interleaved 0 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 0 interleaved 1 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 0 interleaved 2 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 0 interleaved 3 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 0 interleaved 4 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 0 interleaved 5 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 0 interleaved 6 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 0 interleaved 7 0xe9002084 [single 0xe9002084]"
fresh PASS0
echo "UTNA_READ 1 forward 0 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 1 forward 1 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 1 forward 2 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 1 forward 3 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 1 forward 4 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 1 forward 5 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 1 forward 6 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 1 forward 7 0xe9002084 [single 0xe9002084]"
echo "UTNA_READ 1 reverse 0 0xe9002084 [single 0xe9002084]"
echo "UTNA_READ 1 reverse 1 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 1 reverse 2 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 1 reverse 3 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 1 reverse 4 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 1 reverse 5 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 1 reverse 6 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 1 reverse 7 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 1 interleaved 0 0xe9002000 [single 0xe9002000]"
echo "UTNA_READ 1 interleaved 1 0xe9002040 [single 0xe9002040]"
echo "UTNA_READ 1 interleaved 2 0xe9002004 [single 0xe9002004]"
echo "UTNA_READ 1 interleaved 3 0xe9002044 [single 0xe9002044]"
echo "UTNA_READ 1 interleaved 4 0xe9002008 [single 0xe9002008]"
echo "UTNA_READ 1 interleaved 5 0xe9002048 [single 0xe9002048]"
echo "UTNA_READ 1 interleaved 6 0xe9002080 [single 0xe9002080]"
echo "UTNA_READ 1 interleaved 7 0xe9002084 [single 0xe9002084]"
fresh PASS1

echo R19_AFTER_READS
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

fresh AFTER
echo UTNA_READONLY_DONE
shutdown
