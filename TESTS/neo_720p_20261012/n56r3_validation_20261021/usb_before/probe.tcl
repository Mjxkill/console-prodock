init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
echo USB_PARKED
foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}
}
if {[lindex [read_memory 0xe9003000 32 1] 0] != 0x554d5343} {error "USB MSC identity differs"}
for {set i 0} {$i < 3} {incr i} {
  echo "USB_STATUS $i [read_memory 0xe9003004 32 1]"
  sleep 50
}
set trace_id [lindex [read_memory 0xe9002000 32 1] 0]
echo "USB_TRACE_ID $trace_id"
if {$trace_id == 0x55544e41} {
  if {([lindex [read_memory 0xe9002004 32 1] 0] & 1) != 0} {error "Trace busy at entry"}
  foreach cmd {1 2 4} {
    set expected [expr {([lindex [read_memory 0xe9002008 32 1] 0]+1)&0xffffffff}]
    write_memory 0xe900200c 32 [list $cmd]
    set done 0
    for {set poll 0} {$poll < 100} {incr poll} {
      sleep 2
      if {[lindex [read_memory 0xe9002004 32 1] 0] == 0 && [lindex [read_memory 0xe9002008 32 1] 0] == $expected} {set done 1; break}
    }
    echo "USB_TRACE_ACK $cmd $done"
    if {!$done} {break}
    echo "USB_TRACE_BANK $cmd [read_memory 0xe9002040 32 32]"
    if {$cmd == 1} {sleep 200}
  }
}
echo USB_PROBE_COMPLETE
shutdown
