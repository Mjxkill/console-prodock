init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}
}
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU port"}
if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Debug instrument absent"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}
echo "GPU_RAW before [read_memory 0xe9005000 32 16]"
set initial_errors [lindex [read_memory 0xe900100c 32 1] 0]
set initial_lost [lindex [read_memory 0xe900101c 32 1] 0]
set initial_host [lindex [read_memory 0xe9005008 32 1] 0]
if {($initial_host & 7) != 0} {error "Partial host command"}
set status [lindex [read_memory 0xe9005004 32 1] 0]
if {($status & 5) == 4} {write_memory 0xe9005004 32 {1}}
sleep 10
echo "GPU_RAW requested [read_memory 0xe9005000 32 16]"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0xc000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG legacy_affine_0 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1e000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG v1_invalidate_0 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0xc000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG legacy_affine_1 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1e000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG v1_invalidate_1 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0xc000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG legacy_affine_2 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1e000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_CONFIG v1_invalidate_2 $delta $geometry_delta"
echo "GPU_RAW after [read_memory 0xe9005000 32 16]"
echo "GPU_STATUS after [read_memory 0xe9001000 32 26]"
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}
if {[lindex [read_memory 0xe900100c 32 1] 0] != $initial_errors || [lindex [read_memory 0xe900101c 32 1] 0] != $initial_lost} {error "Transport error counters changed"}
if {(([lindex [read_memory 0xe9005008 32 1] 0]-$initial_host)&0xffffffff) != 48} {error "Host word delta differs"}
echo "GPU_CONFIG_COMPLETE [reg pc]"
shutdown
