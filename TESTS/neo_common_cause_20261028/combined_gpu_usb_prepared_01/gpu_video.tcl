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
