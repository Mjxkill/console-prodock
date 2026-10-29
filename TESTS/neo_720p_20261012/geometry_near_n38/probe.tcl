riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
echo GEOM_PARKED
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU ABI"}
if {[lindex [read_memory 0xe9001048 32 1] 0] != 0x47334431} {error "Missing G3D1"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be idle and disabled"}
}
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_v1_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_invalid_commands [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set before_culled [lindex [read_memory 0xe9001058 32 1] 0]
set before_clipped [lindex [read_memory 0xe900105c 32 1] 0]
set before_slivers [lindex [read_memory 0xe9001060 32 1] 0]
set before_passed_pixels [lindex [read_memory 0xe900103c 32 1] 0]
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_0.bin} 0x800000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_0.bin} 0x800000 bin
echo "GEOM_INITIAL_OK 0"
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_1.bin} 0x900000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_1.bin} 0x900000 bin
echo "GEOM_INITIAL_OK 1"
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_2.bin} 0x1700000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/initial_2.bin} 0x1700000 bin
echo "GEOM_INITIAL_OK 2"
set saved_font_address [lindex [read_memory 0xe9001014 32 1] 0]
write_memory 0xe9001014 32 {0x800}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
write_memory 0xe9001018 32 {90}
write_memory 0xe9001018 32 {165}
set expected_done [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x1600180}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 0"}
echo "GEOM_COMMAND_OK 0"
write_memory 0xe9001010 32 {0x17000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 1"}
echo "GEOM_COMMAND_OK 1"
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x3}
write_memory 0xe9001010 32 {0x1084}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 2"}
echo "GEOM_COMMAND_OK 2"
write_memory 0xe9001010 32 {0x18000000}
write_memory 0xe9001010 32 {0x1700000}
write_memory 0xe9001010 32 {0x200020}
write_memory 0xe9001010 32 {0x40}
write_memory 0xe9001010 32 {0xa}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 3"}
echo "GEOM_COMMAND_OK 3"
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x4000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500032}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 4"}
echo "GEOM_COMMAND_OK 4"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 5"}
echo "GEOM_COMMAND_OK 5"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 6"}
echo "GEOM_COMMAND_OK 6"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 7"}
echo "GEOM_COMMAND_OK 7"
write_memory 0xe9001010 32 {0x21000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x8001}
write_memory 0xe9001010 32 {0xc00040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 8"}
echo "GEOM_COMMAND_OK 8"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x17}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 9"}
echo "GEOM_COMMAND_OK 9"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748020}
write_memory 0xe9001010 32 {0x90001}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 10"}
echo "GEOM_COMMAND_OK 10"
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "GEOM_COUNTER errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "GEOM_COUNTER lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_v1_rejected)&0xffffffff}]
echo "GEOM_COUNTER v1_rejected $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid_commands)&0xffffffff}]
echo "GEOM_COUNTER invalid_commands $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "GEOM_COUNTER vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "GEOM_COUNTER triangles $delta"
set delta [expr {([lindex [read_memory 0xe9001058 32 1] 0]-$before_culled)&0xffffffff}]
echo "GEOM_COUNTER culled $delta"
set delta [expr {([lindex [read_memory 0xe900105c 32 1] 0]-$before_clipped)&0xffffffff}]
echo "GEOM_COUNTER clipped $delta"
set delta [expr {([lindex [read_memory 0xe9001060 32 1] 0]-$before_slivers)&0xffffffff}]
echo "GEOM_COUNTER slivers $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_passed_pixels)&0xffffffff}]
echo "GEOM_COUNTER passed_pixels $delta"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/actual_0.bin} 0x800000 1048576
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/actual_1.bin} 0x900000 1048576
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_near_n38/actual_2.bin} 0x1700000 1048576
write_memory 0xe9001014 32 {0x800}
write_memory 0xe9001018 32 {0}
write_memory 0xe9001018 32 {0}
write_memory 0xe9001018 32 {60}
write_memory 0xe9001018 32 {66}
write_memory 0xe9001018 32 {66}
write_memory 0xe9001018 32 {64}
write_memory 0xe9001018 32 {64}
write_memory 0xe9001018 32 {64}
write_memory 0xe9001018 32 {64}
write_memory 0xe9001018 32 {66}
write_memory 0xe9001018 32 {66}
write_memory 0xe9001018 32 {60}
write_memory 0xe9001018 32 {16}
write_memory 0xe9001018 32 {16}
write_memory 0xe9001018 32 {32}
write_memory 0xe9001018 32 {0}
write_memory 0xe9001014 32 [list $saved_font_address]
echo GEOM_COMPLETE
shutdown
