/* CPU-only second stage after reviewed COPY failure; no DDR or GPU writes.
 * ILM code a0005000..5fff, new journal256B a0006400..64ff.
 * Parent must capture GPU before this read: CPU traffic may change arbitration.
 */
.option norvc
.option norelax
.section .text
.global _start
_start:
    li s0, 0xa0006400
    mv t0, s0
    li t1, 64
zero_journal:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, zero_journal
    li t0, 0x52423132
    sw t0, 0(s0)
    li t0, 1
    sw t0, 4(s0)
    sw t0, 8(s0)
    csrr s7, mtvec
    sw s7, 28(s0)
    csrr t0, mstatus
    sw t0, 32(s0)
    andi t1, t0, 8
    csrr t0, mie
    sw t0, 36(s0)
    or t1, t1, t0
    la t0, trap
    csrw mtvec, t0
    bnez t1, bad_guard
    csrr t0, 0x7ca
    sw t0, 16(s0)
    bnez t0, bad_guard
    csrr t0, 0x7c0
    sw t0, 24(s0)
    li t1, 0xa0000001
    bne t0, t1, bad_guard
    csrr t0, satp
    bnez t0, bad_guard
    /* Exact expected previous stage, not a generic arbitrary-memory reader. */
    li t0, 0xa0006000
    lw t1, 0(t0)
    li t2, 0x4d443132
    bne t1, t2, bad_guard
    lw t1, 4(t0)
    li t2, 1
    bne t1, t2, bad_guard
    lw t1, 8(t0)
    li t2, 8
    bne t1, t2, bad_guard
    lw t1, 12(t0)
    li t2, -5
    bne t1, t2, bad_guard
    lw t1, 112(t0)
    li t2, 32
    bne t1, t2, bad_guard
    lw t1, 116(t0)
    bne t1, t2, bad_guard
    li t0, 0xe9000000
    lw t1, 8(t0)
    bnez t1, bad_guard
    lw t1, 12(t0)
    bnez t1, bad_guard
    lw t1, 20(t0)
    bnez t1, bad_guard
    li s1, 0xe9001000
    lw t0, 0(s1)
    sw t0, 68(s0)
    li t1, 0x424c5432
    bne t0, t1, bad_guard
    lw t0, 8(s1)
    sw t0, 72(s0)
    lw t0, 4(s1)
    sw t0, 80(s0)
    lw t0, 12(s1)
    sw t0, 88(s0)
    lw t0, 28(s1)
    sw t0, 96(s0)
    lw t0, 52(s1)
    sw t0, 104(s0)
    fence iorw, iorw
    li t0, 2
    sw t0, 8(s0)
    li t0, 0x12000000
    li t1, 32
    li t2, 0xa5396c17
    addi a2, s0, 128
    li a0, 0
    li a3, 0
read_word:
    sw t0, 112(s0)
    xor t3, t0, t2
    li t5, 0x12000020
    bltu t0, t5, load_word
    li t5, 0x12000040
    bgeu t0, t5, load_word
    addi t3, t0, -32
    xor t3, t3, t2
load_word:
    lw t4, 0(t0)
    sw t4, 0(a2)
    beq t3, t4, read_next
    bnez a0, count_error
    sw t0, 52(s0)
    sw t3, 56(s0)
    sw t4, 60(s0)
count_error:
    addi a0, a0, 1
read_next:
    addi a3, a3, 1
    sw a3, 116(s0)
    sw a0, 64(s0)
    addi t0, t0, 4
    addi a2, a2, 4
    addi t1, t1, -1
    bnez t1, read_word
    fence iorw, iorw
    lw t0, 8(s1)
    sw t0, 76(s0)
    lw t0, 4(s1)
    sw t0, 84(s0)
    lw t0, 12(s1)
    sw t0, 92(s0)
    lw t0, 28(s1)
    sw t0, 100(s0)
    lw t0, 52(s1)
    sw t0, 108(s0)
    csrr t0, 0x7ca
    sw t0, 20(s0)
    bnez t0, bad_guard
    li t0, 3
    sw t0, 8(s0)
    /* Result1 means all32 reads completed, not GPU success or unchanged state. */
    li t0, 1
    j finish
bad_guard:
    li t0, -1
    j finish
.balign 4
trap:
    li s0, 0xa0006400
    csrr t0, mcause
    sw t0, 40(s0)
    csrr t0, mtval
    sw t0, 44(s0)
    csrr t0, mepc
    sw t0, 48(s0)
    li t0, -7
finish:
    sw t0, 12(s0)
    fence iorw, iorw
    csrw mtvec, s7
    li t0, 0x80000000
    jr t0
