riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}
}
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU port"}
if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Debug instrument absent"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}
set old_font [lindex [read_memory 0xe9001014 32 1] 0]
write_memory 0xe9001014 32 {0x321}
set font_test [lindex [read_memory 0xe9001014 32 1] 0]
write_memory 0xe9001014 32 [list $old_font]
if {$font_test != 0x321 || [lindex [read_memory 0xe9001014 32 1] 0] != $old_font} {error "MMIO font address witness differs"}
load_image {/home/michael/console/TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/observer_n56r1_aba_b2/pattern.bin} 0x12000000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/observer_n56r1_aba_b2/memory_before.bin} 0x12000000 4096
verify_image {/home/michael/console/TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/observer_n56r1_aba_b2/pattern.bin} 0x12000000 bin
proc raw_observation {label} {
    if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "Raw observation needs idle GPU"}
    for {set i 0} {$i < 3} {incr i} {
        sleep 2
        echo "OBSERVER_RAW $label $i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
    }
}
proc snapshot_observation {label} {
    set status [lindex [read_memory 0xe9005004 32 1] 0]
    echo "OBSERVER_HANDSHAKE $label before $status [read_memory 0xe900500c 32 1] [read_memory 0xe9005040 32 1]"
    if {($status & 5) == 4} {write_memory 0xe9005004 32 {1}}
    for {set i 0} {$i < 30} {incr i} {
        sleep 1
        set status [lindex [read_memory 0xe9005004 32 1] 0]
        echo "OBSERVER_HANDSHAKE $label poll$i $status [read_memory 0xe900500c 32 1] [read_memory 0xe9005040 32 1]"
        if {($status & 3) == 2} {break}
    }
    raw_observation $label
}
echo "OBSERVER_GPU before [read_memory 0xe9001000 32 26]"
set initial_errors [lindex [read_memory 0xe900100c 32 1] 0]
set initial_lost [lindex [read_memory 0xe900101c 32 1] 0]
set initial_host [lindex [read_memory 0xe9005008 32 1] 0]
if {($initial_host & 7) != 0} {error "Partial host command"}
raw_observation before
snapshot_observation snapshot_before
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
echo "OBSERVER_CONFIG legacy_affine_before $delta $geometry_delta"
raw_observation legacy_affine_before
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG preflight $delta $geometry_delta"
raw_observation preflight
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG zero_width $delta $geometry_delta"
raw_observation zero_width
set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]
set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG preflight_again $delta $geometry_delta"
raw_observation preflight_again
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG matrix_row0 $delta $geometry_delta"
raw_observation matrix_row0
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG matrix_invalid_row $delta $geometry_delta"
raw_observation matrix_invalid_row
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG light $delta $geometry_delta"
raw_observation light
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG material $delta $geometry_delta"
raw_observation material
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG texture $delta $geometry_delta"
raw_observation texture
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
for {set i 0} {$i < 100} {incr i} {
  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}
  sleep 1
}
if {!$complete} {error "Configuration fence timeout"}
sleep 2
set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]
set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]
echo "OBSERVER_CONFIG plane $delta $geometry_delta"
raw_observation plane
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
echo "OBSERVER_CONFIG invalidate $delta $geometry_delta"
raw_observation invalidate
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
echo "OBSERVER_CONFIG legacy_affine_after $delta $geometry_delta"
raw_observation legacy_affine_after
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
echo "OBSERVER_CONFIG invalidate_repeat $delta $geometry_delta"
raw_observation invalidate_repeat
snapshot_observation snapshot_after1
snapshot_observation snapshot_after2
echo "OBSERVER_GPU after [read_memory 0xe9001000 32 26]"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/observer_n56r1_aba_b2/memory_after.bin} 0x12000000 4096
verify_image {/home/michael/console/TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/observer_n56r1_aba_b2/pattern.bin} 0x12000000 bin
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}
if {[lindex [read_memory 0xe900100c 32 1] 0] != $initial_errors || [lindex [read_memory 0xe900101c 32 1] 0] != $initial_lost} {error "Transport error counters changed"}
if {(([lindex [read_memory 0xe9005008 32 1] 0]-$initial_host)&0xffffffff) != 104} {error "Host word delta differs"}
echo "OBSERVER_COMPLETE [reg pc]"
shutdown
