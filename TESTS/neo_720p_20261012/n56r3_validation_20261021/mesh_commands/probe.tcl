init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
echo MESH_PARKED
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}
}
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU"}
if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Missing debug"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}
if {([lindex [read_memory 0xe9005008 32 1] 0]&7) != 0} {error "Partial command"}
set want {4294901760 4294901760 131072 0 0 0 0 0 65536 4294901760 131072 0 0 0 0 0 0 65536 131072 0 0 0 0 0 4294901760 4294901760 6554 0 0 0 0 0 65536 4294901760 196608 0 0 0 0 0 0 65536 196608 0 0 0 0 0 4294377472 4294836224 131072 0 0 0 0 0 524288 4294836224 131072 0 0 0 0 0 0 458752 131072 0 0 0 0 0}
set got [read_memory 0x1740000 32 72]
foreach x $got y $want {if {$x != $y} {error "Mesh data changed since prior diagnostic"}}
set want {66048 0 1048607 2031616 0 32769 42045696 0}
set got [read_memory 0x1748000 32 8]
foreach x $got y $want {if {$x != $y} {error "Mesh data changed since prior diagnostic"}}
echo MESH_MEMORY_VERIFIED
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x1600180}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 0"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 0 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 0 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 0 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 0 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 0 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 0 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 0 triangles $delta"
echo "MESH_HEADERS 0 [read_memory 0xe9005018 32 2]"
echo "MESH_META 0 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x17000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 1"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 1 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 1 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 1 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 1 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 1 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 1 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 1 triangles $delta"
echo "MESH_HEADERS 1 [read_memory 0xe9005018 32 2]"
echo "MESH_META 1 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1c000000}
write_memory 0xe9001010 32 {0x3}
write_memory 0xe9001010 32 {0x1084}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 2"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 2 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 2 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 2 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 2 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 2 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 2 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 2 triangles $delta"
echo "MESH_HEADERS 2 [read_memory 0xe9005018 32 2]"
echo "MESH_META 2 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x18000000}
write_memory 0xe9001010 32 {0x1700000}
write_memory 0xe9001010 32 {0x200020}
write_memory 0xe9001010 32 {0x40}
write_memory 0xe9001010 32 {0xa}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 3"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 3 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 3 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 3 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 3 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 3 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 3 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 3 triangles $delta"
echo "MESH_HEADERS 3 [read_memory 0xe9005018 32 2]"
echo "MESH_META 3 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x4000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500000}
write_memory 0xe9001010 32 {0x500032}
write_memory 0xe9001010 32 {0xa00064}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 4"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 4 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 4 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 4 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 4 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 4 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 4 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 4 triangles $delta"
echo "MESH_HEADERS 4 [read_memory 0xe9005018 32 2]"
echo "MESH_META 4 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 5"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 5 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 5 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 5 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 5 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 5 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 5 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 5 triangles $delta"
echo "MESH_HEADERS 5 [read_memory 0xe9005018 32 2]"
echo "MESH_META 5 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 6"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 6 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 6 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 6 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 6 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 6 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 6 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 6 triangles $delta"
echo "MESH_HEADERS 6 [read_memory 0xe9005018 32 2]"
echo "MESH_META 6 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x2}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 7"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 7 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 7 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 7 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 7 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 7 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 7 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 7 triangles $delta"
echo "MESH_HEADERS 7 [read_memory 0xe9005018 32 2]"
echo "MESH_META 7 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x21000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x8001}
write_memory 0xe9001010 32 {0xc00040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 8"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 8 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 8 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 8 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 8 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 8 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 8 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 8 triangles $delta"
echo "MESH_HEADERS 8 [read_memory 0xe9005018 32 2]"
echo "MESH_META 8 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x17}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 9"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 9 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 9 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 9 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 9 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 9 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 9 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 9 triangles $delta"
echo "MESH_HEADERS 9 [read_memory 0xe9005018 32 2]"
echo "MESH_META 9 [read_memory 0xe9005040 32 1]"
set before_errors [lindex [read_memory 0xe900100c 32 1] 0]
set before_lost [lindex [read_memory 0xe900101c 32 1] 0]
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_pixels [lindex [read_memory 0xe900103c 32 1] 0]
set before_invalid [lindex [read_memory 0xe900104c 32 1] 0]
set before_vertices [lindex [read_memory 0xe9001050 32 1] 0]
set before_triangles [lindex [read_memory 0xe9001054 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x22000000}
write_memory 0xe9001010 32 {0x1740000}
write_memory 0xe9001010 32 {0x1748000}
write_memory 0xe9001010 32 {0x90001}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set poll 0} {$poll < 100} {incr poll} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 5
}
if {!$complete} {error "Fence timeout 10"}
sleep 2
set delta [expr {([lindex [read_memory 0xe900100c 32 1] 0]-$before_errors)&0xffffffff}]
echo "MESH_COUNTER 10 errors $delta"
set delta [expr {([lindex [read_memory 0xe900101c 32 1] 0]-$before_lost)&0xffffffff}]
echo "MESH_COUNTER 10 lost $delta"
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
echo "MESH_COUNTER 10 rejected $delta"
set delta [expr {([lindex [read_memory 0xe900103c 32 1] 0]-$before_pixels)&0xffffffff}]
echo "MESH_COUNTER 10 pixels $delta"
set delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_invalid)&0xffffffff}]
echo "MESH_COUNTER 10 invalid $delta"
set delta [expr {([lindex [read_memory 0xe9001050 32 1] 0]-$before_vertices)&0xffffffff}]
echo "MESH_COUNTER 10 vertices $delta"
set delta [expr {([lindex [read_memory 0xe9001054 32 1] 0]-$before_triangles)&0xffffffff}]
echo "MESH_COUNTER 10 triangles $delta"
echo "MESH_HEADERS 10 [read_memory 0xe9005018 32 2]"
echo "MESH_META 10 [read_memory 0xe9005040 32 1]"
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}
echo MESH_TRACE_COMPLETE
shutdown
