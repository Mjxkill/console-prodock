riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
if {[lindex [reg pc] 2] != 0xa00001e8 || [lindex [reg priv] 2] != 3} { error "Not the observed failed launcher loop" }
if {([lindex [read_memory 0xa00001e8 32 1] 0] & 0xffff) != 0xa001} { error "Launcher loop fingerprint differs" }
echo "NEO_PC [reg pc]"
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
echo "NEO_USB_MSC [read_memory 0xe9003000 32 2]"
echo "NEO_USB_TRACE_BEFORE [read_memory 0xe9002000 32 3]"
write_memory 0xe900200c 32 {2}
sleep 20
echo "NEO_USB_TRACE_AFTER [read_memory 0xe9002000 32 3]"
echo "NEO_USB_TRACE_SNAPSHOT [read_memory 0xe9002040 32 32]"
load_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/pattern.bin} 0x12000000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/read1.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/read2.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/stage_head.bin} 0x10000000 4096
load_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/pattern.bin} 0xa000f000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_ilm_n18r2/ilm_read.bin} 0xa000f000 4096
shutdown
