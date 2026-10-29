# Bounded COPY565 firmware derived from frozen BIN02

Allowed edits only: microdma.S, copy_model.py, ANALYSIS.md. No hardware, no RTL
or protected-test changes. Run fixed MCP run_tests before edit and after all
writes. Use official run_tests rather than manual repeated builds. Toolchain
and full assembly have already passed the actual isolated preflight. Don't
spend steps re-discovering git/environment; they are deliberately absent.

## Concrete changes

microdma.S is exact BIN02,928B compiled. Keep same code4000/journal6000 and
scratch[12000000,12000080). TARGET same16x1 withcolor12000020,Z12000040,stride32.
Replace CLEAR packet with COPY words:
1d000000 12000000 00100001 00000020 00000000 00000000 00100001 00000000
Source12000000,16x1,stride32; src/dst positions0,0; copy16x1 toTARGET+0.
This writes only32B at12000020; other96B unchanged. Keep source operands and
packet label positions so binary remains928B. Keep exact guards/polling/errors.

Final verify_memory a1=1 must expect source seed in offsets32..63 instead of
constantCLEAR. Two instructions suffice in place of the old li t3,6b4d6b4d:
 addi t3,t0,-32
 xor t3,t3,t2
Everything else stays identical. Allowed code offsets2b8/2bc and data380..39f;
protected validator enforces same other bytes and correct packet, not merely
source string matching. Update comments accurately without changing layout.

## Separate model, no copied RTL implementation

copy_model.py: class CopyCPU(RV32) deriving the protected rv32_model.py.
Keep TARGET and nonCOPY behavior through super().command(). Add original,
public-ABI COPY semantics: decode source width HIGH16, height LOW16, stride,
signed source/dst coordinates, requestedextentHIGH16/LOW16. Clip against
source extent and target (target bounds default full), use a byte copy model.
The only exercised layouts are nonoverlapping valid descriptors; explicitly
reject unsupported malformed/overlap, don't silently emulate unknown cases.

API for independent injected faults in protected tests:
- __init__ exposes lists `gpu_reads` and `gpu_byte_writes`, BYTE addresses.
- gpu_read(address,size): validate entire requested range within scratch128B
  before touching memory, log every byteaddress, return bytes. Range failures
  raise ValueError/AssertionError with 'scratch' in message.
- gpu_write(address,data): validate entire range first, log BYTE addresses,
  write bytes. No out-of-range effects before rejection.
- command(COPY) calls these methods (never inline inaccessible memory accesses).
  This is a logical byte-level model, not native bus transactions. The precise
  1native-read/1native-write footprint comes from the separate exact RTL bench.
- Model copies rows after clipping; requested1x16 clips to1x1=2bytes with the
  valid16x1source/target. Preserve source before writing. done increments after
  legal completion, rejected increments for invalid descriptor (no nativeIO).

Protected tests compare compiled execution, all32CPU loads/images/canaries,
32CPU stores, no access outsideILM/MMIO/scratch. Fault subclasses inject wrong
read data, missingwrite, canary corruption, native read/write outside scratch,
late completion and done2butbusy1. They also retain guards/trap/seed failures.
Do not weaken tests or claim hardware modeled. Diagnostic BIN revision has
same journal layout but new expected COPY data, distinct from oldCLEAR decoder.

## Context and deliverable

Hardware: flags1CLEARstalls; CPUreadback32 succeeds withseedunchanged. flags0
CLEAR hardware succeeds done2/busy0. NewCOPY compares a distinct request engine
against shared GPUstage/arb and the same destination. COPY adds GPUread return,
so its failure would not alone prove the shared stage faulty. Plan.md details.

Return working source/model and concise report including exact binarySHA,
test cases, differences, bounds and limits. The final action after report must
be successful fixed MCP run_tests; do not edit afterward. Supervisor creates
persistent ELF/bin after reviewing source. Codefiles≤1000physical lines.
