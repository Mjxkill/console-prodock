/* Image autonome : code, données et pile en ITCM (0x80000000, 64 Ko).
 * Le bitstream initialise code et données ; c_startup() vide la BSS.
 * Le vecteur de reset du BSP (.nds_vector, start.S) doit être le premier mot de l'ITCM. */
ENTRY(_start)
MEMORY {
    ITCM (rwx) : ORIGIN = 0x80000000, LENGTH = 64K
}
SECTIONS {
    .text : {
        KEEP(*(.nds_vector))
        *(.text .text.*)
        *(.rodata .rodata.* .srodata .srodata.*)
        . = ALIGN(8);
    } > ITCM
    .data : {
        __data_start = .;
        *(.sdata .sdata.*)
        *(.data .data.*)
        . = ALIGN(8);
        _edata = .;
    } > ITCM
    __data_lmastart = LOADADDR(.data);
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.sbss .sbss.*) *(.bss .bss.*) *(COMMON)
        . = ALIGN(8);
        _end = .;
    } > ITCM
    PROVIDE(__global_pointer$ = __data_start + 0x800);
    PROVIDE(_heap_end = ORIGIN(ITCM) + LENGTH(ITCM) - 1024);
    PROVIDE(_stack = ORIGIN(ITCM) + LENGTH(ITCM) - 16);
    /DISCARD/ : { *(.bootloader) *(.loader) }
}
