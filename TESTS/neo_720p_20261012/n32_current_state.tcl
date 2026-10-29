gdb_port disabled
tcl_port disabled
telnet_port disabled
init
poll
set was_running [expr {[nds.cpu curstate] eq "running"}]
set failed [catch {
    halt
    echo "NEO_N32_CURRENT_STATE was_running=$was_running"
    echo "NEO_N32_PC [reg pc]"
    echo "NEO_N32_PRIV [reg priv]"
    echo "NEO_N32_SATP [reg satp]"
    echo "NEO_N32_MSTATUS [reg mstatus]"
} reason]
if {$was_running} {resume}
echo "NEO_N32_STATE_RESULT $failed $reason"
shutdown
