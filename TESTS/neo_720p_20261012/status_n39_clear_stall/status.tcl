init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
echo "NEO_SCAN_BEFORE [read_memory 0xe9000000 32 30]"
echo "NEO_GPU_BEFORE [read_memory 0xe9001000 32 26]"
echo "NEO_USB_BEFORE [read_memory 0xe9003000 32 2]"
echo "NEO_PAD0_BEFORE [read_memory 0xe9004020 32 5]"
echo "NEO_PAD1_BEFORE [read_memory 0xe9004040 32 5]"
sleep 1000
echo "NEO_SCAN_AFTER [read_memory 0xe9000000 32 30]"
echo "NEO_GPU_AFTER [read_memory 0xe9001000 32 26]"
echo "NEO_USB_AFTER [read_memory 0xe9003000 32 2]"
echo "NEO_PAD0_AFTER [read_memory 0xe9004020 32 5]"
echo "NEO_PAD1_AFTER [read_memory 0xe9004040 32 5]"
shutdown
