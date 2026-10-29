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
shutdown
