// demo_led.S — défilement LED, attente réduite de 100 à 5 millions d'itérations.
// La durée dépend des accès aux instructions et des branches, pas seulement des 800 MHz du cœur.
// GPIO base 0xF0700000 : CHANNELDIR @0x28, DOUTCLEAR @0x2C, DOUTSET @0x30.
    .equ LED_DELAY_ITERATIONS, 5000000
    .section .nds_vector, "ax"
    .global reset_vector
reset_vector:
    j _start
    .align 2

    .section .text
    .global _start
_start:
    li   t0, 0xF0700000       // GPIO base
    li   t1, 0x7
    sw   t1, 0x28(t0)         // CHANNELDIR : GPIO[2:0] sorties
loop:
    li   t3, 0x1
    sw   t3, 0x30(t0)         // LED0 on (DOUTSET)
    li   t2, LED_DELAY_ITERATIONS
d1: addi t2, t2, -1
    bnez t2, d1
    sw   t3, 0x2C(t0)         // LED0 off (DOUTCLEAR)
    li   t3, 0x2
    sw   t3, 0x30(t0)         // LED1 on
    li   t2, LED_DELAY_ITERATIONS
d2: addi t2, t2, -1
    bnez t2, d2
    sw   t3, 0x2C(t0)
    li   t3, 0x4
    sw   t3, 0x30(t0)         // LED2 on
    li   t2, LED_DELAY_ITERATIONS
d3: addi t2, t2, -1
    bnez t2, d3
    sw   t3, 0x2C(t0)
    j    loop
