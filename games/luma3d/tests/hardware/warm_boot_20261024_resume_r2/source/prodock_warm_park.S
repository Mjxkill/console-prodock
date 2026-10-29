/* Volatile M-mode parking stage, entered ONLY after explicit DCSR.prv=M.
 * Flush the old Linux D-cache BEFORE the packed image is written to DDR.
 * Uses only ILM code, DLM status and the already configured UART2. No DDR
 * writes except completion of old cache writebacks; no FPGA/SD/flash reset.
 * CSR 0x7cc=6 is the ae350_dcache_flush_all operation in the frozen R17
 * launcher cache.o. 0x7ca bits0/1 enable I/D caches; clear after flush.
 */
.section .text
.option norvc
.option norelax
.globl _start
_start:
    csrwi mie, 0
    csrwi mstatus, 0
    csrwi satp, 0
    sfence.vma
    la t0, failure
    csrw mtvec, t0
    csrwi mideleg, 0
    csrwi medeleg, 0
    fence iorw, iorw
    csrwi 0x7cc, 6
    fence iorw, iorw
    csrr t0, 0x7ca
    andi t0, t0, -4
    csrw 0x7ca, t0
    fence.i
    csrr t0, satp
    bnez t0, failure
    csrr t0, 0x7ca
    andi t0, t0, 3
    bnez t0, failure
    li s0, 0xf0300000
    li t0, 0x83
    sw t0, 0x2c(s0)
    li t0, 43
    sw t0, 0x20(s0)
    sw zero, 0x24(s0)
    li t0, 3
    sw t0, 0x2c(s0)
    sw zero, 0x24(s0)
    li t0, 7
    sw t0, 0x28(s0)
    li t0, 0xa0207e00
    li t1, 0x5741524d
    sw t1, 0(t0)
    la a0, ready
    jal ra, puts
park:
    lw t0, 0x34(s0)
    andi t0, t0, 1
    beqz t0, park
    lw t0, 0x20(s0)
    andi t0, t0, 255
    li t1, 63
    beq t0, t1, identify
    li t1, 99
    beq t0, t1, paused
    j park
identify:
    la a0, identity
    jal ra, puts
    j park
paused:
    la a0, pause_ack
    jal ra, puts
    j park
puts:
    lbu t1, 0(a0)
    beqz t1, puts_end
tx_wait:
    lw t0, 0x34(s0)
    andi t0, t0, 32
    beqz t0, tx_wait
    sw t1, 0x20(s0)
    addi a0, a0, 1
    j puts
puts_end:
    ret
.balign 4
failure:
    li s0, 0xf0300000
    li t0, 0xa0207e00
    li t1, 0xbad00001
    sw t1, 0(t0)
    csrr t1, mcause
    sw t1, 4(t0)
    la a0, failed
    jal ra, puts
failed_loop:
    j failed_loop
.section .rodata
ready: .asciz "\r\nPRODOCK WARM PARK M=3 SATP=0 CACHE=OFF READY\r\n"
identity: .asciz "\r\nMegaPro GPU LUMA3D WARM PARK R1\r\n"
pause_ack: .asciz "\r\nRASTER PAUSED\r\n"
failed: .asciz "\r\nPRODOCK WARM PARK FAIL\r\n"
