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
load_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/microdma_r1/build_01/microdma.bin} 0xa0004000 bin
verify_image {/home/michael/console/TESTS/neo_common_cause_20261028/execution_diagnostic_02/microdma_r1/build_01/microdma.bin} 0xa0004000 bin
resume 0xa0004000
sleep 2000
halt 1000
echo "MICRODMA_PC [reg pc]"
dump_image {/home/michael/console/TESTS/neo_common_cause_20261028/root_microdma_board_01/journal.bin} 0xa0006000 512
echo "MICRODMA_GPU [read_memory 0xe9001000 32 14]"
echo MICRODMA_COLLECTED
