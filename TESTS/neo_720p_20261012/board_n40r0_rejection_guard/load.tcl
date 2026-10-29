riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
set geometry [read_memory 0xe9000070 32 2]
if {[lindex $geometry 0] != 0x02d00500 || [lindex $geometry 1] != 0x02ee0672} {error "Wrong live GPU geometry"}
set parking [read_memory 0x80000000 32 2]
if {[lindex $parking 0] != 0x10500073 || [lindex $parking 1] != 0xffdff06f} {error "Boot RAM initialization mismatch"}
set pads [read_memory 0xe9004000 32 2]
if {[lindex $pads 0] != 0x4e504144 || [lindex $pads 1] != 0x00010002} { error "Wrong Neo gamepad ABI" }
set usb [read_memory 0xe9003000 32 1]
if {[lindex $usb 0] != 0x554d5343} { error "Missing SOFT-USB MMIO" }
echo "NEO_GEOMETRY_AND_BOOT_RAM_OK"
echo NEO_MEMORY_PREFLIGHT_BEGIN
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0xa0000000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0xa0000000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0xa0000000 bin
echo "NEO_MEMORY_PREFLIGHT_OK 0xa0000000"
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x10000000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x10000000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x10000000 bin
echo "NEO_MEMORY_PREFLIGHT_OK 0x10000000"
load_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x1034e000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x1034e000 bin
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n40r0_rejection_guard/memory_pattern.bin} 0x1034e000 bin
echo "NEO_MEMORY_PREFLIGHT_OK 0x1034e000"
if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU command ABI"}
set done_before [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]
set gpu_error_registers {0xe900100c 0xe900101c 0xe9001024 0xe9001034 0xe900104c}
foreach address $gpu_error_registers {set gpu_error_before($address) [lindex [read_memory $address 32 1] 0]}
write_memory 0xe9001010 32 {0x16000000}
write_memory 0xe9001010 32 {0x12000000}
write_memory 0xe9001010 32 {0x12001000}
write_memory 0xe9001010 32 {0x200040}
write_memory 0xe9001010 32 {0x400040}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
write_memory 0xe9001010 32 {0x0}
sleep 20
echo "NEO_GPU_PREFLIGHT_STATUS [read_memory 0xe9001000 32 18]"
if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) != (($done_before+1)&0xffff)} {error "GPU preflight command did not complete"}
foreach address $gpu_error_registers {
  set after [lindex [read_memory $address 32 1] 0]
  if {$after != $gpu_error_before($address)} {error "GPU preflight command rejected/lost at $address: $gpu_error_before($address) -> $after"}
}
echo NEO_GPU_PREFLIGHT_OK
echo "NEO_USB_PREFLIGHT_STATUS [read_memory 0xe9003000 32 2]"
echo NEO_PREFLIGHT_ONLY_COMPLETE
shutdown
