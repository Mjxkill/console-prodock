riscv expose_csrs 1994,1996,2000
init
halt
riscv set_enable_virt2phys off
echo "NEO_PC [reg pc]"
reg priv 3
reg satp 0
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
load_image {/home/michael/console/TESTS/neo_720p_20261012/memory_n18r2/pattern.bin} 0x12000000 bin
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_n18r2/read1.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_n18r2/read2.bin} 0x12000000 4096
dump_image {/home/michael/console/TESTS/neo_720p_20261012/memory_n18r2/stage_head.bin} 0x10000000 4096
shutdown
