/* R19 diagnostic only. CPU executes from ILM with NO stack and NO DDR code.
 * Exact DDR footprint: [0x12000000,0x12000080), thirty-two words.
 * Journal512B at0xa0006000; code linked at0xa0004000, must fit4096B.
 * Fresh parked CPU, MCACHE_CTL==0 and MILMB==a0000001 are prerequisites.
 * Finite poll loops cannot bound a hung AHB transaction: host watchdog required.
 */
.option norvc
.option norelax
.section .text
.global _start
_start:
    li s0, 0xa0006000
    mv t0, s0
    li t1, 128
zero_journal:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, zero_journal
    li t0, 0x4d443132
    sw t0, 0(s0)
    li t0, 1
    sw t0, 4(s0)
    sw t0, 8(s0)
    csrr s7, mtvec
    sw s7, 28(s0)
    csrr s8, mstatus
    sw s8, 32(s0)
    csrr s9, mie
    sw s9, 36(s0)
    la t0, trap
    csrw mtvec, t0
    /* Do not flush a possibly dirty foreign cache. Refuse if either cache
     * is enabled: root already measured this register as zero on parked R19. */
    csrr t0, 0x7ca
    sw t0, 16(s0)
    bnez t0, bad_guard
    csrr t0, 0x7c0
    sw t0, 24(s0)
    li t1, 0xa0000001
    bne t0, t1, bad_guard
    csrr t0, satp
    bnez t0, bad_guard
    bnez s9, bad_guard
    andi t0, s8, 8
    bnez t0, bad_guard
    fence iorw, iorw
    fence.i
    li s1, 0xe9001000
    lw t0, 0(s1)
    sw t0, 68(s0)
    li t1, 0x424c5432
    bne t0, t1, bad_guard
    lw t0, 4(s1)
    bnez t0, bad_guard
    lw t0, 8(s1)
    sw t0, 72(s0)
    bnez t0, bad_guard
    jal ra, check_gpu_errors
    bnez a0, bad_guard
    li t0, 0xe9000000
    lw t1, 8(t0)
    bnez t1, bad_guard
    lw t1, 12(t0)
    bnez t1, bad_guard
    lw t1, 20(t0)
    bnez t1, bad_guard
    /* CPU seeds every word. Address-derived words make aliases observable. */
    li t0, 2
    sw t0, 8(s0)
    li t0, 0x12000000
    li t1, 32
    li t2, 0xa5396c17
seed:
    sw t0, 100(s0)
    xor t3, t0, t2
    sw t3, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, seed
    fence iorw, iorw
    li t0, 3
    sw t0, 8(s0)
    li a1, 0
    addi a2, s0, 128
    jal ra, verify_memory
    sw a3, 112(s0)
    bnez a0, bad_seed
    /* TARGET is the negative control: it must not touch the DDR payload. */
    li t0, 4
    sw t0, 8(s0)
    la a0, target_words
    jal ra, send_packet
    li t0, 5
    sw t0, 8(s0)
    li a0, 1
    jal ra, wait_done
    sw a1, 76(s0)
    bnez a0, bad_target_wait
    li t0, 6
    sw t0, 8(s0)
    li a1, 0
    addi a2, s0, 256
    jal ra, verify_memory
    sw a3, 116(s0)
    bnez a0, bad_target_memory
    /* COPY extent0 retains the source descriptor but issues no native traffic.
     * Z and the other96B remain canaries. */
    li t0, 7
    sw t0, 8(s0)
    la a0, copy_words
    jal ra, send_packet
    li t0, 8
    sw t0, 8(s0)
    li a0, 2
    jal ra, wait_done
    sw a1, 80(s0)
    bnez a0, bad_copy_wait
    li t0, 9
    sw t0, 8(s0)
    li a1, 0
    addi a2, s0, 384
    jal ra, verify_memory
    sw a3, 120(s0)
    bnez a0, bad_copy_memory
    csrr t0, 0x7ca
    sw t0, 20(s0)
    bnez t0, bad_guard
    li t0, 10
    sw t0, 8(s0)
    li t0, 1
    j finish

/* a0 points to exactly8 words in ILM. No FIFO polling can block forever
 * in software; a failed MMIO access itself still needs the host watchdog. */
send_packet:
    li t0, 8
send_word:
    li t1, 50000
send_poll:
    lw t2, 4(s1)
    andi t2, t2, 2
    beqz t2, send_ready
    addi t1, t1, -1
    bnez t1, send_poll
    li t0, -9
    j finish
send_ready:
    sw t0, 96(s0)
    lw t2, 0(a0)
    sw t2, 16(s1)
    addi a0, a0, 4
    addi t0, t0, -1
    bnez t0, send_word
    fence iorw, iorw
    ret

/* a0 expected done count. Require that count AND BUSY/FULL==0; CSR values
 * cross domains independently, so neither observation alone is a fence. */
wait_done:
    li t0, 50000
wait_poll:
    lw a1, 8(s1)
    bne a1, a0, wait_more
    lw t1, 4(s1)
    beqz t1, wait_success
wait_more:
    addi t0, t0, -1
    bnez t0, wait_poll
    li a0, 1
    ret
wait_success:
    /* Tail-call retains caller return address. */
    j check_gpu_errors
check_gpu_errors:
    lw t1, 12(s1)
    sw t1, 84(s0)
    lw t2, 28(s1)
    sw t2, 88(s0)
    lw t3, 52(s1)
    sw t3, 92(s0)
    or a0, t1, t2
    or a0, a0, t3
    ret

/* a1=0 expects seed everywhere; a1=1 expects the source seed at offsets32..63.
 * a2 is one128B ILM image. Return a0=error count,a3=words compared.
 * This is a CPU load path: debugger transport never reads DDR for us. */
verify_memory:
    fence iorw, iorw
    li t0, 0x12000000
    li t1, 32
    li t2, 0xa5396c17
    li a0, 0
    li a3, 0
verify_word:
    sw t0, 100(s0)
    xor t3, t0, t2
    beqz a1, verify_load
    li t5, 0x12000020
    bltu t0, t5, verify_load
    li t5, 0x12000040
    bgeu t0, t5, verify_load
    addi t3, t0, -32
    xor t3, t3, t2
verify_load:
    lw t4, 0(t0)
    sw t4, 0(a2)
    beq t3, t4, verify_next
    bnez a0, verify_count
    sw t0, 52(s0)
    sw t3, 56(s0)
    sw t4, 60(s0)
verify_count:
    addi a0, a0, 1
verify_next:
    addi a3, a3, 1
    addi t0, t0, 4
    addi a2, a2, 4
    addi t1, t1, -1
    bnez t1, verify_word
    sw a0, 64(s0)
    ret

bad_guard:         li t0,-1; j finish
bad_seed:          li t0,-2; j finish
bad_target_wait:   li t0,-3; j finish
bad_target_memory: li t0,-4; j finish
bad_copy_wait:     li t0,-5; j finish
bad_copy_memory:   li t0,-6; j finish
.balign 4
trap:
    li s0, 0xa0006000
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
    /* mstatus/mie/cache have never been modified by the program. */
    li t0, 0x80000000
    jr t0
.balign 4
target_words:
    .word 0x16000000,0x12000020,0x12000040,0x00100001
    .word 0x00200020,0,0,0
copy_words:
    .word 0x1d000000,0x12000000,0x00100001,0x00000020
    .word 0,0,0,0
