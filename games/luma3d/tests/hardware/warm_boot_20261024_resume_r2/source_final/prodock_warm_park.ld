ENTRY(_start)
SECTIONS {
  . = 0xa000f000;
  .text : { *(.text) *(.rodata) }
  /DISCARD/ : { *(.comment) *(.note*) *(.riscv.attributes) }
  ASSERT(SIZEOF(.text) < 0x1000, "Warm stage exceeds reserved ILM page")
}
