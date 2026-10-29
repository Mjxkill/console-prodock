init
halt
riscv set_enable_virt2phys off
if {[lindex [reg pc] 2] != 0xa00001e8 || [lindex [reg priv] 2] != 3} {error "Not the failed ILM launcher"}
if {([lindex [read_memory 0xa00001e8 32 1] 0] & 0xffff) != 0xa001} {error "Failed loop fingerprint differs"}
echo NEO_FAILED_LAUNCHER_CONFIRMED
shutdown
