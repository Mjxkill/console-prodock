// mini_uart.S — preuve de vie CPU via UART2 direct (sans BSP, sans printf, sans polling).
// Offsets UART 16550 du AE350 (BSP ae350.h) : THR/DLL=0x20, DLM=0x24, FCR=0x28, LCR=0x2C.
// Émet 'A' en continu (délai entre octets).
    .section .nds_vector, "ax"
    .global reset_vector
reset_vector:
    j _start
    .align 2

    .section .text
    .global _start
_start:
    li   t0, 0xF0300000       // UART2 base
    li   t1, 0x83             // LCR : DLAB=1, 8N1
    sw   t1, 0x2C(t0)
    li   t1, 54               // div = 100e6/(16*115200) = 54 (DLL)
    sw   t1, 0x20(t0)
    li   t1, 0
    sw   t1, 0x24(t0)         // DLM
    li   t1, 0x03             // LCR : 8N1, DLAB=0
    sw   t1, 0x2C(t0)
    li   t1, 0x07             // FCR : FIFO on
    sw   t1, 0x28(t0)
    li   t3, 0x41             // 'A'
loop:
    sw   t3, 0x20(t0)         // THR : chaque écriture émet un octet
    li   t2, 200000           // délai
d1: addi t2, t2, -1
    bnez t2, d1
    j    loop
