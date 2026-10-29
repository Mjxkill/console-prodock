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
