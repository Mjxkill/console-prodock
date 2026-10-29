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

echo "NCP_RAW_BEFORE_ASSERT [read_memory 0xe9005080 32 7]"
foreach {addr expected} {
  0xe9005080 0x4e435031 0xe9005088 0 0xe900508c 0
  0xe9001004 0 0xe9001008 0 0xe9001034 0
} {
  if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "Unexpected idle GPU/NCP counters"}
}
echo "NCP_COUNTERS [read_memory 0xe9005088 32 2]"
echo "WARM_CHECK_0"
# Non-destructive sampling and one register-only geometry command; no DMA command.
proc cv_video {label} {
 echo "COMBINED_TIME $label [clock milliseconds]"
 echo "COMBINED_SCAN $label [read_memory 0xe9000000 32 30]"
 echo "COMBINED_GPU $label [read_memory 0xe9001000 32 26]"
 echo "COMBINED_NCP $label [read_memory 0xe9005080 32 7]"
}
proc cv_snapshot {base label} {
 if {$base!=0xe9005000 && $base!=0xe9006000} {error "Forbidden snapshot base"}
 set id [lindex [read_memory $base 32 1] 0]
 set status [lindex [read_memory [expr {$base+4}] 32 1] 0]
 if {$id!=0x4e474442 || ($status&5)!=4} {
  echo "COMBINED_GPU_FAIL $label source_not_ready $id $status"
  return 0
 }
 set n [expr {([lindex [read_memory [expr {$base+12}] 32 1] 0]+1)&0xffffffff}]
 if {$base==0xe9005000} {write_memory 0xe9005004 32 {1}} else {write_memory 0xe9006004 32 {1}}
 set complete 0
 for {set i 0} {$i<50} {incr i} {
  set s [lindex [read_memory [expr {$base+4}] 32 1] 0]
  set seq [lindex [read_memory [expr {$base+12}] 32 1] 0]
  if {$s==6 && $seq==$n} {set complete 1;break}
  sleep 1
 }
 if {!$complete} {echo "COMBINED_GPU_FAIL $label snapshot_timeout $s $seq";return 0}
 echo "COMBINED_SNAPSHOT $label [read_memory $base 32 17]"
 return 1
}
proc cv_matrix {} {
 set idle [lindex [read_memory 0xe9001004 32 1] 0]
 set sent [lindex [read_memory 0xe9005008 32 1] 0]
 set received [lindex [read_memory 0xe9005010 32 1] 0]
 if {$idle!=0 || ($sent&7)!=0 || $sent!=$received} {echo "COMBINED_GPU_FAIL MATRIX not_idle $idle $sent $received";return}
 foreach a {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {
  if {[lindex [read_memory $a 32 1] 0]!=0} {error "Scanout DMA must be disabled"}
 }
 set done [expr {[lindex [read_memory 0xe9001008 32 1] 0]&0xffff}]
 set errors [read_memory 0xe900100c 32 1]
 set rejected [read_memory 0xe9001034 32 1]
 echo "COMBINED_MATRIX_BEFORE $sent $received $done $errors $rejected"
 foreach word {0x1f000000 0 65536 0 0 0 0 0} {write_memory 0xe9001010 32 [list $word]}
 set complete 0
 for {set i 0} {$i<50} {incr i} {
  set after [expr {[lindex [read_memory 0xe9001008 32 1] 0]&0xffff}]
  if {$after==(($done+1)&0xffff)} {set complete 1;break}
  sleep 1
 }
 set sent_after [lindex [read_memory 0xe9005008 32 1] 0]
 set received_after [lindex [read_memory 0xe9005010 32 1] 0]
 set errors_after [read_memory 0xe900100c 32 1]
 set rejected_after [read_memory 0xe9001034 32 1]
 echo "COMBINED_MATRIX_AFTER $sent_after $received_after $after $errors_after $rejected_after"
 if {!$complete || $sent_after!=(($sent+8)&0xffffffff) || $received_after!=(($received+8)&0xffffffff) || $errors_after ne $errors || $rejected_after ne $rejected} {echo "COMBINED_GPU_FAIL MATRIX counters_or_completion"}
}
foreach label {T0 T100 T200 T1200} {
 if {$label eq "T100" || $label eq "T200"} {sleep 100}
 if {$label eq "T1200"} {sleep 1000}
 cv_video $label
}
# Only four UTNA observer commands. No CPU resume, DDR/GPU/SD write.
proc utw_single {address} {
 set row [read_memory $address 32 1]
 if {[llength $row]!=1} {error "Bad single read length"}
 set v [lindex $row 0]
 if {$v<0 || $v>0xffffffff} {error "Bad single word"}
 return $v
}
proc utw_status {} {return [list [utw_single 0xe9002000] [utw_single 0xe9002004] [utw_single 0xe9002008]]}
proc utw_idle {label n} {
 set s [utw_status]
 echo "UTW1_CONTROL $label $s"
 if {[lindex $s 0]!=0x55544e41 || [lindex $s 1]!=0 || [lindex $s 2]!=$n} {error "Observer is not idle at expected sequence"}
}
proc utw_read {label phase start count} {
 set values [read_memory $start 32 $count]
 if {[llength $values]!=$count} {error "Partial read"}
 for {set i 0} {$i<$count} {incr i} {
  set v [lindex $values $i]
  if {$v<0 || $v>0xffffffff} {error "Bad image word"}
  set a [expr {$start+4*$i}]
  echo [format {UTW1_READ %s {"phase":"%s","address":"0x%08x","value":"0x%08x"}} $label $phase $a $v]
 }
}
proc utw_capture {label command n} {
 set allowed {ARM {1 1} DISARM {6 2} STOPPED {2 3} STABLE {2 4}}
 if {![dict exists $allowed $label] || [dict get $allowed $label] ne [list $command $n]} {error "Forbidden command"}
 utw_idle "${label}_PRE" [expr {$n-1}]
 echo "UTW1_WRITE $label $command $n"
 write_memory 0xe900200c 32 [list $command]
 set deadline [expr {[clock milliseconds]+2000}]
 set ack 0
 for {set poll 0} {$poll<100} {incr poll} {
  set s [utw_status];set flags [lindex $s 1];set seq [lindex $s 2]
  if {[lindex $s 0]!=0x55544e41 || ($flags&2) || ($flags&~3)} {error "Invalid/rejected observer state"}
  if {$seq!=$n && $seq!=$n-1} {error "Unexpected sequence while waiting"}
  if {$flags==0 && $seq==$n} {set ack 1;break}
  if {[clock milliseconds]>=$deadline} {break}
  sleep 2
 }
 if {!$ack} {error "Observer acknowledgement timeout"}
 utw_idle "${label}_ACK" $n
 utw_read $label before 0xe9002000 3
 foreach phase {image_a image_b} {
  utw_read $label $phase 0xe9002040 32
  utw_read $label $phase 0xe90020c0 16
 }
 utw_read $label after 0xe9002000 3
 echo "UTW1_CAPTURE_COMPLETE $label"
}
utw_idle INITIAL 0
set initial [read_memory 0xe90020c0 32 16]
echo "UTW1_INITIAL_EXT $initial"
if {[llength $initial]!=16 || [lindex $initial 0]!=0x55545731 || [lindex $initial 1]!=0x10001} {error "Missing fresh UTW1 identity/ABI"}
foreach value [lrange $initial 2 end] {if {$value!=0} {error "Witness is not fresh after programming"}}
utw_capture ARM 1 1
set g [cv_snapshot 0xe9005000 GPU_BEFORE]
set s [cv_snapshot 0xe9006000 SCAN_BEFORE]
if {$g && $s} {cv_matrix} else {echo "COMBINED_GPU_FAIL MATRIX skipped_snapshot_failure"}
cv_snapshot 0xe9005000 GPU_AFTER_MATRIX
cv_video AFTER_MATRIX
echo COMBINED_BEGIN_DONE
