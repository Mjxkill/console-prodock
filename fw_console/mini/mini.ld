/* mini.ld — tout en ITCM : vecteur de reset en premier mot, rien d'autre. */
ENTRY(_start)
MEMORY {
    ITCM (rwx) : ORIGIN = 0x80000000, LENGTH = 64K
}
SECTIONS {
    .text : {
        KEEP(*(.nds_vector))
        *(.text .text.*)
        . = ALIGN(8);
    } > ITCM
    PROVIDE(_stack = ORIGIN(ITCM) + LENGTH(ITCM) - 16);
}
