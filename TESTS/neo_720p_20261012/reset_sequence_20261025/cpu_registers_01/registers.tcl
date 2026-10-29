init
halt
echo R15_CPU_HALTED
reg pc
echo "GPU_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "GPU_1 [read_memory 0xe9000000 32 32]"
echo R15_REGISTER_READ_COMPLETE
shutdown
