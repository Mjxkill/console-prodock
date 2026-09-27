// mini_wfi.S — preuve de vie CPU la plus pure : boucle de WFI.
// Si le CPU exécute quoi que ce soit, CORE0_WFI_MODE sort du socle et allume la LED4.
    .section .nds_vector, "ax"
    .global reset_vector
reset_vector:
    j _start
    .align 2

    .section .text
    .global _start
_start:
loop:
    wfi                       // le cœur dort : CORE0_WFI_MODE = 1 (visible sur LED4)
    j    loop
