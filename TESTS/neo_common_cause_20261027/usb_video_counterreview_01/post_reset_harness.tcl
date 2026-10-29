
set fault [lindex $argv 0]
set now 0
set seq 0
set armed 0
set ticks 0
set bank [lrepeat 32 0]
set bank_reads 0
set writes {}
set lag 0
proc echo {text} {puts $text}
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc get_reg {args} {return [dict create pc 0x80000004 priv 3 satp 0]}
rename clock original_clock
proc clock {what} {global now;return $now}
proc sleep {ms} {global now ticks armed;incr now $ms;if {$armed} {set ticks [expr {($ticks+$ms*60000)&0xffffffff}]}}
proc write_memory {address bits words} {
 global fault seq armed ticks bank bank_reads writes lag
 if {$address!=0xe900200c || $bits!=32 || [llength $words]!=1} {error "Unexpected mock write"}
 set command [lindex $words 0]
 lappend writes $command
 set bank [lrepeat 32 0]
 lset bank 0 0x55544e41
 lset bank 1 1
 lset bank 2 $command
 lset bank 3 $ticks
 lset bank 31 [expr {$armed ? 0x400 : 0}]
 if {$command==1} {set armed 1;set ticks 0}
 if {$command==6} {
  set ticks [expr {($ticks+1)&0xffffffff}]
  set armed 0
  if {$fault eq "lost_disarm_tick"} {incr ticks -1}
 }
 if {$command==2 && $fault eq "keeps_ticking"} {incr ticks}
 if {$fault eq "header"} {lset bank 2 99}
 if {$fault eq "no_ticks" && $command==6} {lset bank 3 0}
 if {$fault eq "armed_stuck" && $command==2} {lset bank 31 0x400}
 set seq [expr {($seq+1)&0xffffffff}]
 if {$fault eq "sequence"} {incr seq}
 set bank_reads 0
 set lag [expr {$fault eq "delayed_ack" ? 3 : 0}]
}
proc read_memory {address bits count} {
 global fault seq armed ticks bank bank_reads writes lag
 if {$bits!=32} {error "Unexpected width"}
 if {$fault eq "post_reset" && [llength $writes]==4 && $address==0xe9000000 && $count==30} {set seq 0}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9000000 && $count==1} {return {0x47505531}}
 if {$address==0xe9000070 && $count==1} {return {0x02d00500}}
 if {$address==0xe9002000 && $count==3} {
  if {$fault eq "identity"} {return {0 0 0}}
  if {[llength $writes]>0 && $fault eq "rejected"} {return [list 0x55544e41 2 $seq]}
  if {[llength $writes]>0 && $fault eq "busy"} {return [list 0x55544e41 1 [expr {$seq-1}]]}
  if {$lag>0} {incr lag -1;return [list 0x55544e41 1 [expr {$seq-1}]]}
  return [list 0x55544e41 0 $seq]
 }
 if {$address==0xe9002040 && $count==32} {
  incr bank_reads
  if {$fault eq "unstable" && $bank_reads==2} {lset bank 29 1}
  if {$fault eq "short_bank"} {return [lrange $bank 0 30]}
  return $bank
 }
 if {$address in {0xe9000000 0xe9001000 0xe9005000 0xe9006000}} {return [lrepeat $count 0]}
 error "Unexpected mock read $address $count"
}
source [lindex $argv 1]
if {$writes ne {1 6 2 2}} {error "Unexpected command sequence $writes"}
puts MOCK_PROTOCOL_PASS
