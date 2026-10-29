init
halt
riscv set_enable_virt2phys off
set registers [get_reg -force {pc priv satp}]
set pc [dict get $registers pc]
if {($pc!=0x80000000 && $pc!=0x80000004) || [dict get $registers priv]!=3 || [dict get $registers satp]!=0} {error "Expected parked CPU in M mode, no Linux"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000000 32 1] 0]!=0x47505531 || [lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong GPU/geometry"}
echo "PARKED_CPU $pc"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
if {[lindex [read_memory 0xe9001008 32 1] 0]!=1 || [lindex [read_memory 0xe9001034 32 1] 0]!=1} {error "R18r1 counter anchor changed"}
if {[lindex [read_memory 0xe9005080 32 1] 0]!=0x4e435031 || [lindex [read_memory 0xe9005088 32 1] 0]!=1 || [lindex [read_memory 0xe900508c 32 1] 0]!=1} {error "R18r1 observer anchor changed"}
echo CASE_BEGIN_0
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=1} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==2} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_0
echo CASE_BEGIN_1
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=2} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==3} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_1
echo CASE_BEGIN_2
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=3} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==4} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_2
echo CASE_BEGIN_3
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=4} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==5} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_3
echo CASE_BEGIN_4
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=5} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==6} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_4
echo CASE_BEGIN_5
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=6} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==7} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_5
echo CASE_BEGIN_6
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=7} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x16000000 0x12000000 0x12010000 0x800010 0x1000100 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==8} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_6
echo CASE_BEGIN_7
proc word {address} {return [lindex [read_memory $address 32 1] 0]}
set ready 0
for {set i 0} {$i<100} {incr i} {
    if {[word 0xe9005080]==0x4e435031 && ([word 0xe9005084]&7)==4} {set ready 1;break}
    sleep 10
}
if {!$ready} {error "NCP1 absent or not ready"}
set beat [word 0xe9005098]
sleep 10
if {[word 0xe9005098]==$beat} {error "GPU heartbeat stopped"}
set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=8} {error "GPU already active before first TARGET"}
foreach index {3 7 9 19} {if {[lindex $gpu $index]!=0} {error "Initial GPU error"}}
if {[word 0xe9005000]!=0x4e474442} {error "Legacy observer signature changed"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
set arm [word 0xe9005088]
set seq [word 0xe900508c]
set status [word 0xe9005084]
set epoch [expr {1-(($status>>5)&1)}]
if {$status&3} {error "Observer busy before arm"}
write_memory 0xe9005084 32 {1}
set armed 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==4 && (($status>>5)&1)==$epoch && [word 0xe9005088]==(($arm+1)&0xffffffff)} {set armed 1;break}
    sleep 10
}
if {!$armed} {error "Explicit arm handshake failed"}
echo "ARMED $epoch $status [word 0xe9005088]"
foreach w {0x1e000000 0x0 0x0 0x0 0x0 0x0 0x0 0x0} {
    if {[word 0xe9001004]&2} {error "Unexpected full command FIFO"}
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==9} {set complete 1;break}
    sleep 10
}
echo "GPU_AFTER $gpu"
if {!$complete} {error "First TARGET did not finish"}
echo "RAW_AFTER [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
write_memory 0xe9005088 32 {1}
set snapped 0
for {set i 0} {$i<100} {incr i} {
    set status [word 0xe9005084]
    if {($status&0x4f)==12 && [word 0xe900508c]==(($seq+1)&0xffffffff)} {set snapped 1;break}
    sleep 10
}
if {!$snapped} {error "Snapshot handshake failed"}
for {set i 0} {$i<3} {incr i} {
    echo "NCP_${i} [read_memory 0xe9005080 32 7]"
    sleep 2
}
echo TARGET_CAPTURE_COMPLETE
echo CASE_END_7
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
echo REPEAT_COMPLETE
shutdown
