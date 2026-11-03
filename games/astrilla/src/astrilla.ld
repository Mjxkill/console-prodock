/* ASTRILLA on C37: code in writable ILM, data/stack in DLM.
 * The reference ITCM/bitstream is unchanged. Never reset during download.
 */
ENTRY(_start)
MEMORY {
    ILM (rx) : ORIGIN = 0xA0000000, LENGTH = 64K
    DLM (rw) : ORIGIN = 0xA0200000, LENGTH = 32K
}
SECTIONS {
 .text : { KEEP(*(.nds_vector)) *(.text .text.*) *(.rodata .rodata.* .srodata .srodata.*) . = ALIGN(8); } > ILM
 .data : { __data_start = .; *(.sdata .sdata.*) *(.data .data.*) . = ALIGN(8); _edata = .; } > DLM AT > ILM
 __data_lmastart = LOADADDR(.data);
 .bss (NOLOAD) : { __bss_start = .; *(.sbss .sbss.*) *(.bss .bss.*) *(COMMON) . = ALIGN(8); _end = .; } > DLM
 PROVIDE(__global_pointer$ = __data_start + 0x800);
 PROVIDE(_heap_end = ORIGIN(DLM) + LENGTH(DLM) - 0x4000);
 PROVIDE(_stack = ORIGIN(DLM) + LENGTH(DLM) - 16);
 ASSERT(_end < ORIGIN(DLM) + LENGTH(DLM) - 0x4000, "ASTRILLA must leave 16 KiB stack")
 /DISCARD/ : { *(.bootloader) *(.loader) }
}
