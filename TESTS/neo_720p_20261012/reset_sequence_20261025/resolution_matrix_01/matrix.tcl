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
write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 150
if {[lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Commit pending"}
write_memory 0xe900002c 32 {1}
sleep 100
echo "MODE_0_3_0 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_1 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_2 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_3 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_4 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_5 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_6 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_0_3_7 [read_memory 0xe9000000 32 30]"
sleep 40
write_memory 0xe9000008 32 {7}
write_memory 0xe900000c 32 {1}
sleep 150
if {[lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Commit pending"}
write_memory 0xe900002c 32 {1}
sleep 100
echo "MODE_1_7_0 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_1 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_2 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_3 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_4 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_5 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_6 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_1_7_7 [read_memory 0xe9000000 32 30]"
sleep 40
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 150
if {[lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Commit pending"}
write_memory 0xe900002c 32 {1}
sleep 100
echo "MODE_2_3_0 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_1 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_2 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_3 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_4 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_5 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_6 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_2_3_7 [read_memory 0xe9000000 32 30]"
sleep 40
write_memory 0xe9000008 32 {7}
write_memory 0xe900000c 32 {1}
sleep 150
if {[lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Commit pending"}
write_memory 0xe900002c 32 {1}
sleep 100
echo "MODE_3_7_0 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_1 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_2 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_3 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_4 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_5 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_6 [read_memory 0xe9000000 32 30]"
sleep 40
echo "MODE_3_7_7 [read_memory 0xe9000000 32 30]"
sleep 40
echo MATRIX_COMPLETE

shutdown
