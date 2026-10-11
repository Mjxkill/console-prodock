/* itcm.ld — image de démarrage autonome : code et constantes en ITCM (0x80000000, 64 Ko, initialisé par
 * le bitstream), données en ILM (copiées depuis l'ITCM au démarrage par c_startup(), CFG_XIP), pile en DLM.
 * Le vecteur de reset du BSP (.nds_vector, start.S) doit être le premier mot de l'ITCM. */
ENTRY(_start)
MEMORY {
    ITCM (rx)  : ORIGIN = 0x80000000, LENGTH = 64K
    ILM  (rw)  : ORIGIN = 0xA0000000, LENGTH = 64K
    DLM  (rw)  : ORIGIN = 0xA0200000, LENGTH = 32K
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
    } > ILM AT > ITCM
    __data_lmastart = LOADADDR(.data);
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.sbss .sbss.*) *(.bss .bss.*) *(COMMON)
        . = ALIGN(8);
        _end = .;
    } > ILM
    PROVIDE(__global_pointer$ = __data_start + 0x800);
    PROVIDE(_heap_end = ORIGIN(ILM) + LENGTH(ILM));
    PROVIDE(_stack = ORIGIN(DLM) + LENGTH(DLM) - 16);
    /DISCARD/ : { *(.bootloader) *(.loader) }
}
