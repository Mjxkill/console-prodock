riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
set pc [lindex [reg pc] 2]
if {($pc != 0x80000000 && $pc != 0x80000004) || [lindex [reg priv] 2] != 3} {error "CPU is not in the boot parking loop"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot parking fingerprint differs"}
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU ABI"}
if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU is not idle"}
if {[lindex [read_memory 0xe9000004 32 1] 0] != 0} {error "Scanout is enabled"}
echo LEGACY_BEGIN
load_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_legacy_n33/pattern.bin} 0x800000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_legacy_n33/pattern.bin} 0x800000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_legacy_n33/before.bin} 0x800000 128
echo "LEGACY_BEFORE [read_memory 0xe9001004 32 3]"
write_memory 0xe9001010 32 {0x100a600}
write_memory 0xe9001010 32 {0x200000}
write_memory 0xe9001010 32 {0x200001}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 100
echo "LEGACY_AFTER [read_memory 0xe9001004 32 3]"
dump_image {/home/michael/console/TESTS/neo_720p_20261012/gpu_legacy_n33/after.bin} 0x800000 128
echo LEGACY_COMPLETE
shutdown
