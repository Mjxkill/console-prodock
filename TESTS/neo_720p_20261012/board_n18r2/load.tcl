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
load_image {/home/michael/console/linux/build-neo/payload.rle.bin} 0x10000000 bin
load_image {/home/michael/console/linux/build-neo/launch_packed.bin} 0xa0000000 bin
verify_image {/home/michael/console/linux/build-neo/launch_packed.bin} 0xa0000000 bin
echo "NEO_PAD0_BEFORE [read_memory 0xe9004020 32 5]"
echo "NEO_PAD1_BEFORE [read_memory 0xe9004040 32 5]"
sleep 200
echo "NEO_PAD0_AFTER [read_memory 0xe9004020 32 5]"
echo "NEO_PAD1_AFTER [read_memory 0xe9004040 32 5]"
reg a0 0
reg a1 0
reg a2 0
resume 0xa000000c
shutdown
