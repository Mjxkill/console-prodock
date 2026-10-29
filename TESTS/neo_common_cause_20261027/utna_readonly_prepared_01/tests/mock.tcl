
set fault [lindex $argv 0]
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc shutdown {} {}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {args} {error "FORBIDDEN WRITE"}
proc read_memory {address bits count} {
 global fault
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$count!=1} {error "Unexpected bulk read"}
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$fault eq "busy"?1:0}]}
  e9002008 {return [expr {$fault eq "sequence"?1:0}]}
  e9002040 {return [expr {$fault eq "alias"?0x55544e41:0}]}
  e9002044 {if {$fault eq "short"} {return {}};return 0}
  e9002048 - e9002080 - e9002084 {return 0}
  default {error "Unexpected address $address"}
 }
}
source [lindex $argv 1]
