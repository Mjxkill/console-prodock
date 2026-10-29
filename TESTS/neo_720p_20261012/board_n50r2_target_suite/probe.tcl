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
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12001000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET preflight $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0x4000200}
write_memory 0xe9001010 32 {0x8000800}
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
echo "GPU_TARGET maximum $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET small $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x10}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET zero_width $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x80000}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET zero_height $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x1}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET unaligned_color $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x3}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET unaligned_depth $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET overlap $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x200010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET short_stride $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x3fffffe0}
write_memory 0xe9001010 32 {0x1000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET overflow $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x100000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_00000000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x100000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_00000000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x100000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_00000000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_00800000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_00800000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x800000}
write_memory 0xe9001010 32 {0x900000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_00800000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x10000000}
write_memory 0xe9001010 32 {0x10100000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_10000000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x10000000}
write_memory 0xe9001010 32 {0x10100000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_10000000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x10000000}
write_memory 0xe9001010 32 {0x10100000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_10000000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12100000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_12000000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12100000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_12000000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12100000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_12000000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x20100000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_20000000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x20100000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_20000000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x20000000}
write_memory 0xe9001010 32 {0x20100000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_20000000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x30000000}
write_memory 0xe9001010 32 {0x30100000}
write_memory 0xe9001010 32 {0x80010}
write_memory 0xe9001010 32 {0x200020}
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
echo "GPU_TARGET base_30000000_8x16 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x30000000}
write_memory 0xe9001010 32 {0x30100000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET base_30000000_32x64 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x30000000}
write_memory 0xe9001010 32 {0x30100000}
write_memory 0xe9001010 32 {0x19000f0}
write_memory 0xe9001010 32 {0x3200320}
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
echo "GPU_TARGET base_30000000_400x240 $delta"
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12001000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
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
echo "GPU_TARGET preflight_again $delta"
snapshot after
echo GPU_SNAPSHOT_COMPLETE
shutdown
