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
echo "PARKED_CPU $pc"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
set cc [get_reg -force {csr1994}]
if {[dict get $cc csr1994]!=0} {error "Cache control is not disabled"}
echo "CACHE_CONTROL [dict get $cc csr1994]"
foreach {addr expected} {
  0xe9001000 0x424c5432
  0xe9005080 0x4e435031 0xe9005088 2 0xe900508c 2
  0xe9001004 0 0xe9001008 2 0xe9001034 1 0xe900500c 2
} {
  if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 COPY anchor changed"}
}
echo R19_COPY_ANCHOR_CONFIRMED

shutdown
