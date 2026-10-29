
set oldjournal {1296314674 1 8 4294967291 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 32 32}
set clearedjournal {0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0}
set pcs {0x80000000 0x80000004 0x80000004}
set pcindex 0
proc read_memory {address bits count} {
    global oldjournal clearedjournal
    puts "READ $address $bits $count"
    if {$address == 0xa0006000} {return $oldjournal}
    if {$address == 0xa0006400} {return $clearedjournal}
    error "Forbidden memory read $address"
}
proc reg {name} {global pcs pcindex; set v [lindex $pcs $pcindex];incr pcindex; return [list pc 32 $v]}
proc mww {address value count} {
    if {$address != 0xa0006400 || $value != 0 || $count != 64} {error "Forbidden write"}
    puts "ZERO $address $value $count"
}
proc load_image {path address kind} {
    if {$address != 0xa0005000 || $kind ne "bin"} {error "Wrong code write"}
    puts LOADED
}
proc verify_image {args} {error "Injected verify failure"}
proc resume {address} {if {$address != 0xa0005000} {error "Wrong resume"};puts RESUMED}
proc sleep {args} {}
proc halt {args} {}
proc dump_image {path address count} {
    if {$address != 0xa0006400 || $count != 256} {error "Wrong dump"}
    puts DUMPED
}
proc microdma_capture_r19 {label} {puts "SNAP $label"}
proc echo {args} {puts [join $args]}
set status [catch {

set md [read_memory 0xa0006000 32 30]
if {[llength $md] != 30} {error "Incomplete previous journal"}
foreach i {0 1 2 3} want {0x4d443132 1 8 0xfffffffb} {
    if {[lindex $md $i] != $want} {error "Readback requires reviewed phase8 result-5"}
}
if {[lindex $md 28] != 32 || [lindex $md 29] != 32} {error "Seed/target verification missing"}
set rb_before_pc [lindex [reg pc] 2]
if {$rb_before_pc != 0x80000000 && $rb_before_pc != 0x80000004} {error "CPU not parked before reader"}
mww 0xa0006400 0 64
set rb_empty [read_memory 0xa0006400 32 64]
if {[llength $rb_empty] != 64} {error "Incomplete cleared reader journal"}
foreach value $rb_empty {if {$value != 0} {error "Reader journal clear not verified"}}
echo READBACK_ZERO_VERIFIED
load_image {/fixture/readback.bin} 0xa0005000 bin
verify_image {/fixture/readback.bin} 0xa0005000 bin
echo READBACK_START
resume 0xa0005000
sleep 2000
halt 1000
set rb_after_pc [lindex [reg pc] 2]
echo "READBACK_PC [reg pc]"
dump_image {/fixture/out/readback.bin} 0xa0006400 256
if {$rb_after_pc != 0x80000000 && $rb_after_pc != 0x80000004} {error "CPU did not return to ROM after reader"}
echo READBACK_RETURN_VERIFIED
microdma_capture_r19 READBACK_AFTER
sleep 100
microdma_capture_r19 READBACK_AFTER100
echo READBACK_COLLECTED

} message]
puts "CAUGHT $status $message"
