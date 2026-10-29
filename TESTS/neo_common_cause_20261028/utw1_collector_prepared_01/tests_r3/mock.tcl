
set fault [lindex $argv 0]
set writes 0
set command 0
set bankreads 0
set extreads 0
set controls 0
proc init {} {}
proc halt {} {}
proc riscv {args} {}
proc echo {message} {puts $message}
proc sleep {n} {if {$n ni {2 100 200}} {error "unbounded sleep"}}
proc get_reg {args} {
 global fault
 return [dict create pc [expr {$fault eq "cpu"?0x80010000:0x80000004}] priv 3 satp 0]
}
proc write_memory {address width words} {
 global writes command bankreads extreads controls fault
 if {$address!=0xe900200c || $width!=32 || $words ne [lindex {1 6 2 2} $writes] || $writes>3} {error "Unexpected write"}
 incr writes;set command $words;set bankreads 0;set extreads 0;set controls 0
}
proc word {address} {
 global fault writes
 switch -- [format %x $address] {
  e9000000 {return 0x47505531}
  e9000070 {return 0x02d00500}
  e9000008 - e900000c - e9005088 - e900508c - e9001004 - e9001034 {return 0}
  e9001008 {return [expr {$fault eq "gpu"?1:0}]}
  e9000060 {return 0x1ff8f800}
  e9005080 {return 0x4e435031}
  e9002000 {return [expr {$fault eq "id"?0:0x55544e41}]}
  e9002004 {return [expr {$writes&&$fault eq "reject"?2:($fault eq "busy"?1:($writes&&$fault eq "flags"?4:0))}]}
  e9002008 {return [expr {$writes?($fault eq "timeout"?0:($fault eq "sequence"?7:$writes)):0}]}
  default {error "Unexpected address $address"}
 }
}
proc read_memory {address bits count} {
 global fault writes command bankreads extreads controls
 if {$bits!=32} {error "bad width"}
 if {$address==0x80000000 && $count==2} {return {0x10500073 0xffdff06f}}
 if {$address==0xe9005080 && $count==7} {return {0x4e435031 4 0 0 0 0 0}}
 if {$address==0xe9005088 && $count==2} {return {0 0}}
 if {$address==0xe9002000 && $count==3} {
  incr controls;set values [list [word $address] [word [expr {$address+4}]] [word [expr {$address+8}]]]
  if {$fault eq "changed_control" && $controls==2} {lset values 2 77}
  return $values
 }
 if {$address==0xe9002040 && $count==32} {
   incr bankreads
   set result [lrepeat 32 0]
   lset result 0 0x55544e41;lset result 1 1;lset result 2 $command
   lset result 3 [lindex {0 0 123 124 124} $writes]
   if {$writes==2} {lset result 31 0x400}
   if {$fault in {version0 raw0}} {lset result 1 0}
   if {$fault eq "version3"} {lset result 1 3}
   if {$fault eq "bank_id"} {lset result 0 0}
   if {$fault eq "command"} {lset result 2 7}
   if {$fault eq "ticks"} {lset result 3 0}
   if {$fault eq "armed"} {lset result 31 0}
   if {$fault eq "last_tick" && $writes>=3} {lset result 3 123}
   if {$fault eq "unstable" && $bankreads==2} {lset result 9 1}
   if {$fault eq "short"} {set result [lrange $result 0 end-1]}
   if {$fault eq "out_of_u32"} {lset result 9 0x100000000}
   return $result
 }
 if {$address==0xe90020c0 && $count==16} {
   set result [concat {0x55545731 0x10001} [lrepeat 14 0]]
   if {$fault eq "abi"} {lset result 1 3}
   if {$writes==0} {
    if {$fault eq "initial_dirty"} {lset result 4 1}
    return $result
   }
   incr extreads
   set raw [expr {$fault in {raw0 contradiction}?0:1}]
   lset result 2 0x55544e41;lset result 3 $raw;lset result 4 $command;lset result 5 $raw
   foreach i {6 7 8 10} {lset result $i $writes}
   lset result 9 [expr {32*$writes}]
   lset result 12 0x003f0007
   foreach i {13 14 15} {lset result $i [expr {$writes-1}]}
   if {$fault eq "alias"} {lset result 5 3}
   if {$fault eq "ec"} {lset result 11 1}
   if {$fault eq "tag"} {lset result 14 $writes}
   if {$fault eq "total"} {lset result 9 [expr {31*$writes}]}
   if {$fault eq "status"} {lset result 12 0x00370007}
   if {$fault eq "frame"} {lset result 7 0}
   if {$fault eq "rawid"} {lset result 2 0}
   if {$fault eq "rawcommand"} {lset result 4 0}
   if {$fault eq "unstable_ext" && $extreads==2} {lset result 15 99}
   if {$fault eq "short_ext"} {set result [lrange $result 0 end-1]}
   return $result
 }
 if {$count!=1} {error "Unexpected bulk read"}
 return [word $address]
}
source [lindex $argv 1]
if {$writes!=4} {error "Expected exactly four writes"}
