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
sleep 200
utw_capture DISARM 6 2
sleep 100
utw_capture STOPPED 2 3
sleep 100
utw_capture STABLE 2 4
echo UTW1_READS_DONE
