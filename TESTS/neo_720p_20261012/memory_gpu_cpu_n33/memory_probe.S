/* Volatile diagnostic only: execute in ILM, touch scratch DDR 0x12000000.
 * C000 holds the verified expected pattern; B000/D000 hold CPU readbacks.
 * E000 holds status. Always return to the known external boot parking loop.
 */
.option norvc
.section .text
.global _start
_start:
    li t0, 0
    csrw mie, t0
    csrw mstatus, t0
    la t0, trap
    csrw mtvec, t0
    li s0, 0xa000e000
    li t0, 0x4d435055
    sw t0, 0(s0)
    sw zero, 4(s0)
    sw zero, 8(s0)
    sw zero, 12(s0)
#ifdef PROBE_GPU
    sw zero, 16(s0)
    sw zero, 20(s0)
    sw zero, 24(s0)
    sw zero, 28(s0)
#endif
    /* Read the pattern previously written by JTAG, without changing DDR. */
    li t0, 0x12000000
    li t1, 0xa000b000
    li t2, 1024
read_jtag:
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    addi t2, t2, -1
    bnez t2, read_jtag
    li t0, 1
    sw t0, 4(s0)
    /* Write the same verified pattern with CPU stores. */
    li t0, 0xa000c000
    li t1, 0x12000000
    li t2, 1024
write_cpu:
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    addi t2, t2, -1
    bnez t2, write_cpu
    fence iorw, iorw
    li t0, 2
    sw t0, 4(s0)
    li t0, 0x12000000
    li t1, 0xa000d000
    li t2, 1024
read_cpu:
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    addi t2, t2, -1
    bnez t2, read_cpu
    li t0, 3
    sw t0, 4(s0)
#ifdef PROBE_GPU
    /* Exercise the GPU command port with CPU MMIO stores, independent of
     * OpenOCD's repeated writes to one FIFO address. TARGET does no DMA. */
    li s1, 0xe9001000
    lw t0, 0(s1)
    sw t0, 24(s0)
    li t1, 0x424c5432
    bne t0, t1, gpu_bad_id
    lw s2, 8(s1)
    sw s2, 16(s0)
    addi s2, s2, 1
    slli s2, s2, 16
    srli s2, s2, 16
    la t0, gpu_target
    li t1, 8
gpu_send:
    lw t2, 0(t0)
    sw t2, 16(s1)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, gpu_send
    fence iorw, iorw
    li t1, 50000
gpu_poll:
    lw t2, 8(s1)
    sw t2, 20(s0)
    slli t2, t2, 16
    srli t2, t2, 16
    beq t2, s2, gpu_ok
    addi t1, t1, -1
    bnez t1, gpu_poll
    li t0, -1
    j gpu_result
gpu_bad_id:
    li t0, -2
    j gpu_result
gpu_ok:
    li t0, 1
gpu_result:
    sw t0, 28(s0)
#endif
park:
    fence iorw, iorw
    li t0, 0x80000000
    jr t0
.balign 4
trap:
    li s0, 0xa000e000
    csrr t0, mcause
    sw t0, 8(s0)
    csrr t0, mtval
    sw t0, 12(s0)
    li t0, -1
    sw t0, 4(s0)
    j park
#ifdef PROBE_GPU
.balign 4
gpu_target:
    .word 0x16000000, 0x12000000, 0x12001000, 0x00200040
    .word 0x00400040, 0, 0, 0
#endif
