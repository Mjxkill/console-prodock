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
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU is not idle"}
set sent [lindex [read_memory 0xe9005008 32 1] 0]
if {($sent & 7) != 0 || $sent != [lindex [read_memory 0xe9005010 32 1] 0]} {error "Pending/partial command"}
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}
}
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET matrix_row0 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET matrix_row1 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET matrix_row2 $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1f000000}
write_memory 0xe9001010 32 {0x3}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET matrix_invalid_row $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x21000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET light $delta $geometry_delta"
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
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET invalidate $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x100}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET material $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x19000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x101}
write_memory 0xe9001010 32 {0xffff}
write_memory 0xe9001010 32 {0x4020100}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET material_invalid_alpha $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x18000000}
write_memory 0xe9001010 32 {0x1700000}
write_memory 0xe9001010 32 {0x10001}
write_memory 0xe9001010 32 {0x20}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET texture $delta $geometry_delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x1a000000}
write_memory 0xe9001010 32 {0x10000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
set complete 0
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET plane $delta $geometry_delta"
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
for {set i 0} {$i < 50} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "TARGET fence timeout"}
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "GPU_TARGET invalidate_again $delta $geometry_delta"
snapshot after
echo GPU_SNAPSHOT_COMPLETE
shutdown
