# PREPARE ONLY. No init/transport/CPU resume here. Root owns the controller,
# board identity, R19 SHA, Neo lock, host watchdog and unconditional restoration.
# Source only inside that reviewed controller after its exact R19 guards.
# One write to NGDB+4 requests an observation-only snapshot; no GPU command.
proc microdma_capture_r19 {label} {
    if {![regexp {^[A-Za-z0-9_]+$} $label]} {error "Unsafe capture label"}
    set base 0xe9005000
    set id [lindex [read_memory $base 32 1] 0]
    if {$id != 0x4e474442} {error "R19 NGDB identity mismatch"}
    set before [read_memory 0xe9005004 32 3]
    set status [lindex $before 0]
    set sequence [lindex $before 2]
    if {($status & 5) != 4} {error "NGDB not ready or request already active"}
    echo "MICRODMA_${label}_BEFORE $before"
    mww 0xe9005004 1
    set complete 0
    for {set tries 0} {$tries < 32} {incr tries} {
        set state [read_memory 0xe9005004 32 3]
        if {([lindex $state 0] & 7) == 6 &&
            [lindex $state 2] == (($sequence + 1) & 0xffffffff)} {
            set complete 1
            break
        }
        sleep 2
    }
    if {!$complete} {error "NGDB snapshot did not complete; do not interpret stale payload"}
    # These ten words are held coherent snapshot data: received,last,live[255:0].
    # The headers at +18/+1c are separate asynchronous diagnostic taps.
    set first [read_memory 0xe9005010 32 12]
    set second [read_memory 0xe9005010 32 12]
    foreach i {0 1 4 5 6 7 8 9 10 11} {
        if {[lindex $first $i] != [lindex $second $i]} {
            error "Held snapshot changed during read"
        }
    }
    set after [read_memory 0xe9005004 32 3]
    if {([lindex $after 0] & 7) != 6 || [lindex $after 2] != (($sequence + 1) & 0xffffffff)} {
        error "NGDB snapshot identity changed"
    }
    echo "MICRODMA_${label}_SNAPSHOT_A $first"
    echo "MICRODMA_${label}_SNAPSHOT_B $second"
    echo "MICRODMA_${label}_AFTER $after"
    echo "MICRODMA_${label}_GPU [read_memory 0xe9001000 32 26]"
    return $first
}

riscv expose_csrs 1984,1985,1994,1996
init
halt 1000
echo "CONTEXT_PC [reg pc]"
set here [lindex [reg pc] 2]
if {$here != 0x80000000 && $here != 0x80000004} {error "CPU is not parked; stop context probe"}
echo "CONTEXT_PRIV [reg priv]"
echo "CONTEXT_SATP [reg satp]"
echo "CONTEXT_MSTATUS [reg mstatus]"
echo "CONTEXT_MIE [reg mie]"
echo "CONTEXT_ILM [reg csr1984]"
echo "CONTEXT_DLM [reg csr1985]"
echo "CONTEXT_CACHE [reg csr1994]"
echo "CONTEXT_ROM [read_memory 0x80000000 32 2]"
echo "CONTEXT_VIDEO [read_memory 0xe9000000 32 3]"
echo "CONTEXT_GPU [read_memory 0xe9001000 32 4]"
echo "CONTEXT_DONE"

if {[lindex [reg csr1994] 2] != 0} {error "Caches are enabled"}
if {[lindex [reg csr1984] 2] != 0xa0000001} {error "Unexpected ILM mapping"}
microdma_capture_r19 BEFORE
load_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_probe_01/firmware_delivery_01/build_01/microdma.bin} 0xa0004000 bin
verify_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_probe_01/firmware_delivery_01/build_01/microdma.bin} 0xa0004000 bin
resume 0xa0004000
sleep 2000
halt 1000
echo "MICRODMA_PC [reg pc]"
dump_image {/home/michael/console/TESTS/neo_common_cause_20261028/root_copy_readback_run_01/journal.bin} 0xa0006000 512
echo "MICRODMA_GPU [read_memory 0xe9001000 32 14]"
microdma_capture_r19 AFTER
sleep 100
microdma_capture_r19 AFTER100

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
load_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/build_01/readback.bin} 0xa0005000 bin
verify_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/build_01/readback.bin} 0xa0005000 bin
echo READBACK_START
resume 0xa0005000
sleep 2000
halt 1000
set rb_after_pc [lindex [reg pc] 2]
echo "READBACK_PC [reg pc]"
dump_image {/home/michael/console/TESTS/neo_common_cause_20261028/root_copy_readback_run_01/readback.bin} 0xa0006400 256
if {$rb_after_pc != 0x80000000 && $rb_after_pc != 0x80000004} {error "CPU did not return to ROM after reader"}
echo READBACK_RETURN_VERIFIED
microdma_capture_r19 READBACK_AFTER
sleep 100
microdma_capture_r19 READBACK_AFTER100
echo READBACK_COLLECTED

echo MICRODMA_COLLECTED

shutdown
