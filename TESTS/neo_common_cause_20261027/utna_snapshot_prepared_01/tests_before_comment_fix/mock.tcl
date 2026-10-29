
set fault [lindex $argv 0]
set writes 0
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc sleep {n} {}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {address width words} {
 global writes
 if {$address!=0xe900200c || $width!=32 || $words ne "2" || $writes!=0} {error "Unexpected write"}
 incr writes
}
proc read_memory {address bits count} {
 global fault writes
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$address==0xe9002040 && $count>1} {
   set result [lrepeat $count 0]
   lset result 0 0x55544e41;lset result 1 1;lset result 2 2
   if {$fault eq "bulk_alias" || $fault eq "all_alias"} {lset result 1 0;lset result 2 1}
   if {$fault eq "bulk3" && $count==3} {lset result 2 3}
   if {$fault eq "short"} {set result [lrange $result 0 end-1]}
   return $result
 }
 if {$count!=1} {error "Unexpected bulk read"}
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$writes&&$fault eq "reject"?2:($fault eq "busy"?1:0)}]}
  e9002008 {return [expr {$writes?($fault eq "timeout"?0:($fault eq "sequence"?2:1)):0}]}
  e9002040 {return [expr {$writes?0x55544e41:0}]}
  e9002044 {return [expr {$writes?($fault eq "individual"||$fault eq "all_alias"?0:1):0}]}
  e9002048 {return [expr {$writes?($fault eq "all_alias"?1:2):0}]}
  default {error "Unexpected address $address"}
 }
}
source [lindex $argv 1]
if {$writes!=1} {error "Expected exactly one write"}
