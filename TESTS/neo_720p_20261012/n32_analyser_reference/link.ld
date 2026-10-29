ENTRY(_start)
MEMORY {
    ITCM (rx) : ORIGIN = 0xa0000000, LENGTH = 32K
    DTCM (rw) : ORIGIN = 0xa0200000, LENGTH = 64K
}
SECTIONS {
    .text : { KEEP(*(.entry)) *(.text*) *(.rodata*) } > ITCM
    .data : { *(.data*) *(.sdata*) } > DTCM
    .bss (NOLOAD) : { *(.bss*) *(.sbss*) *(COMMON) } > DTCM
    ASSERT(SIZEOF(.data) + SIZEOF(.bss) == 0, "Diagnostic must not need C startup")
}
