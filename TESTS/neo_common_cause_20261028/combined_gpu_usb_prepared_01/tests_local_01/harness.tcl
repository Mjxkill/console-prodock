
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

set gpuwords 0
set gpudone 0
array set snap {0xe9005000 0 0xe9006000 0}
set frames 1
rename sleep parent_sleep
proc sleep {n} {if {$n ni {1 2 100 200 1000}} {error "unbounded wait"}}
rename read_memory parent_read
rename write_memory parent_write
rename word parent_word
proc word {a} {
 global fault gpuwords gpudone
 if {$a in {0xe9000014 0xe9000034 0xe9000044}} {return 0}
 if {$a==0xe9001008} {return $gpudone}
 if {$a==0xe900100c} {return 0}
 return [parent_word $a]
}
proc write_memory {a bits values} {
 global snap gpuwords gpudone fault
 if {$bits!=32} {error "bad write width"}
 if {$a==0xe900200c} {return [parent_write $a $bits $values]}
 if {$a in {0xe9005004 0xe9006004}} {
  if {$values ne "1"} {error "forbidden snapshot"}
  set base [format 0x%x [expr {$a-4}]];incr snap($base);return
 }
 if {$a==0xe9001010} {
  if {$gpuwords>=8 || $values!=[lindex {0x1f000000 0 65536 0 0 0 0 0} $gpuwords]} {error "forbidden GPU command"}
  incr gpuwords
  if {$gpuwords==8 && $fault ne "gpu_timeout"} {incr gpudone}
  return
 }
 error "forbidden write $a"
}
proc read_memory {a bits count} {
 global snap gpuwords gpudone frames fault
 if {$bits!=32} {error "bad read width"}
 if {$a==0xe9000000 && $count==30} {
  set v [lrepeat 30 0];lset v 0 0x47505531;lset v 6 $frames;lset v 24 0x1ff8f800;lset v 28 0x02d00500
  if {$fault ne "video_stopped"} {incr frames};return $v
 }
 if {$a==0xe9001000 && $count==26} {set v [lrepeat 26 0];lset v 0 0x424c5432;lset v 2 $gpudone;return $v}
 foreach base {0xe9005000 0xe9006000} {
  if {$a==$base && $count==17} {
   set v [lrepeat 17 0];lset v 0 0x4e474442;lset v 1 6;lset v 2 $gpuwords;lset v 3 $snap($base);lset v 4 $gpuwords;lset v 8 $gpudone;lset v 9 0x00fff000;return $v
  }
  if {$count==1 && $a>=$base && $a<=$base+16} {
   switch [expr {$a-$base}] {
    0 {return 0x4e474442}
    4 {return [expr {$fault eq "source_stopped"?0:($snap($base)>0 && $fault ne "snapshot_timeout"?6:4)}]}
    8 {return $gpuwords}
    12 {return $snap($base)}
    16 {return [expr {$fault eq "gpu_lost" && $gpuwords?7:$gpuwords}]}
   }
  }
 }
 if {$count==1 && $a in {0xe9000014 0xe9000034 0xe9000044 0xe9001008 0xe900100c}} {return [word $a]}
 return [parent_read $a $bits $count]
}
source [lindex $argv 1]
echo {COMBINED_HOST {"devices":[],"usb_io_attempted":false,"hs_present":false,"diag_status":"NO_DEVICE"}}
source [lindex $argv 2]
if {$writes!=4} {error "wrong observer write count"}
if {$fault ni {source_stopped snapshot_timeout} && $gpuwords!=8} {error "not eight GPU words"}
