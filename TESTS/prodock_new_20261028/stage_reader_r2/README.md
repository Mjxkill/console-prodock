# Stage reader R2 — descriptor mode correction only

R1 returned9 on the actual board because Linux mm/mmap.c clears VM_SHARED
when the file lacks FMODE_WRITE. The frozen GPU mmap callback requires
VM_SHARED. R2 therefore opens the GPU with O_RDWR, while the mapping stays
strictly PROT_READ. It issues no ioctl and performs no store to GPU memory.
The driver close side effect fb_restore remains unchanged.

The only C change is O_RDONLY→O_RDWR on the GPU open call. Source diff and
binary byte comparisons are provided. The compiler shifts instructions, so
many same-offset bytes differ despite that one source change. R1 is preserved.
The exact RV32 ELF remains13032bytes, SHA00bf58fbcf032f1c4c95f7c64cc0b85bb47c03b8f00dfb689de6a9ebc29534a0.
Packed FM4A data is unchanged. Invoke the new helper at a distinct path and
verify its complete bytes before execution, using the same output argument.

Host ASan/UBSan and exact RV32 QEMU checks cover decoding/output/refusal.
QEMU's sparse-file mmap fixture cannot reproduce a custom driver's VM_SHARED
validation, which explains why R1 passed that test. mmap_contract.json now
records the exact Linux transition and GPU callback requirement separately.
No hardware was accessed by this task.
