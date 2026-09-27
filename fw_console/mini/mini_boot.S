// mini_boot.S — firmware minimal SANS BSP : preuve de vie du CPU AE350.
// Écrit en boucle sur le slave AHB vidéo/registres à 0xE9000000 (hors APB, hors DDR).
// Les signaux vid_hsel/vid_haddr du socle sont câblés aux LED dans le top : si le CPU
// exécute ce code, les LED bougent.
// Vecteur de reset (premier mot de l'ITCM) : j _start ; puis boucle d'écritures.
    .section .nds_vector, "ax"
    .global reset_vector
reset_vector:
    j _start
    .align 2

    .section .text
    .global _start
_start:
    li   t0, 0xE9000000       // slave vidéo (pas de dépendance APB)
    li   t1, 0x00000001       // valeur écrite (visible sur vid_hwdata si on veut)
    li   t2, 0x00000000
loop:
    sw   t1, 0(t0)            // écriture : génère vid_hsel + haddr
    sw   t2, 4(t0)
    sw   t1, 8(t0)
    sw   t2, 12(t0)
    j    loop
