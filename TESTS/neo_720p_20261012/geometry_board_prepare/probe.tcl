init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU ABI"}
if {[lindex [read_memory 0xe9001048 32 1] 0] != 0x47334431} {error "Missing G3D1"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}
if {([lindex [read_memory 0xe9000004 32 1] 0] & 1) != 0} {error "Scanout must be disabled"}
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_v1_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_invalid_commands [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set before_culled [lindex [read_memory 0xe9001058 32 1] 0]
set before_clipped [lindex [read_memory 0xe900105c 32 1] 0]
set before_slivers [lindex [read_memory 0xe9001060 32 1] 0]
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_0.bin} 0x800000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_0.bin} 0x800000 bin
echo "GEOM_INITIAL_OK 0"
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_1.bin} 0x900000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_1.bin} 0x900000 bin
echo "GEOM_INITIAL_OK 1"
load_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_2.bin} 0x1700000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/initial_2.bin} 0x1700000 bin
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
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x20000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 11"}
echo "GEOM_COMMAND_OK 11"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 12"}
echo "GEOM_COMMAND_OK 12"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x80}
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
if {!$complete} {error "GPU fence timeout at command 13"}
echo "GEOM_COMMAND_OK 13"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 14"}
echo "GEOM_COMMAND_OK 14"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xfffe0000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 15"}
echo "GEOM_COMMAND_OK 15"
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
if {!$complete} {error "GPU fence timeout at command 16"}
echo "GEOM_COMMAND_OK 16"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0xb4}
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
if {!$complete} {error "GPU fence timeout at command 17"}
echo "GEOM_COMMAND_OK 17"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 18"}
echo "GEOM_COMMAND_OK 18"
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
if {!$complete} {error "GPU fence timeout at command 19"}
echo "GEOM_COMMAND_OK 19"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0xfffc0000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 20"}
echo "GEOM_COMMAND_OK 20"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0xc8}
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
if {!$complete} {error "GPU fence timeout at command 21"}
echo "GEOM_COMMAND_OK 21"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 22"}
echo "GEOM_COMMAND_OK 22"
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
if {!$complete} {error "GPU fence timeout at command 23"}
echo "GEOM_COMMAND_OK 23"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x4f0000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 24"}
echo "GEOM_COMMAND_OK 24"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0xdc}
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
if {!$complete} {error "GPU fence timeout at command 25"}
echo "GEOM_COMMAND_OK 25"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 26"}
echo "GEOM_COMMAND_OK 26"
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
if {!$complete} {error "GPU fence timeout at command 27"}
echo "GEOM_COMMAND_OK 27"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x20000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 28"}
echo "GEOM_COMMAND_OK 28"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
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
if {!$complete} {error "GPU fence timeout at command 29"}
echo "GEOM_COMMAND_OK 29"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 30"}
echo "GEOM_COMMAND_OK 30"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1e0000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 31"}
echo "GEOM_COMMAND_OK 31"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 32"}
echo "GEOM_COMMAND_OK 32"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x64}
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
if {!$complete} {error "GPU fence timeout at command 33"}
echo "GEOM_COMMAND_OK 33"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 34"}
echo "GEOM_COMMAND_OK 34"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xffe20000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 35"}
echo "GEOM_COMMAND_OK 35"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 36"}
echo "GEOM_COMMAND_OK 36"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x96}
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
if {!$complete} {error "GPU fence timeout at command 37"}
echo "GEOM_COMMAND_OK 37"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 38"}
echo "GEOM_COMMAND_OK 38"
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
if {!$complete} {error "GPU fence timeout at command 39"}
echo "GEOM_COMMAND_OK 39"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0xffff0000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 40"}
echo "GEOM_COMMAND_OK 40"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0xd2}
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
if {!$complete} {error "GPU fence timeout at command 41"}
echo "GEOM_COMMAND_OK 41"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 42"}
echo "GEOM_COMMAND_OK 42"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 43"}
echo "GEOM_COMMAND_OK 43"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x60000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 44"}
echo "GEOM_COMMAND_OK 44"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
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
if {!$complete} {error "GPU fence timeout at command 45"}
echo "GEOM_COMMAND_OK 45"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 46"}
echo "GEOM_COMMAND_OK 46"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x7fffffff}
write_memory 0xe9001010 32 {0x7fffffff}
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
if {!$complete} {error "GPU fence timeout at command 47"}
echo "GEOM_COMMAND_OK 47"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 48"}
echo "GEOM_COMMAND_OK 48"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 49"}
echo "GEOM_COMMAND_OK 49"
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x3}
write_memory 0xe9001010 32 {0x0}
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
if {!$complete} {error "GPU fence timeout at command 50"}
echo "GEOM_COMMAND_OK 50"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740001}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 51"}
echo "GEOM_COMMAND_OK 51"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x1010003}
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
if {!$complete} {error "GPU fence timeout at command 52"}
echo "GEOM_COMMAND_OK 52"
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
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
if {!$complete} {error "GPU fence timeout at command 53"}
echo "GEOM_COMMAND_OK 53"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 54"}
echo "GEOM_COMMAND_OK 54"
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
if {!$complete} {error "GPU fence timeout at command 55"}
echo "GEOM_COMMAND_OK 55"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 56"}
echo "GEOM_COMMAND_OK 56"
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
if {!$complete} {error "GPU fence timeout at command 57"}
echo "GEOM_COMMAND_OK 57"
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
if {!$complete} {error "GPU fence timeout at command 58"}
echo "GEOM_COMMAND_OK 58"
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
if {!$complete} {error "GPU fence timeout at command 59"}
echo "GEOM_COMMAND_OK 59"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1750000}
write_memory 0xe9001010 32 {0x1758000}
write_memory 0xe9001010 32 {0x30001}
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
if {!$complete} {error "GPU fence timeout at command 60"}
echo "GEOM_COMMAND_OK 60"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1760000}
write_memory 0xe9001010 32 {0x90002}
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
if {!$complete} {error "GPU fence timeout at command 61"}
echo "GEOM_COMMAND_OK 61"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1768000}
write_memory 0xe9001010 32 {0x176c000}
write_memory 0xe9001010 32 {0x1000001}
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
if {!$complete} {error "GPU fence timeout at command 62"}
echo "GEOM_COMMAND_OK 62"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1770000}
write_memory 0xe9001010 32 {0x1770400}
write_memory 0xe9001010 32 {0x40002}
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
if {!$complete} {error "GPU fence timeout at command 63"}
echo "GEOM_COMMAND_OK 63"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1788000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 64"}
echo "GEOM_COMMAND_OK 64"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x178c000}
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
if {!$complete} {error "GPU fence timeout at command 65"}
echo "GEOM_COMMAND_OK 65"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020101}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 66"}
echo "GEOM_COMMAND_OK 66"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 67"}
echo "GEOM_COMMAND_OK 67"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x84020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 68"}
echo "GEOM_COMMAND_OK 68"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 69"}
echo "GEOM_COMMAND_OK 69"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0x10000}
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
if {!$complete} {error "GPU fence timeout at command 70"}
echo "GEOM_COMMAND_OK 70"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 71"}
echo "GEOM_COMMAND_OK 71"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1000001}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 72"}
echo "GEOM_COMMAND_OK 72"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 73"}
echo "GEOM_COMMAND_OK 73"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 74"}
echo "GEOM_COMMAND_OK 74"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 75"}
echo "GEOM_COMMAND_OK 75"
write_memory 0xe9001010 32 {0x19000001}
write_memory 0xe9001010 32 {0x13}
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
if {!$complete} {error "GPU fence timeout at command 76"}
echo "GEOM_COMMAND_OK 76"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 77"}
echo "GEOM_COMMAND_OK 77"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x10}
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
if {!$complete} {error "GPU fence timeout at command 78"}
echo "GEOM_COMMAND_OK 78"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 79"}
echo "GEOM_COMMAND_OK 79"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
write_memory 0xe9001010 32 {0x101}
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
if {!$complete} {error "GPU fence timeout at command 80"}
echo "GEOM_COMMAND_OK 80"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 81"}
echo "GEOM_COMMAND_OK 81"
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x13}
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
if {!$complete} {error "GPU fence timeout at command 82"}
echo "GEOM_COMMAND_OK 82"
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800001}
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
if {!$complete} {error "GPU fence timeout at command 83"}
echo "GEOM_COMMAND_OK 83"
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
if {!$complete} {error "GPU fence timeout at command 84"}
echo "GEOM_COMMAND_OK 84"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 85"}
echo "GEOM_COMMAND_OK 85"
write_memory 0xe9001010 32 {0x16000001}
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
if {!$complete} {error "GPU fence timeout at command 86"}
echo "GEOM_COMMAND_OK 86"
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
if {!$complete} {error "GPU fence timeout at command 87"}
echo "GEOM_COMMAND_OK 87"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
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
if {!$complete} {error "GPU fence timeout at command 88"}
echo "GEOM_COMMAND_OK 88"
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
if {!$complete} {error "GPU fence timeout at command 89"}
echo "GEOM_COMMAND_OK 89"
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
if {!$complete} {error "GPU fence timeout at command 90"}
echo "GEOM_COMMAND_OK 90"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 91"}
echo "GEOM_COMMAND_OK 91"
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0x4000200}
write_memory 0xe9001010 32 {0x8000800}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 92"}
echo "GEOM_COMMAND_OK 92"
write_memory 0xe9001010 32 {0x17000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
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
if {!$complete} {error "GPU fence timeout at command 93"}
echo "GEOM_COMMAND_OK 93"
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x2000000}
write_memory 0xe9001010 32 {0x1000000}
write_memory 0xe9001010 32 {0x2000100}
write_memory 0xe9001010 32 {0x4000200}
write_memory 0xe9001010 32 {0x0}
set expected_done [expr {($expected_done+1)&0xffff}]
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "GPU fence timeout at command 94"}
echo "GEOM_COMMAND_OK 94"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1790000}
write_memory 0xe9001010 32 {0x1798000}
write_memory 0xe9001010 32 {0x40002}
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
if {!$complete} {error "GPU fence timeout at command 95"}
echo "GEOM_COMMAND_OK 95"
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
if {!$complete} {error "GPU fence timeout at command 96"}
echo "GEOM_COMMAND_OK 96"
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
if {!$complete} {error "GPU fence timeout at command 97"}
echo "GEOM_COMMAND_OK 97"
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
if {!$complete} {error "GPU fence timeout at command 98"}
echo "GEOM_COMMAND_OK 98"
write_memory 0xe9001010 32 {0xe000000}
write_memory 0xe9001010 32 {0x10}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x100}
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
if {!$complete} {error "GPU fence timeout at command 99"}
echo "GEOM_COMMAND_OK 99"
write_memory 0xe9001010 32 {0xf000000}
write_memory 0xe9001010 32 {0xf}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x200020}
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
if {!$complete} {error "GPU fence timeout at command 100"}
echo "GEOM_COMMAND_OK 100"
write_memory 0xe9001010 32 {0x10000000}
write_memory 0xe9001010 32 {0xff380000}
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
if {!$complete} {error "GPU fence timeout at command 101"}
echo "GEOM_COMMAND_OK 101"
write_memory 0xe9001010 32 {0x11000000}
write_memory 0xe9001010 32 {0xff380000}
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
if {!$complete} {error "GPU fence timeout at command 102"}
echo "GEOM_COMMAND_OK 102"
write_memory 0xe9001010 32 {0x13000000}
write_memory 0xe9001010 32 {0xc800c8}
write_memory 0xe9001010 32 {0xdf00c8}
write_memory 0xe9001010 32 {0xc800df}
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
if {!$complete} {error "GPU fence timeout at command 103"}
echo "GEOM_COMMAND_OK 103"
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90003}
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
if {!$complete} {error "GPU fence timeout at command 104"}
echo "GEOM_COMMAND_OK 104"
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "GEOM_COUNTER errors $delta"
if {$delta != 0} {error "Unexpected errors counter"}
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "GEOM_COUNTER lost $delta"
if {$delta != 0} {error "Unexpected lost counter"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_v1_rejected)&0xffffffff}]
echo "GEOM_COUNTER v1_rejected $delta"
if {$delta != 31} {error "Unexpected v1_rejected counter"}
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid_commands)&0xffffffff}]
echo "GEOM_COUNTER invalid_commands $delta"
if {$delta != 21} {error "Unexpected invalid_commands counter"}
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "GEOM_COUNTER vertices $delta"
if {$delta != 402} {error "Unexpected vertices counter"}
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "GEOM_COUNTER triangles $delta"
if {$delta != 61} {error "Unexpected triangles counter"}
set delta [expr {([lindex [read_memory 0xe9001058 32 1] 0]-$before_culled)&0xffffffff}]
echo "GEOM_COUNTER culled $delta"
if {$delta != 12} {error "Unexpected culled counter"}
set delta [expr {([lindex [read_memory 0xe900105c 32 1] 0]-$before_clipped)&0xffffffff}]
echo "GEOM_COUNTER clipped $delta"
if {$delta != 113} {error "Unexpected clipped counter"}
set delta [expr {([lindex [read_memory 0xe9001060 32 1] 0]-$before_slivers)&0xffffffff}]
echo "GEOM_COUNTER slivers $delta"
if {$delta != 2} {error "Unexpected slivers counter"}
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/actual_0.bin} 0x800000 1048576
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/actual_1.bin} 0x900000 1048576
dump_image {/home/michael/console/TESTS/neo_720p_20261012/geometry_board_prepare/actual_2.bin} 0x1700000 1048576
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
